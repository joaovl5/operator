"""OpenAI OAuth helpers and models."""

import secrets as _secrets

from .errors import (
    OpenAIOAuthError,
    OpenAIOAuthProtocolError,
    OpenAIOAuthReauthRequiredError,
    OpenAIOAuthStateMismatchError,
)
from .main import (
    OPENAI_OAUTH_AUTHORIZE_ENDPOINT,
    OPENAI_OAUTH_CLIENT_ID,
    OPENAI_OAUTH_REDIRECT_URI,
    OPENAI_OAUTH_SCOPE,
    OPENAI_OAUTH_TOKEN_ENDPOINT,
    build_authorize_url,
    build_pkce_verifier_and_challenge,
    exchange_authorization_code,
    extract_account_id,
    generate_oauth_state,
    refresh_access_token,
    validate_oauth_state,
)
from .types import (
    AuthorizeRequest,
    OpenAIOAuthCredentials,
    OpenAITokenResponse,
    RefreshTokenRequest,
    TokenExchangeRequest,
)

secrets = _secrets

__all__ = [
    "OPENAI_OAUTH_AUTHORIZE_ENDPOINT",
    "OPENAI_OAUTH_CLIENT_ID",
    "OPENAI_OAUTH_REDIRECT_URI",
    "OPENAI_OAUTH_SCOPE",
    "OPENAI_OAUTH_TOKEN_ENDPOINT",
    "AuthorizeRequest",
    "OpenAIOAuthCredentials",
    "OpenAIOAuthError",
    "OpenAIOAuthProtocolError",
    "OpenAIOAuthReauthRequiredError",
    "OpenAIOAuthStateMismatchError",
    "OpenAITokenResponse",
    "RefreshTokenRequest",
    "TokenExchangeRequest",
    "build_authorize_url",
    "build_pkce_verifier_and_challenge",
    "exchange_authorization_code",
    "extract_account_id",
    "generate_oauth_state",
    "refresh_access_token",
    "validate_oauth_state",
]
