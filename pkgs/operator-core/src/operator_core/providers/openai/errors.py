"""OpenAI provider package errors."""

from operator_core.providers.errors import ProviderError
from operator_core.providers.utils.store.errors import JsonCredentialStoreCorruptionError


class OpenAIProviderError(ProviderError):
    """Base error for OpenAI provider operations."""


class OpenAIOAuthModelConstraintError(OpenAIProviderError):
    """Raised when an OAuth provider receives an unsupported model name."""


class OpenAIOAuthSettingsConstraintError(OpenAIProviderError):
    """Raised when an OAuth provider receives unsupported response settings."""


class OpenAIOAuthStoreError(RuntimeError):
    """Base OpenAI OAuth store error."""


class OpenAIOAuthStoreCorruptionError(
    OpenAIOAuthStoreError,
    JsonCredentialStoreCorruptionError,
):
    """Raised when stored OpenAI OAuth credentials cannot be decoded."""


class OpenAIOAuthError(RuntimeError):
    """Base OAuth error for Operator-owned OpenAI auth helpers."""


class OpenAIOAuthReauthRequiredError(OpenAIOAuthError):
    """Raised when stored credentials are no longer usable and login is required."""


class OpenAIOAuthProtocolError(OpenAIOAuthError):
    """Raised when the OAuth endpoints return an unexpected response."""


class OpenAIOAuthStateMismatchError(OpenAIOAuthError):
    """Raised when an OAuth callback returns an unexpected state value."""


__all__ = [
    "OpenAIOAuthError",
    "OpenAIOAuthModelConstraintError",
    "OpenAIOAuthProtocolError",
    "OpenAIOAuthReauthRequiredError",
    "OpenAIOAuthSettingsConstraintError",
    "OpenAIOAuthStateMismatchError",
    "OpenAIOAuthStoreCorruptionError",
    "OpenAIOAuthStoreError",
    "OpenAIProviderError",
]
