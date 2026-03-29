"""OpenAI OAuth helpers, protocol flows, and store adapter."""

import asyncio
import base64
import hashlib
import json
import os
import secrets
from collections.abc import Callable, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, override

import httpx
from attrs import define, field
from pydantic import ValidationError
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from operator_core.providers.utils.store import JsonCredentialStore
from operator_core.providers.utils.store.utils import get_async_path_lock
from operator_shared.settings.main import CallbackSettings
from operator_shared.time import epoch_ms

from .client import (
    DEFAULT_REFRESH_BUFFER_MS,
    MISSING_CREDENTIALS_MESSAGE,
    REFRESH_REJECTED_MESSAGE,
    REMOVED_CREDENTIALS_MESSAGE,
    BaseOpenAIModelProvider,
    build_chatgpt_oauth_client,
)
from .errors import (
    OpenAIOAuthModelConstraintError,
    OpenAIOAuthProtocolError,
    OpenAIOAuthReauthRequiredError,
    OpenAIOAuthSettingsConstraintError,
    OpenAIOAuthStateMismatchError,
    OpenAIOAuthStoreCorruptionError,
)
from .types import (
    ACCOUNT_ID_CLAIMS,
    OPENAI_OAUTH_CLIENT_ID,
    OPENAI_OAUTH_SCOPE,
    TOKEN_RESPONSE_MISSING_REFRESH_MESSAGE,
    AuthorizeRequest,
    OpenAIModelConfig,
    OpenAIModelSettings,
    OpenAIOAuthCredentials,
    OpenAITokenResponse,
    RefreshTokenRequest,
    TokenExchangeRequest,
)

if TYPE_CHECKING:
    from openai import AsyncOpenAI
    from pydantic_ai.models import Model

OPENAI_OAUTH_AUTHORIZE_ENDPOINT = "https://auth.openai.com/oauth/authorize"
OPENAI_OAUTH_TOKEN_ENDPOINT = "https://auth.openai.com/oauth/token"  # noqa: S105
OPENAI_OAUTH_REDIRECT_URI = CallbackSettings().redirect_uri()
STATE_MISMATCH_MESSAGE = "OpenAI callback state mismatch"
TOKEN_REQUEST_INVALID_JSON_MESSAGE = "token endpoint returned invalid JSON"  # noqa: S105
TOKEN_REQUEST_MISSING_FIELDS_MESSAGE = "token endpoint response is missing required fields"  # noqa: S105
RELOGIN_REQUIRED_MESSAGE = "OpenAI OAuth credentials require re-login"
AUTH_ERROR_CODES = frozenset({400, 401, 403})
AUTH_ERROR_NAMES = frozenset(
    {
        "access_denied",
        "consent_required",
        "expired_token",
        "invalid_grant",
        "login_required",
        "token_expired",
    }
)
_JWT_PART_COUNT = 3
OPENAI_OAUTH_ALLOWED_MODELS = ("gpt-5.3-codex",)


type RefreshAccessToken = Callable[[str], OpenAITokenResponse]


def _refresh_access_token_default(refresh_token: str) -> OpenAITokenResponse:
    return refresh_access_token(refresh_token=refresh_token)


def default_openai_oauth_credentials_path() -> Path:
    """Return the default on-disk location for OpenAI OAuth credentials."""
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    base_dir = Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"
    return base_dir / "operator" / "auth" / "openai.json"


class OpenAIOAuthStore(JsonCredentialStore[OpenAIOAuthCredentials]):
    """Store OpenAI OAuth credentials using the reusable JSON store."""

    def __init__(
        self,
        *,
        path: Path | None = None,
        base_dir: Path | None = None,
    ) -> None:
        """Initialize the OpenAI OAuth store from an explicit or derived path."""
        super().__init__(
            model_type=OpenAIOAuthCredentials,
            path=_resolve_store_path(path=path, base_dir=base_dir),
        )

    def _build_corruption_error(self, *, message: str) -> OpenAIOAuthStoreCorruptionError:
        return OpenAIOAuthStoreCorruptionError(message)


