"""Errors for OpenAI client and provider integration."""


class OpenAIProviderError(ValueError):
    """Base error for OpenAI model provider validation."""


class OpenAIOAuthModelConstraintError(OpenAIProviderError):
    """Raised when an OAuth provider receives an unsupported model name."""


class OpenAIOAuthSettingsConstraintError(OpenAIProviderError):
    """Raised when an OAuth provider receives unsupported response settings."""
