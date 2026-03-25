"""OpenAI OAuth request and response models."""

from typing import ClassVar
from urllib.parse import urlencode

from pydantic import BaseModel, ConfigDict

from operator_shared.time import epoch_ms

from .errors import OpenAIOAuthProtocolError
from .utils import (
    OPENAI_OAUTH_AUTHORIZE_ENDPOINT,
    OPENAI_OAUTH_CLIENT_ID,
    OPENAI_OAUTH_REDIRECT_URI,
    OPENAI_OAUTH_SCOPE,
    TOKEN_RESPONSE_MISSING_REFRESH_MESSAGE,
    TOKEN_TYPE_BEARER,
    extract_account_id_from_id_token,
)


class OpenAIOAuthCredentials(BaseModel):
    """Persisted OpenAI OAuth credentials used for ChatGPT-backed traffic."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str
    id_token: str | None = None
    expires_at_ms: int | None = None
    account_id: str | None = None
    scope: str | None = None
    token_type: str = TOKEN_TYPE_BEARER

    def is_expired(self, *, now_ms: int | None = None) -> bool:
        """Report whether the credentials are expired at the given time."""
        if self.expires_at_ms is None:
            return False
        current_ms = epoch_ms() if now_ms is None else now_ms
        return self.expires_at_ms <= current_ms

    def expires_within(self, *, now_ms: int | None = None, buffer_ms: int = 0) -> bool:
        """Report whether the credentials expire within the given buffer."""
        if self.expires_at_ms is None:
            return False
        current_ms = epoch_ms() if now_ms is None else now_ms
        return self.expires_at_ms <= current_ms + buffer_ms


class OpenAITokenResponse(BaseModel):
    """Validated token payload returned by the OpenAI OAuth token endpoint."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    access_token: str
    refresh_token: str | None = None
    id_token: str | None = None
    expires_in: int | None = None
    scope: str | None = None
    token_type: str = TOKEN_TYPE_BEARER

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
            account_id=extract_account_id_from_id_token(self.id_token),
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
    redirect_uri: str = OPENAI_OAUTH_REDIRECT_URI
    scope: str = OPENAI_OAUTH_SCOPE
    code_challenge_method: str = "S256"
    id_token_add_organizations: str = "true"  # noqa: S105
    codex_cli_simplified_flow: str = "true"

    def query_params(self) -> dict[str, str]:
        """Return the authorize-request query parameters."""
        return self.model_dump(mode="json")

    def authorize_url(self) -> str:
        """Build the full authorize URL for this request."""
        return f"{OPENAI_OAUTH_AUTHORIZE_ENDPOINT}?{urlencode(self.query_params())}"


class TokenExchangeRequest(BaseModel):
    """Typed authorization-code exchange payload for the token endpoint."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    code: str
    code_verifier: str
    grant_type: str = "authorization_code"
    client_id: str = OPENAI_OAUTH_CLIENT_ID
    redirect_uri: str = OPENAI_OAUTH_REDIRECT_URI

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
