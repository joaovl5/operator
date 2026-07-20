"""OpenAI OAuth-backed model provider."""

from typing import TYPE_CHECKING, override

from attrs import define, field
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from operator_core_olden.providers import ModelProvider

from .chatgpt import build_chatgpt_oauth_client
from .manager import OpenAIOAuthManager
from .settings import OpenAIOAuthModelConfig

if TYPE_CHECKING:
  from openai import AsyncOpenAI
  from pydantic_ai.models import Model

  from .store import OpenAIOAuthStore


@define(kw_only=True)
class OpenAIOAuthModelProvider(ModelProvider[OpenAIOAuthModelConfig]):
  """OAuth-backed OpenAI provider using responses models by
  default."""

  store: OpenAIOAuthStore
  _oauth_manager: OpenAIOAuthManager | None = field(
    init=False, default=None
  )
  _oauth_client: AsyncOpenAI | None = field(init=False, default=None)
  _oauth_provider: OpenAIProvider | None = field(
    init=False, default=None
  )

  def get_openai_client(self) -> AsyncOpenAI:
    """Return the cached OAuth OpenAI client."""
    client = self._oauth_client
    if client is None:
      client = build_chatgpt_oauth_client(manager=self.oauth_manager)
      self._oauth_client = client
    return client

  @property
  def oauth_manager(self) -> OpenAIOAuthManager:
    """Return the lazily-created OAuth manager for this provider."""
    manager = self._oauth_manager
    if manager is None:
      manager = OpenAIOAuthManager(store=self.store)
      self._oauth_manager = manager
    return manager

  def build_provider(self) -> OpenAIProvider:
    """Return the cached provider wrapper for the OAuth client."""
    provider = self._oauth_provider
    if provider is None:
      provider = OpenAIProvider(
        openai_client=self.get_openai_client()
      )
      self._oauth_provider = provider
    return provider

  @override
  def build_model(
    self, *, model_config: OpenAIOAuthModelConfig
  ) -> Model:
    """Build a validated OAuth-backed responses model."""
    return OpenAIResponsesModel(
      model_name=model_config.name,
      provider=self.build_provider(),
      settings=model_config.settings.to_model_settings(
        temperature=model_config.temperature
      ),
    )


__all__ = ["OpenAIOAuthModelProvider"]
