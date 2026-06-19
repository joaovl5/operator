"""Shared Operator settings models and loaders."""

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import quote

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .utils import default_config_path, load_optional_toml

if TYPE_CHECKING:
    from .types import OperatorSettingsPath, OperatorSettingsSource


DEFAULT_CALLBACK_BIND_HOST = "localhost"
DEFAULT_CALLBACK_PORT = 1455
DEFAULT_CALLBACK_PATH = "/auth/callback"


class CallbackSettings(BaseModel):
    """OAuth callback settings for the local browser login flow."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    port: int = Field(default=DEFAULT_CALLBACK_PORT, ge=1, le=65_535)
    path: str = DEFAULT_CALLBACK_PATH

    @field_validator("path")
    @classmethod
    def validate_path(cls, value: str) -> str:
        """Require an absolute URI-safe callback path without query or fragment components."""
        if not value.startswith("/") or "?" in value or "#" in value or quote(value, safe="/") != value:
            message = "callback path must be absolute, URI-safe, and exclude query/fragment components"
            raise ValueError(message)
        return value

    def redirect_uri(self) -> str:
        """Return the browser redirect URI for this callback configuration."""
        return f"http://{DEFAULT_CALLBACK_BIND_HOST}:{self.port}{self.path}"


class OAuthSettings(BaseModel):
    """OAuth runtime settings shared across Operator packages."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    callback: CallbackSettings = Field(default_factory=CallbackSettings)


class OperatorSettings(BaseModel):
    """Top-level settings loaded from the canonical `config.toml` file."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    oauth: OAuthSettings = Field(default_factory=OAuthSettings)


def load_operator_settings(*, path: OperatorSettingsPath | None = None) -> OperatorSettings:
    """Load `config.toml` when present and validate it as `OperatorSettings`."""
    settings_path = default_config_path() if path is None else Path(path)
    document = load_optional_toml(path=settings_path)
    return OperatorSettings.model_validate(_shared_settings_document(document))


def _shared_settings_document(document: OperatorSettingsSource) -> dict[str, object]:
    oauth = document.get("oauth")
    return {"oauth": oauth} if oauth   else {}
