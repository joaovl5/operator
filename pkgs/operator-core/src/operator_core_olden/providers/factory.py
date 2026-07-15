"""Runtime provider factory helpers."""

from typing import TYPE_CHECKING

from operator_core_olden.config import (
  OpenAIOAuthRuntimeModelConfig,
  OperatorModelConfig,
)
from operator_core_olden.providers.generic.client import (
  GenericModelProvider,
  get_generic_client,
)
from operator_core_olden.providers.generic.types import (
  GenericModelConfig,
)
from operator_core_olden.providers.openai import (
  OpenAIOAuthModelProvider,
  OpenAIOAuthStore,
)
from operator_core_olden.providers.zai import (
  ZAIModelConfig,
  ZAIModelProvider,
  get_zai_client,
)

if TYPE_CHECKING:
  from pydantic_ai.models import Model


# TODO: refactor this bullshit
def build_model_from_config(*, config: OperatorModelConfig) -> Model:
  """Build a pydantic-ai model from injected runtime config."""
  match config:
    case OpenAIOAuthRuntimeModelConfig():
      provider = OpenAIOAuthModelProvider(store=OpenAIOAuthStore())
      return provider.build_model(
        model_config=config.to_openai_oauth_config()
      )
    case ZAIModelConfig():
      provider = ZAIModelProvider(
        openai_client=get_zai_client(
          api_key=config.api_key.get_secret_value(),
          base_url=config.base_url,
        )
      )

      return provider.build_model(model_config=config)
    case GenericModelConfig():
      return GenericModelProvider(
        openai_client=get_generic_client(
          api_key=config.api_key.get_secret_value(),
          base_url=config.base_url,
        ),
      ).build_model(model_config=config)
