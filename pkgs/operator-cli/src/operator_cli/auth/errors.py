"""Errors raised by the CLI OpenAI auth flow."""


class OpenAIAuthCliError(RuntimeError):
  """Base error for CLI-facing OpenAI auth failures."""


class CallbackParseError(ValueError, OpenAIAuthCliError):
  """Raised when a pasted callback URL cannot be parsed safely."""


class CallbackStateMismatchError(OpenAIAuthCliError):
  """Raised when an OAuth callback returns an unexpected state value."""


class CallbackListenerTimeoutError(TimeoutError, OpenAIAuthCliError):
  """Raised when no valid OAuth callback is received before the deadline."""
