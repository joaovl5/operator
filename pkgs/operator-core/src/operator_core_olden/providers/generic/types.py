"""Z.AI provider configuration and model settings."""

from typing import ClassVar, Literal

from pydantic import ConfigDict, Field, SecretStr
from pydantic_ai.models.openai import OpenAIChatModelSettings

from operator_core_olden.providers.types import ModelConfig, ModelSettings


class GenericModelSettings(ModelSettings):
    """Serializable Z.AI chat-completions settings payload."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    def to_model_settings(self, *, temperature: float) -> OpenAIChatModelSettings:
        """Convert validated Z.AI settings into pydantic-ai settings."""
        return OpenAIChatModelSettings(temperature=temperature)


class GenericModelConfig(ModelConfig[GenericModelSettings]):
    """Validated Z.AI OpenAI-compatible model configuration."""

    provider: Literal["generic"] = "generic"
    name: str
    temperature: float = Field(default=0.1, gt=0, le=1)
    api_key: SecretStr
    base_url: str
    settings: GenericModelSettings = Field(
        default_factory=GenericModelSettings,
    )
