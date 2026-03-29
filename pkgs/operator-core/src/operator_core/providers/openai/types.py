"""OpenAI-specific provider configuration and OAuth payload models."""

import base64
import json
from typing import ClassVar
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field
from pydantic_ai.models.openai import OpenAIResponsesModelSettings

from operator_core.providers.types import ModelConfig, ModelSettings
from operator_shared.settings.main import CallbackSettings
from operator_shared.time import epoch_ms

from .errors import OpenAIOAuthProtocolError

OPENAI_OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OPENAI_OAUTH_SCOPE = "openid profile email offline_access"
_DEFAULT_OPENAI_OAUTH_AUTHORIZE_ENDPOINT = "https://auth.openai.com/oauth/authorize"
TOKEN_RESPONSE_MISSING_REFRESH_MESSAGE = "token response did not include a refresh token"  # noqa: S105
ACCOUNT_ID_CLAIMS = (
    "chatgpt_account_id",
    "https://auth.openai.com/account_id",
    "https://api.openai.com/auth/account_id",
    "account_id",
)
_JWT_PART_COUNT = 3


class OpenAIOAuthCredentials(BaseModel):
    """Persisted OpenAI OAuth credentials used for ChatGPT-backed traffic."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    id_token: str | None = None
    expires_at_ms: int | None = None
    account_id: str | None = None
    scope: str | None = None
    token_type: str = "Bearer"  # noqa: S105

    def is_expired(self, *, now_ms: int | None = None) -> bool:
        """Report whether the credentials are expired at the given time."""
        current_ms = epoch_ms() if now_ms is None else now_ms
        return self.expires_at_ms is not None and self.expires_at_ms <= current_ms

    def expires_within(self, *, now_ms: int | None = None, buffer_ms: int = 0) -> bool:
        """Report whether the credentials expire within the given buffer."""
        current_ms = epoch_ms() if now_ms is None else now_ms
        return self.expires_at_ms is not None and self.expires_at_ms <= current_ms + buffer_ms


class OpenAITokenResponse(BaseModel):
    """Validated token payload returned by the OpenAI OAuth token endpoint."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str | None = None
    id_token: str | None = None
    expires_in: int | None = None
    scope: str | None = None
    token_type: str = "Bearer"  # noqa: S105

    def to_credentials(
        self,
        *,
        now_ms: int | None = None,
        previous_credentials: OpenAIOAuthCredentials | None = None,
    ) -> OpenAIOAuthCredentials:
        """Convert a token response into persisted OAuth credentials."""
        current_ms = epoch_ms() if now_ms is None else now_ms
        expires_at_ms = None
        if self.expires_in is not None:
            expires_at_ms = current_ms + (self.expires_in * 1000)

        refresh_token = self.refresh_token
        if refresh_token is None and previous_credentials is not None:
            refresh_token = previous_credentials.refresh_token
        if refresh_token is None:
            raise OpenAIOAuthProtocolError(TOKEN_RESPONSE_MISSING_REFRESH_MESSAGE)

        return OpenAIOAuthCredentials(
            access_token=self.access_token,
            refresh_token=refresh_token,
            id_token=self.id_token,
            expires_at_ms=expires_at_ms,
            account_id=_extract_account_id_from_id_token(self.id_token),
            scope=self.scope,
            token_type=self.token_type,
        )


