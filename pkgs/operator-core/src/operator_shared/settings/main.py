"""Shared Operator settings models and loaders."""

from pathlib import Path
from typing import TYPE_CHECKING, ClassVar

from pydantic import BaseModel, ConfigDict, Field

from .utils import default_operator_settings_path, load_optional_toml

if TYPE_CHECKING:
    from .types import OperatorSettingsPath


DEFAULT_CALLBACK_HOST = "127.0.0.1"
DEFAULT_CALLBACK_PORT = 1455
DEFAULT_CALLBACK_PATH = "/auth/callback"
DEFAULT_CALLBACK_HOST_URI = "localhost"
DEFAULT_REFRESH_BUFFER_MS = 60_000


class CallbackSettings(BaseModel):
    """OAuth callback settings for the local browser login flow."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    host: str = DEFAULT_CALLBACK_HOST
    port: int = DEFAULT_CALLBACK_PORT
    path: str = DEFAULT_CALLBACK_PATH
    host_uri: str = DEFAULT_CALLBACK_HOST_URI

    def redirect_uri(self) -> str:
        """Return the browser redirect URI for this callback configuration."""
        return f"http://{self.host_uri}:{self.port}{self.path}"


class OAuthSettings(BaseModel):
    """OAuth runtime settings shared across Operator packages."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    refresh_buffer_ms: int = DEFAULT_REFRESH_BUFFER_MS
    callback: CallbackSettings = Field(default_factory=CallbackSettings)


class OperatorSettings(BaseModel):
    """Top-level settings loaded from the canonical `operator.toml` file."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    oauth: OAuthSettings = Field(default_factory=OAuthSettings)


def load_operator_settings(*, path: OperatorSettingsPath | None = None) -> OperatorSettings:
    """Load `operator.toml` when present and validate it as `OperatorSettings`."""
    settings_path = default_operator_settings_path() if path is None else Path(path)
    document = load_optional_toml(path=settings_path)
    return OperatorSettings.model_validate(document)