@define(kw_only=True)
class OpenAIOAuthManager:
    """Loads, refreshes, and persists OAuth credentials for ChatGPT traffic."""

    store: OpenAIOAuthStore
    refresh_access_token: RefreshAccessToken = _refresh_access_token_default
    refresh_buffer_ms: int = DEFAULT_REFRESH_BUFFER_MS

    @property
    def current_credentials(self) -> OpenAIOAuthCredentials | None:
        """Return the latest credentials currently stored on disk, if any."""
        return self.store.load()

    async def get_access_token(self) -> str:
        """Return a usable access token, refreshing and persisting if needed."""
        credentials = self._require_credentials()
        if not credentials.expires_within(now_ms=epoch_ms(), buffer_ms=self.refresh_buffer_ms):
            return credentials.access_token

        async with get_async_path_lock(path=self.store.path):
            credentials = self._require_credentials()
            if not credentials.expires_within(now_ms=epoch_ms(), buffer_ms=self.refresh_buffer_ms):
                return credentials.access_token

            return await self._refresh_credentials(credentials)

    def _require_credentials(self) -> OpenAIOAuthCredentials:
        credentials = self.store.load()
        if credentials is None:
            raise OpenAIOAuthReauthRequiredError(MISSING_CREDENTIALS_MESSAGE)
        return credentials

    async def _refresh_credentials(self, credentials: OpenAIOAuthCredentials) -> str:
        try:
            token_response = await asyncio.to_thread(
                self.refresh_access_token,
                credentials.refresh_token,
            )
        except OpenAIOAuthReauthRequiredError as error:
            raise OpenAIOAuthReauthRequiredError(REFRESH_REJECTED_MESSAGE) from error

        def persist_refresh(
            current: OpenAIOAuthCredentials | None,
        ) -> OpenAIOAuthCredentials:
            if current is None:
                raise OpenAIOAuthReauthRequiredError(REMOVED_CREDENTIALS_MESSAGE)

            if current != credentials and not current.expires_within(
                now_ms=epoch_ms(),
                buffer_ms=self.refresh_buffer_ms,
            ):
                return current

            return token_response.to_credentials(
                now_ms=epoch_ms(),
                previous_credentials=current,
            )

        refreshed_credentials = self.store.update(persist_refresh)
        if refreshed_credentials is None:
            raise OpenAIOAuthReauthRequiredError(REMOVED_CREDENTIALS_MESSAGE)
        return refreshed_credentials.access_token


def _resolve_store_path(*, path: Path | None, base_dir: Path | None) -> Path:
    if path is not None and base_dir is not None:
        message = "path and base_dir are mutually exclusive"
        raise ValueError(message)

    if path is not None:
        return path
    if base_dir is not None:
        return base_dir / "auth" / "openai.json"
    return default_openai_oauth_credentials_path()


