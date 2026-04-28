"""Runtime configuration models and loader for operator-core."""

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

from operator_core.providers.openai.oauth import OpenAIOAuthModelConfig, OpenAIOAuthModelSettings
from operator_core.providers.zai import ZAIModelConfig
from operator_shared.settings import OAuthSettings
from operator_shared.settings.utils import default_config_path, load_optional_toml

if TYPE_CHECKING:
    from operator_shared.settings.types import OperatorSettingsPath

DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///.operator/operator.sqlite3"
DEFAULT_OPERATOR_SYSTEM_PROMPT = "You're a helpful assistant."
DEFAULT_ORCHESTRATOR_MODEL = "gpt-5.3-codex"


class DatabaseConfig(BaseModel):
    """Database connection settings."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    url: str = DEFAULT_DATABASE_URL


class AgentConfig(BaseModel):
    """Default orchestrator-agent settings."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    system_prompt: str = ""


class OpenAIOAuthRuntimeModelConfig(BaseModel):
    """Runtime OpenAI OAuth model selection settings."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    provider: Literal["openai-oauth"] = "openai-oauth"
    name: str = DEFAULT_ORCHESTRATOR_MODEL
    temperature: float = 0.1
    settings: OpenAIOAuthModelSettings = Field(default_factory=OpenAIOAuthModelSettings)

    def to_openai_oauth_config(self) -> OpenAIOAuthModelConfig:
        """Convert runtime model config into the OpenAI OAuth provider config."""
        return OpenAIOAuthModelConfig(
            name=self.name,
            temperature=self.temperature,
            settings=self.settings,
        )


type OperatorModelConfig = Annotated[
    OpenAIOAuthRuntimeModelConfig | ZAIModelConfig,
    Field(discriminator="provider"),
]


class OperatorConfig(BaseModel):
    """Top-level operator-core runtime configuration."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    agent: AgentConfig = Field(default_factory=AgentConfig)
    model: OperatorModelConfig = Field(default_factory=OpenAIOAuthRuntimeModelConfig)
    oauth: OAuthSettings = Field(default_factory=OAuthSettings)


def get_config(*, path: OperatorSettingsPath | None = None) -> OperatorConfig:
    """Load `config.toml` when present and validate it as `OperatorConfig`."""
    config_path = default_config_path() if path is None else Path(path)
    document = load_optional_toml(path=config_path)
    return OperatorConfig.model_validate(document)


__all__ = [
    "DEFAULT_DATABASE_URL",
    "DEFAULT_OPERATOR_SYSTEM_PROMPT",
    "DEFAULT_ORCHESTRATOR_MODEL",
    "AgentConfig",
    "DatabaseConfig",
    "OpenAIOAuthRuntimeModelConfig",
    "OperatorConfig",
    "OperatorModelConfig",
    "get_config",
]
