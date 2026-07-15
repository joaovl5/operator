"""OAuth-backed OpenAI model settings and config."""

from typing import ClassVar, Literal

from pydantic import ConfigDict, Field, field_validator
from pydantic_ai.models.openai import OpenAIResponsesModelSettings

from operator_core_olden.providers.types import (
  ModelConfig,
  ModelSettings,
)


class OpenAIOAuthModelSettings(ModelSettings):
  """OAuth-safe OpenAI model settings payload."""

  model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

  openai_store: Literal[False] = False
  openai_send_reasoning_ids: Literal[False] = False

  def to_model_settings(
    self, *, temperature: float
  ) -> OpenAIResponsesModelSettings:
    """Convert OAuth-safe settings into pydantic-ai settings."""
    model_settings = OpenAIResponsesModelSettings(
      temperature=temperature
    )
    model_settings["openai_store"] = self.openai_store
    model_settings["openai_send_reasoning_ids"] = (
      self.openai_send_reasoning_ids
    )
    return model_settings


class OpenAIOAuthModelConfig(ModelConfig[OpenAIOAuthModelSettings]):
  """Validated OAuth-backed model configuration."""

  name: str
  settings: OpenAIOAuthModelSettings = Field(
    default_factory=OpenAIOAuthModelSettings
  )

  @field_validator("name")
  @classmethod
  def validate_name(cls, value: str) -> str:
    """Validate that the OAuth-backed model name stays on the supported codex model."""
    if value != "gpt-5.3-codex":
      message = f"Unsupported model name: {value}"
      raise ValueError(message)
    return value


def oauth_responses_settings() -> OpenAIOAuthModelSettings:
  """Return stateless OAuth-safe Responses defaults."""
  return OpenAIOAuthModelSettings()


__all__ = [
  "OpenAIOAuthModelConfig",
  "OpenAIOAuthModelSettings",
  "oauth_responses_settings",
]