def build_pkce_verifier_and_challenge() -> tuple[str, str]:
    """Build a PKCE verifier and matching S256 code challenge."""
    verifier = _urlsafe_b64(secrets.token_bytes(48))
    challenge = _urlsafe_b64(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def generate_oauth_state() -> str:
    """Generate the state value used to bind authorize and callback requests."""
    return secrets.token_urlsafe(32)


def validate_oauth_state(*, received_state: str, pending_state: str) -> str:
    """Validate the callback state value and return it when it matches."""
    if received_state != pending_state:
        raise OpenAIOAuthStateMismatchError(STATE_MISMATCH_MESSAGE)
    return received_state


def build_authorize_url(
    *, state: str, code_challenge: str, redirect_uri: str = OPENAI_OAUTH_REDIRECT_URI
) -> str:
    """Build the OpenAI OAuth authorization URL for the local callback flow."""
    return AuthorizeRequest(
        state=state,
        code_challenge=code_challenge,
        redirect_uri=redirect_uri,
    ).authorize_url(authorize_endpoint=OPENAI_OAUTH_AUTHORIZE_ENDPOINT)


def exchange_authorization_code(
    *,
    code: str,
    code_verifier: str,
    redirect_uri: str = OPENAI_OAUTH_REDIRECT_URI,
    client: httpx.Client | None = None,
) -> OpenAITokenResponse:
    """Exchange an authorization code for OAuth tokens."""
    return _post_token_request(
        request_model=TokenExchangeRequest(
            code=code,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
        ),
        client=client,
    )


def refresh_access_token(
    *,
    refresh_token: str,
    client: httpx.Client | None = None,
) -> OpenAITokenResponse:
    """Refresh an OAuth access token using the stored refresh token."""
    return _post_token_request(
        request_model=RefreshTokenRequest(refresh_token=refresh_token),
        client=client,
    )


def extract_account_id(id_token: str | None) -> str | None:
    """Extract the preferred ChatGPT account identifier from an ID token."""
    return extract_account_id_from_id_token(id_token)


def add_base64_padding(value: str) -> str:
    """Add JWT-safe base64 padding when needed."""
    return value + ("=" * (-len(value) % 4))


def decode_jwt_payload(token: str) -> Mapping[str, object] | None:
    """Decode a JWT payload without verifying its signature."""
    parts = token.split(".")
    if len(parts) != _JWT_PART_COUNT:
        return None

    try:
        payload_bytes = base64.urlsafe_b64decode(add_base64_padding(parts[1]))
        payload = json.loads(payload_bytes)
    except ValueError:
        return None

    return payload if isinstance(payload, Mapping) else None


def extract_account_id_from_id_token(id_token: str | None) -> str | None:
    """Extract the preferred ChatGPT account identifier from an ID token."""
    if not id_token:
        return None

    payload = decode_jwt_payload(id_token)
    if not isinstance(payload, Mapping):
        return None

    for claim_name in ACCOUNT_ID_CLAIMS:
        claim_value = payload.get(claim_name)
        if isinstance(claim_value, str) and claim_value.strip():
            return claim_value

    return None


@define(kw_only=True)
class OpenAIOAuthModelProvider(BaseOpenAIModelProvider):
    """OAuth-backed OpenAI provider using responses models by default."""

    store: OpenAIOAuthStore
    _oauth_manager: OpenAIOAuthManager | None = field(init=False, default=None)
    _oauth_client: AsyncOpenAI | None = field(init=False, default=None)
    _oauth_provider: OpenAIProvider | None = field(init=False, default=None)

    @override
    def get_openai_client(self) -> AsyncOpenAI:
        """Return the cached OAuth OpenAI client."""
        client = self._oauth_client
        if client is None:
            client = build_chatgpt_oauth_client(manager=self.oauth_manager)
            self._oauth_client = client
        return client

    @property
    def oauth_manager(self) -> OpenAIOAuthManager:
        """Return the lazily-created OAuth manager for this provider."""
        manager = self._oauth_manager
        if manager is None:
            manager = OpenAIOAuthManager(store=self.store)
            self._oauth_manager = manager
        return manager

    @override
    def build_provider(self) -> OpenAIProvider:
        """Return the cached provider wrapper for the OAuth client."""
        provider = self._oauth_provider
        if provider is None:
            provider = OpenAIProvider(openai_client=self.get_openai_client())
            self._oauth_provider = provider
        return provider

    @override
    def build_model(self, *, model_config: OpenAIModelConfig) -> Model:
        """Build a validated OAuth-backed responses model."""
        if model_config.name not in OPENAI_OAUTH_ALLOWED_MODELS:
            message = f"Unsupported OpenAI OAuth model: {model_config.name}"
            raise OpenAIOAuthModelConstraintError(message)

        settings = model_config.settings
        if settings.openai_previous_response_id is not None:
            message = "openai_previous_response_id is not supported for OAuth"
            raise OpenAIOAuthSettingsConstraintError(message)
        if settings.openai_store is True:
            message = "openai_store must be false for OAuth"
            raise OpenAIOAuthSettingsConstraintError(message)
        if settings.openai_send_reasoning_ids is True:
            message = "openai_send_reasoning_ids must be false for OAuth"
            raise OpenAIOAuthSettingsConstraintError(message)

        oauth_defaults = OpenAIModelSettings.oauth_defaults(
            openai_store=False,
            openai_send_reasoning_ids=False,
        )
        return OpenAIResponsesModel(
            model_name=model_config.name,
            provider=self.build_provider(),
            settings=oauth_defaults.to_model_settings(temperature=model_config.temperature),
        )


def _post_token_request(
    *,
    request_model: TokenExchangeRequest | RefreshTokenRequest,
    client: httpx.Client | None,
) -> OpenAITokenResponse:
    with _token_client(client=client) as token_client:
        try:
            response = token_client.post(
                OPENAI_OAUTH_TOKEN_ENDPOINT,
                data=request_model.form_data(),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        except httpx.HTTPError as error:
            message = "token request failed"
            raise OpenAIOAuthProtocolError(message) from error

    if response.is_error:
        _raise_for_auth_error(response)
        message = f"token request failed with status {response.status_code}"
        raise OpenAIOAuthProtocolError(message)

    try:
        payload = response.json()
    except ValueError as error:
        raise OpenAIOAuthProtocolError(TOKEN_REQUEST_INVALID_JSON_MESSAGE) from error

    try:
        return OpenAITokenResponse.model_validate(payload)
    except ValidationError as error:
        raise OpenAIOAuthProtocolError(TOKEN_REQUEST_MISSING_FIELDS_MESSAGE) from error


def _raise_for_auth_error(response: httpx.Response) -> None:
    payload = _read_json_error_body(response)
    error_name = payload.get("error") if isinstance(payload, Mapping) else None

    if (
        response.status_code in AUTH_ERROR_CODES
        and isinstance(error_name, str)
        and error_name in AUTH_ERROR_NAMES
    ):
        raise OpenAIOAuthReauthRequiredError(RELOGIN_REQUIRED_MESSAGE)


def _read_json_error_body(response: httpx.Response) -> Mapping[str, object] | None:
    try:
        payload = response.json()
    except ValueError:
        return None
    return payload if isinstance(payload, Mapping) else None


@contextmanager
def _token_client(*, client: httpx.Client | None):
    if client is not None:
        yield client
        return

    with httpx.Client() as default_client:
        yield default_client


def _urlsafe_b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


__all__ = [
    "ACCOUNT_ID_CLAIMS",
    "AUTH_ERROR_CODES",
    "AUTH_ERROR_NAMES",
    "OPENAI_OAUTH_AUTHORIZE_ENDPOINT",
    "OPENAI_OAUTH_CLIENT_ID",
    "OPENAI_OAUTH_REDIRECT_URI",
    "OPENAI_OAUTH_SCOPE",
    "OPENAI_OAUTH_TOKEN_ENDPOINT",
    "RELOGIN_REQUIRED_MESSAGE",
    "STATE_MISMATCH_MESSAGE",
    "TOKEN_REQUEST_INVALID_JSON_MESSAGE",
    "TOKEN_REQUEST_MISSING_FIELDS_MESSAGE",
    "TOKEN_RESPONSE_MISSING_REFRESH_MESSAGE",
    "AuthorizeRequest",
    "OpenAIOAuthCredentials",
    "OpenAIOAuthManager",
    "OpenAIOAuthModelProvider",
    "OpenAIOAuthStore",
    "OpenAITokenResponse",
    "RefreshTokenRequest",
    "TokenExchangeRequest",
    "add_base64_padding",
    "build_authorize_url",
    "build_pkce_verifier_and_challenge",
    "decode_jwt_payload",
    "default_openai_oauth_credentials_path",
    "exchange_authorization_code",
    "extract_account_id",
    "extract_account_id_from_id_token",
    "generate_oauth_state",
    "refresh_access_token",
    "validate_oauth_state",
]
