"""OpenAI-specific provider configuration and model settings."""

from typing import ClassVar, Literal

from pydantic import ConfigDict, Field
from pydantic_ai.models.openai import OpenAIResponsesModelSettings

from operator_core_olden.providers.types import ModelConfig, ModelSettings


class OpenAIModelSettings(ModelSettings):
    """Serializable OpenAI model settings payload."""

    model_config: ClassVar[ConfigDict] = ConfigDict(extra="forbid")

    openai_store: bool | None = None
    openai_send_reasoning_ids: bool | None = None
    openai_previous_response_id: str | None = None

    def to_model_settings(self, *, temperature: float) -> OpenAIResponsesModelSettings:
        """Convert validated OpenAI settings into pydantic-ai settings."""
        model_settings = OpenAIResponsesModelSettings(temperature=temperature)

        if self.openai_store:
            model_settings["openai_store"] = self.openai_store
        if self.openai_send_reasoning_ids:
            model_settings["openai_send_reasoning_ids"] = self.openai_send_reasoning_ids
        if self.openai_previous_response_id:
            model_settings["openai_previous_response_id"] = self.openai_previous_response_id

        return model_settings


class DirectOpenAIModelConfig(ModelConfig[OpenAIModelSettings]):
    """Serializable OpenAI model configuration."""

    provider: Literal["openai"] = "openai"
    settings: OpenAIModelSettings = Field(default_factory=OpenAIModelSettings)


__all__ = ["DirectOpenAIModelConfig", "OpenAIModelSettings"]
