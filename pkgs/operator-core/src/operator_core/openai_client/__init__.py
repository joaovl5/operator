"""Authenticated OpenAI client helpers for ChatGPT OAuth traffic."""

from .errors import (
    OpenAIOAuthModelConstraintError,
    OpenAIOAuthSettingsConstraintError,
    OpenAIProviderError,
)
from .main import (
    CHATGPT_CODEX_BASE_URL,
    DEFAULT_REFRESH_BUFFER_MS,
    MISSING_CREDENTIALS_MESSAGE,
    OPERATOR_ORIGINATOR,
    REFRESH_REJECTED_MESSAGE,
    REMOVED_CREDENTIALS_MESSAGE,
    OpenAIOAuthManager,
    build_chatgpt_oauth_client,
    oauth_responses_settings,
)
from .types import OAuthResponsesSettings

__all__ = [
    "CHATGPT_CODEX_BASE_URL",
    "DEFAULT_REFRESH_BUFFER_MS",
    "MISSING_CREDENTIALS_MESSAGE",
    "OPERATOR_ORIGINATOR",
    "REFRESH_REJECTED_MESSAGE",
    "REMOVED_CREDENTIALS_MESSAGE",
    "OAuthResponsesSettings",
    "OpenAIOAuthManager",
    "OpenAIOAuthModelConstraintError",
    "OpenAIOAuthSettingsConstraintError",
    "OpenAIProviderError",
    "build_chatgpt_oauth_client",
    "oauth_responses_settings",
]
