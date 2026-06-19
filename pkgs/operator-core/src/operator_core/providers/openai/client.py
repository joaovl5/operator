"""OpenAI client construction and non-OAuth provider helpers."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, override

from attrs import define
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from operator_core.providers import ModelProvider

from .types import DirectOpenAIModelConfig

if TYPE_CHECKING:
    from pydantic_ai import ModelSettings
    from pydantic_ai.models import Model


def get_openai_client(*, api_key: str | None, base_url: str | None) -> AsyncOpenAI:
    """Create an OpenAI client."""
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


@define
class BaseOpenAIModelProvider(ModelProvider[DirectOpenAIModelConfig], ABC):
    """Shared OpenAI provider behavior."""

    @abstractmethod
    def get_openai_client(self) -> AsyncOpenAI:
        """Return the OpenAI client used to build a provider."""

    def build_provider(self) -> OpenAIProvider:
        """Build the shared pydantic-ai provider wrapper."""
        return OpenAIProvider(openai_client=self.get_openai_client())

    def build_model_settings(self, *, model_config: DirectOpenAIModelConfig) -> ModelSettings:
        """Build the model settings payload from the validated config."""
        return model_config.settings.to_model_settings(temperature=model_config.temperature)


@define(kw_only=True)
class OpenAIModelProvider(BaseOpenAIModelProvider):
    """Plain OpenAI platform provider."""

    openai_client: AsyncOpenAI

    @override
    def get_openai_client(self) -> AsyncOpenAI:
        """Return the configured OpenAI client."""
        return self.openai_client

    @override
    def build_model(self, *, model_config: DirectOpenAIModelConfig) -> Model:
        """Build a chat model for the configured OpenAI client."""
        return OpenAIChatModel(
            model_name=model_config.name,
            provider=self.build_provider(),
            settings=self.build_model_settings(model_config=model_config),
        )


__all__ = [
    "BaseOpenAIModelProvider",
    "OpenAIModelProvider",
    "get_openai_client",
]
