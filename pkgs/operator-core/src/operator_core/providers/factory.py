"""Runtime provider factory helpers."""

from typing import TYPE_CHECKING

from operator_core.config import OpenAIOAuthRuntimeModelConfig, OperatorModelConfig
from operator_core.providers.openai import OpenAIOAuthModelProvider, OpenAIOAuthStore
from operator_core.providers.zai import ZAIModelConfig, ZAIModelProvider, get_zai_client

if TYPE_CHECKING:
    from pydantic_ai.models import Model


def build_model_from_config(*, config: OperatorModelConfig) -> Model:
    """Build a pydantic-ai model from injected runtime config."""
    match config:
        case OpenAIOAuthRuntimeModelConfig():
            provider = OpenAIOAuthModelProvider(store=OpenAIOAuthStore())
            return provider.build_model(model_config=config.to_openai_oauth_config())
        case ZAIModelConfig():
            provider = ZAIModelProvider(
                openai_client=get_zai_client(
                    api_key=config.api_key.get_secret_value(),
                    base_url=config.base_url,
                ),
            )
            return provider.build_model(model_config=config)
