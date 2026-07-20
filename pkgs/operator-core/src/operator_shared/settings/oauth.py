from urllib.parse import quote

from pydantic import Field, ValidationError, field_validator

from operator_shared.settings.types import Fac, SettingsBase

DEFAULT_CALLBACK_BIND_HOST = "127.0.0.1"
DEFAULT_CALLBACK_PORT = 10459
DEFAULT_CALLBACK_PATH = "/auth/callback"


class _OAuthCallbackSettings(SettingsBase):
  """OAuth callback settings for the local browser login flow."""

  port: int = Field(default=DEFAULT_CALLBACK_PORT, ge=1, le=65_535)
  path: str = DEFAULT_CALLBACK_PATH

  @field_validator("path")
  @classmethod
  def validate_path(cls, value: str) -> str:
    """Require an absolute URI-safe callback path without query or
    fragment components."""
    if (
      not value.startswith("/")
      or "?" in value
      or "#" in value
      or quote(value, safe="/") != value
    ):
      message = (
        "callback path must be absolute, URI-safe, and exclude "
        "query/fragment components"
      )
      raise ValidationError(message)
    return value

  def redirect_uri(self) -> str:
    """Return the browser redirect URI for this callback
    configuration."""
    return (
      f"http://{DEFAULT_CALLBACK_BIND_HOST}:{self.port}{self.path}"
    )


class OAuthSettings(SettingsBase):
  """OAuth runtime settings shared across Operator packages."""

  callback: Fac[_OAuthCallbackSettings]
