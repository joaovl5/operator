"""OpenAI provider package errors."""

from operator_core_olden.providers.errors import ProviderError
from operator_core_olden.providers.utils.store.errors import (
  JsonCredentialStoreCorruptionError,
)


class OpenAIProviderError(ProviderError):
  """Base error for OpenAI provider operations."""


class OpenAIOAuthError(RuntimeError):
  """Base OAuth error for Operator-owned OpenAI auth helpers."""


class OpenAIOAuthReauthRequiredError(OpenAIOAuthError):
  """Raised when stored credentials are no longer usable and login
  is required."""


class OpenAIOAuthProtocolError(OpenAIOAuthError):
  """Raised when the OAuth endpoints return an unexpected response."""


class OpenAIOAuthStateMismatchError(OpenAIOAuthError):
  """Raised when an OAuth callback returns an unexpected state
  value."""


class OpenAIOAuthStoreError(RuntimeError):
  """Base OpenAI OAuth store error."""


class OpenAIOAuthStoreCorruptionError(
  OpenAIOAuthStoreError,
  JsonCredentialStoreCorruptionError,
):
  """Raised when stored OpenAI OAuth credentials cannot be decoded."""


__all__ = [
  "OpenAIOAuthError",
  "OpenAIOAuthProtocolError",
  "OpenAIOAuthReauthRequiredError",
  "OpenAIOAuthStateMismatchError",
  "OpenAIOAuthStoreCorruptionError",
  "OpenAIOAuthStoreError",
  "OpenAIProviderError",
]
