"""OpenAI OAuth store error hierarchy."""


class OpenAIOAuthStoreError(RuntimeError):
    """Base OpenAI OAuth store error."""


class OpenAIOAuthStoreCorruptionError(OpenAIOAuthStoreError):
    """Raised when the stored OpenAI OAuth credentials cannot be decoded."""
