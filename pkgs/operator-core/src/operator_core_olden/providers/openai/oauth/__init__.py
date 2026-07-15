"""OpenAI OAuth public API."""

from operator_core_olden.providers.openai.errors import (
  OpenAIOAuthError,
  OpenAIOAuthProtocolError,
  OpenAIOAuthReauthRequiredError,
  OpenAIOAuthStateMismatchError,
  OpenAIOAuthStoreCorruptionError,
  OpenAIOAuthStoreError,
  OpenAIProviderError,
)

from .chatgpt import (
  CHATGPT_CODEX_BASE_URL,
  OPERATOR_ORIGINATOR,
  OpenAIOAuthManagerProtocol,
  build_chatgpt_oauth_client,
)
from .jwt import (
  add_base64_padding,
  decode_jwt_payload,
  extract_account_id_from_id_token,
)
from .manager import (
  DEFAULT_REFRESH_BUFFER_MS,
  MISSING_CREDENTIALS_MESSAGE,
  REFRESH_REJECTED_MESSAGE,
  REMOVED_CREDENTIALS_MESSAGE,
  OpenAIOAuthManager,
)
from .protocol import (
  AUTH_ERROR_CODES,
  AUTH_ERROR_NAMES,
  OPENAI_OAUTH_AUTHORIZE_ENDPOINT,
  OPENAI_OAUTH_REDIRECT_URI,
  OPENAI_OAUTH_TOKEN_ENDPOINT,
  RELOGIN_REQUIRED_MESSAGE,
  STATE_MISMATCH_MESSAGE,
  TOKEN_REQUEST_INVALID_JSON_MESSAGE,
  TOKEN_REQUEST_MISSING_FIELDS_MESSAGE,
  build_authorize_url,
  build_pkce_verifier_and_challenge,
  exchange_authorization_code,
  generate_oauth_state,
  refresh_access_token,
  validate_oauth_state,
)
from .provider import OpenAIOAuthModelProvider
from .settings import (
  OpenAIOAuthModelConfig,
  OpenAIOAuthModelSettings,
  oauth_responses_settings,
)
from .store import (
  OpenAIOAuthStore,
  default_openai_oauth_credentials_path,
)
from .types import (
  OPENAI_OAUTH_CLIENT_ID,
  OPENAI_OAUTH_SCOPE,
  TOKEN_RESPONSE_MISSING_REFRESH_MESSAGE,
  AuthorizeRequest,
  OpenAIOAuthCredentials,
  OpenAITokenResponse,
  RefreshTokenRequest,
  TokenExchangeRequest,
)

__all__ = [
  "AUTH_ERROR_CODES",
  "AUTH_ERROR_NAMES",
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
  "RELOGIN_REQUIRED_MESSAGE",
  "REMOVED_CREDENTIALS_MESSAGE",
  "STATE_MISMATCH_MESSAGE",
  "TOKEN_REQUEST_INVALID_JSON_MESSAGE",
  "TOKEN_REQUEST_MISSING_FIELDS_MESSAGE",
  "TOKEN_RESPONSE_MISSING_REFRESH_MESSAGE",
  "AuthorizeRequest",
  "OpenAIOAuthCredentials",
  "OpenAIOAuthError",
  "OpenAIOAuthManager",
  "OpenAIOAuthManagerProtocol",
  "OpenAIOAuthModelConfig",
  "OpenAIOAuthModelProvider",
  "OpenAIOAuthModelSettings",
  "OpenAIOAuthProtocolError",
  "OpenAIOAuthReauthRequiredError",
  "OpenAIOAuthStateMismatchError",
  "OpenAIOAuthStore",
  "OpenAIOAuthStoreCorruptionError",
  "OpenAIOAuthStoreError",
  "OpenAIProviderError",
  "OpenAITokenResponse",
  "RefreshTokenRequest",
  "TokenExchangeRequest",
  "add_base64_padding",
  "build_authorize_url",
  "build_chatgpt_oauth_client",
  "build_pkce_verifier_and_challenge",
  "decode_jwt_payload",
  "default_openai_oauth_credentials_path",
  "exchange_authorization_code",
  "extract_account_id_from_id_token",
  "generate_oauth_state",
  "oauth_responses_settings",
  "refresh_access_token",
  "validate_oauth_state",
]
