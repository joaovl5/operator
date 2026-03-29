"""OpenAI provider configuration, client helpers, and OAuth APIs."""

from . import oauth as _oauth
from .client import (
    CHATGPT_CODEX_BASE_URL,
    DEFAULT_REFRESH_BUFFER_MS,
    MISSING_CREDENTIALS_MESSAGE,
    OPERATOR_ORIGINATOR,
    REFRESH_REJECTED_MESSAGE,
    REMOVED_CREDENTIALS_MESSAGE,
    OpenAIModelProvider,
    build_chatgpt_oauth_client,
    get_openai_client,
    oauth_responses_settings,
)
from .errors import (
    OpenAIOAuthError,
    OpenAIOAuthModelConstraintError,
    OpenAIOAuthProtocolError,
    OpenAIOAuthReauthRequiredError,
    OpenAIOAuthSettingsConstraintError,
    OpenAIOAuthStateMismatchError,
    OpenAIOAuthStoreCorruptionError,
    OpenAIOAuthStoreError,
    OpenAIProviderError,
)
from .oauth import (
    OpenAIOAuthManager,
    OpenAIOAuthModelProvider,
    OpenAIOAuthStore,
    build_authorize_url,
    build_pkce_verifier_and_challenge,
    default_openai_oauth_credentials_path,
    exchange_authorization_code,
    extract_account_id,
    generate_oauth_state,
    refresh_access_token,
    validate_oauth_state,
)
from .types import (
    AuthorizeRequest,
    OpenAIModelConfig,
    OpenAIModelSettings,
    OpenAIOAuthCredentials,
    OpenAITokenResponse,
    RefreshTokenRequest,
    TokenExchangeRequest,
)

OPENAI_OAUTH_AUTHORIZE_ENDPOINT = _oauth.OPENAI_OAUTH_AUTHORIZE_ENDPOINT
OPENAI_OAUTH_CLIENT_ID = _oauth.OPENAI_OAUTH_CLIENT_ID
OPENAI_OAUTH_REDIRECT_URI = _oauth.OPENAI_OAUTH_REDIRECT_URI
OPENAI_OAUTH_SCOPE = _oauth.OPENAI_OAUTH_SCOPE
OPENAI_OAUTH_TOKEN_ENDPOINT = _oauth.OPENAI_OAUTH_TOKEN_ENDPOINT

__all__ = [
    "CHATGPT_CODEX_BASE_URL",
    "DEFAULT_REFRESH_BUFFER_MS",
    "MISSING_CREDENTIALS_MESSAGE",
    "OPENAI_OAUTH_AUTHORIZE_ENDPOINT",
    "OPENAI_OAUTH_CLIENT_ID",
    "OPENAI_OAUTH_REDIRECT_URI",
    "OPENAI_OAUTH_SCOPE",
    "OPENAI_OAUTH_TOKEN_ENDPOINT",
    "OPERATOR_ORIGINATOR",
    "REFRESH_REJECTED_MESSAGE",
    "REMOVED_CREDENTIALS_MESSAGE",
    "AuthorizeRequest",
    "OpenAIModelConfig",
    "OpenAIModelProvider",
    "OpenAIModelSettings",
    "OpenAIOAuthCredentials",
    "OpenAIOAuthError",
    "OpenAIOAuthManager",
    "OpenAIOAuthModelConstraintError",
    "OpenAIOAuthModelProvider",
    "OpenAIOAuthProtocolError",
    "OpenAIOAuthReauthRequiredError",
    "OpenAIOAuthSettingsConstraintError",
    "OpenAIOAuthStateMismatchError",
    "OpenAIOAuthStore",
    "OpenAIOAuthStoreCorruptionError",
    "OpenAIOAuthStoreError",
    "OpenAIProviderError",
    "OpenAITokenResponse",
    "RefreshTokenRequest",
    "TokenExchangeRequest",
    "build_authorize_url",
    "build_chatgpt_oauth_client",
    "build_pkce_verifier_and_challenge",
    "default_openai_oauth_credentials_path",
    "exchange_authorization_code",
    "extract_account_id",
    "generate_oauth_state",
    "get_openai_client",
    "oauth_responses_settings",
    "refresh_access_token",
    "validate_oauth_state",
]
