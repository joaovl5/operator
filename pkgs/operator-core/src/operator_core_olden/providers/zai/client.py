"""Z.AI OpenAI-compatible provider helpers."""

from typing import TYPE_CHECKING, override

from attrs import define
from openai import AsyncOpenAI
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from operator_core_olden.providers import ModelProvider

from .types import ZAIModelConfig

if TYPE_CHECKING:
    from pydantic_ai.models import Model


def get_zai_client(*, api_key: str, base_url: str) -> AsyncOpenAI:
    """Create an OpenAI-compatible Z.AI client."""
    return AsyncOpenAI(api_key=api_key, base_url=base_url)


@define(kw_only=True)
class ZAIModelProvider(ModelProvider[ZAIModelConfig]):
    """Z.AI provider using the OpenAI-compatible chat API."""

    openai_client: AsyncOpenAI

    def build_provider(self) -> OpenAIProvider:
        """Build the pydantic-ai provider wrapper."""
        return OpenAIProvider(openai_client=self.openai_client)

    @override
    def build_model(self, *, model_config: ZAIModelConfig) -> Model:
        """Build a chat model for the configured Z.AI client."""
        return OpenAIChatModel(
            model_name=model_config.name,
            provider=self.build_provider(),
            settings=model_config.settings.to_model_settings(
                temperature=model_config.temperature,
            ),
        )


__all__ = ["ZAIModelProvider", "get_zai_client"]
