"""OpenAI OAuth payload models."""

from typing import ClassVar
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict, Field

from operator_core_olden.providers.openai.errors import OpenAIOAuthProtocolError
from operator_shared.settings.main import CallbackSettings
from operator_shared.time import epoch_ms

from .jwt import extract_account_id_from_id_token

OPENAI_OAUTH_CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann"
OPENAI_OAUTH_SCOPE = "openid profile email offline_access"
TOKEN_RESPONSE_MISSING_REFRESH_MESSAGE = "token response did not include a refresh token"  # noqa: S105


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
        return self.expires_at_ms and self.expires_at_ms <= current_ms

    def expires_within(self, *, now_ms: int | None = None, buffer_ms: int = 0) -> bool:
        """Report whether the credentials expire within the given buffer."""
        current_ms = epoch_ms() if now_ms is None else now_ms
        return self.expires_at_ms and self.expires_at_ms <= current_ms + buffer_ms


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
        if self.expires_in:
            expires_at_ms = current_ms + (self.expires_in * 1000)

        refresh_token = self.refresh_token
        if refresh_token is None and previous_credentials:
            refresh_token = previous_credentials.refresh_token
        if refresh_token is None:
            raise OpenAIOAuthProtocolError(TOKEN_RESPONSE_MISSING_REFRESH_MESSAGE)

        account_id = extract_account_id_from_id_token(self.id_token)
        if account_id is None and previous_credentials:
            account_id = previous_credentials.account_id

        return OpenAIOAuthCredentials(
            access_token=self.access_token,
            refresh_token=refresh_token,
            id_token=self.id_token,
            expires_at_ms=expires_at_ms,
            account_id=account_id,
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
        authorize_endpoint: str = "https://auth.openai.com/oauth/authorize",
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


__all__ = [
    "OPENAI_OAUTH_CLIENT_ID",
    "OPENAI_OAUTH_SCOPE",
    "TOKEN_RESPONSE_MISSING_REFRESH_MESSAGE",
    "AuthorizeRequest",
    "OpenAIOAuthCredentials",
    "OpenAITokenResponse",
    "RefreshTokenRequest",
    "TokenExchangeRequest",
]
