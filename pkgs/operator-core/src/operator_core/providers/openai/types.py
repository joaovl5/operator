"""OpenAI-specific provider configuration and model settings."""

from typing import ClassVar

from pydantic import ConfigDict, Field
from pydantic_ai.models.openai import OpenAIResponsesModelSettings

from operator_core.providers.types import ModelConfig, ModelSettings


class OpenAIModelSettings(ModelSettings):
    """Serializable OpenAI model settings payload."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    openai_store: bool | None = None
    openai_send_reasoning_ids: bool | None = None
    openai_previous_response_id: str | None = None

    def to_model_settings(self, *, temperature: float) -> OpenAIResponsesModelSettings:
        """Convert validated OpenAI settings into pydantic-ai settings."""
        model_settings = OpenAIResponsesModelSettings(temperature=temperature)

        if self.openai_store is not None:
            model_settings["openai_store"] = self.openai_store
        if self.openai_send_reasoning_ids is not None:
            model_settings["openai_send_reasoning_ids"] = self.openai_send_reasoning_ids
        if self.openai_previous_response_id is not None:
            model_settings["openai_previous_response_id"] = self.openai_previous_response_id

        return model_settings


class OpenAIModelConfig(ModelConfig[OpenAIModelSettings]):
    """Serializable OpenAI model configuration."""

    settings: OpenAIModelSettings = Field(default_factory=OpenAIModelSettings)


__all__ = ["OpenAIModelConfig", "OpenAIModelSettings"]
