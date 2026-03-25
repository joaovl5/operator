"""OpenAI OAuth error hierarchy."""


class OpenAIOAuthError(RuntimeError):
    """Base OAuth error for Operator-owned OpenAI auth helpers."""


class OpenAIOAuthReauthRequiredError(OpenAIOAuthError):
    """Raised when stored credentials are no longer usable and login is required."""


class OpenAIOAuthProtocolError(OpenAIOAuthError):
    """Raised when the OAuth endpoints return an unexpected response."""


class OpenAIOAuthStateMismatchError(OpenAIOAuthError):
    """Raised when an OAuth callback returns an unexpected state value."""
