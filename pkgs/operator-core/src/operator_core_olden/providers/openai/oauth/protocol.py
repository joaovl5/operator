"""OpenAI OAuth protocol helpers."""

import base64
import hashlib
import secrets
from collections.abc import Mapping
from contextlib import contextmanager

import httpx
from pydantic import TypeAdapter, ValidationError

from operator_core_olden.providers.openai.errors import (
    OpenAIOAuthProtocolError,
    OpenAIOAuthReauthRequiredError,
    OpenAIOAuthStateMismatchError,
)
from operator_shared.settings.main import CallbackSettings

from .types import (
    AuthorizeRequest,
    OpenAITokenResponse,
    RefreshTokenRequest,
    TokenExchangeRequest,
)

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


def _urlsafe_b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


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
    *,
    state: str,
    code_challenge: str,
    redirect_uri: str = OPENAI_OAUTH_REDIRECT_URI,
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
        payload_object = TypeAdapter(object).validate_json(response.content)
    except ValidationError as error:
        raise OpenAIOAuthProtocolError(TOKEN_REQUEST_INVALID_JSON_MESSAGE) from error

    try:
        return OpenAITokenResponse.model_validate(payload_object)
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
        return TypeAdapter(dict[str, object]).validate_json(response.content)
    except ValidationError:
        return None


@contextmanager
def _token_client(*, client: httpx.Client | None):
    if client:
        yield client
        return

    with httpx.Client() as default_client:
        yield default_client


__all__ = [
    "AUTH_ERROR_CODES",
    "AUTH_ERROR_NAMES",
    "OPENAI_OAUTH_AUTHORIZE_ENDPOINT",
    "OPENAI_OAUTH_REDIRECT_URI",
    "OPENAI_OAUTH_TOKEN_ENDPOINT",
    "RELOGIN_REQUIRED_MESSAGE",
    "STATE_MISMATCH_MESSAGE",
    "TOKEN_REQUEST_INVALID_JSON_MESSAGE",
    "TOKEN_REQUEST_MISSING_FIELDS_MESSAGE",
    "build_authorize_url",
    "build_pkce_verifier_and_challenge",
    "exchange_authorization_code",
    "generate_oauth_state",
    "refresh_access_token",
    "validate_oauth_state",
]