class AuthorizeRequest(BaseModel):
    """Typed authorize-request payload for the local OpenAI OAuth flow."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    state: str
    code_challenge: str
    response_type: str = "code"
    client_id: str = OPENAI_OAUTH_CLIENT_ID
    redirect_uri: str = Field(default_factory=CallbackSettings().redirect_uri)
    scope: str = OPENAI_OAUTH_SCOPE
    code_challenge_method: str = "S256"
    id_token_add_organizations: str = "true"  # noqa: S105
    codex_cli_simplified_flow: str = "true"

    def query_params(self) -> dict[str, str]:
        """Return the authorize-request query parameters."""
        return self.model_dump(mode="json")

    def authorize_url(
        self,
        *,
        authorize_endpoint: str = _DEFAULT_OPENAI_OAUTH_AUTHORIZE_ENDPOINT,
    ) -> str:
        """Build the full authorize URL for this request."""
        return f"{authorize_endpoint}?{urlencode(self.query_params())}"


class TokenExchangeRequest(BaseModel):
    """Typed authorization-code exchange payload for the token endpoint."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    code: str
    code_verifier: str
    grant_type: str = "authorization_code"
    client_id: str = OPENAI_OAUTH_CLIENT_ID
    redirect_uri: str = Field(default_factory=CallbackSettings().redirect_uri)

    def form_data(self) -> dict[str, str]:
        """Return form-encoded token exchange fields."""
        return self.model_dump(mode="json")


class RefreshTokenRequest(BaseModel):
    """Typed refresh-token payload for the token endpoint."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    refresh_token: str
    grant_type: str = "refresh_token"
    client_id: str = OPENAI_OAUTH_CLIENT_ID

    def form_data(self) -> dict[str, str]:
        """Return form-encoded refresh fields."""
        return self.model_dump(mode="json")


class OpenAIModelSettings(ModelSettings):
    """Serializable OpenAI model settings payload."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    openai_store: bool | None = None
    openai_send_reasoning_ids: bool | None = None
    openai_previous_response_id: str | None = None

    @classmethod
    def oauth_defaults(
        cls,
        *,
        openai_store: bool = False,
        openai_send_reasoning_ids: bool = False,
    ) -> OpenAIModelSettings:
        """Build stateless OAuth-safe OpenAI settings defaults."""
        return cls(
            openai_store=openai_store,
            openai_send_reasoning_ids=openai_send_reasoning_ids,
        )

    def to_model_settings(self, *, temperature: float) -> OpenAIResponsesModelSettings:
        """Convert validated OpenAI settings into pydantic-ai settings."""
        model_settings = OpenAIResponsesModelSettings(temperature=temperature)

        if self.openai_store is not None:
            model_settings["openai_store"] = self.openai_store
        if self.openai_send_reasoning_ids is not None:
            model_settings["openai_send_reasoning_ids"] = self.openai_send_reasoning_ids
        if self.openai_previous_response_id is not None:
            model_settings["openai_previous_response_id"] = self.openai_previous_response_id

        return model_settings


class OpenAIModelConfig(ModelConfig[OpenAIModelSettings]):
    """Serializable OpenAI model configuration."""

    settings: OpenAIModelSettings = Field(default_factory=OpenAIModelSettings)


__all__ = [
    "ACCOUNT_ID_CLAIMS",
    "OPENAI_OAUTH_CLIENT_ID",
    "OPENAI_OAUTH_SCOPE",
    "TOKEN_RESPONSE_MISSING_REFRESH_MESSAGE",
    "AuthorizeRequest",
    "OpenAIModelConfig",
    "OpenAIModelSettings",
    "OpenAIOAuthCredentials",
    "OpenAITokenResponse",
    "RefreshTokenRequest",
    "TokenExchangeRequest",
]


def _add_base64_padding(value: str) -> str:
    return value + ("=" * (-len(value) % 4))


def _decode_jwt_payload(token: str) -> dict[str, object] | None:
    parts = token.split(".")
    if len(parts) != _JWT_PART_COUNT:
        return None

    try:
        payload_bytes = base64.urlsafe_b64decode(_add_base64_padding(parts[1]))
        payload = json.loads(payload_bytes)
    except ValueError:
        return None

    return payload if isinstance(payload, dict) else None


def _extract_account_id_from_id_token(id_token: str | None) -> str | None:
    if not id_token:
        return None

    payload = _decode_jwt_payload(id_token)
    if payload is None:
        return None

    for claim_name in ACCOUNT_ID_CLAIMS:
        claim_value = payload.get(claim_name)
        if isinstance(claim_value, str) and claim_value.strip():
            return claim_value

    return None
