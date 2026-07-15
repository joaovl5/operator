"""Z.AI provider configuration and model settings."""

from typing import ClassVar, Literal

from pydantic import ConfigDict, Field, SecretStr
from pydantic_ai.models.openai import OpenAIChatModelSettings

from operator_core_olden.providers.types import (
  ModelConfig,
  ModelSettings,
)

ZAI_CODING_BASE_URL = "https://api.z.ai/api/coding/paas/v4/"
ZAI_GENERAL_BASE_URL = "https://api.z.ai/api/paas/v4/"
ZAI_DEFAULT_MODEL = "GLM-4.7"


class ZAIModelSettings(ModelSettings):
  """Serializable Z.AI chat-completions settings payload."""

  model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

  def to_model_settings(
    self, *, temperature: float
  ) -> OpenAIChatModelSettings:
    """Convert validated Z.AI settings into pydantic-ai settings."""
    return OpenAIChatModelSettings(temperature=temperature)


class ZAIModelConfig(ModelConfig[ZAIModelSettings]):
  """Validated Z.AI OpenAI-compatible model configuration."""

  provider: Literal["zai"] = "zai"
  name: str = ZAI_DEFAULT_MODEL
  temperature: float = Field(default=0.1, gt=0, le=1)
  api_key: SecretStr
  base_url: str = ZAI_CODING_BASE_URL
  settings: ZAIModelSettings = Field(default_factory=ZAIModelSettings)


__all__ = [
  "ZAI_CODING_BASE_URL",
  "ZAI_DEFAULT_MODEL",
  "ZAI_GENERAL_BASE_URL",
  "ZAIModelConfig",
  "ZAIModelSettings",
]
