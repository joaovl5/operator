"""Provider-agnostic interfaces for model integrations."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pydantic_ai.models import Model


class ModelProvider[ConfigT](ABC):
    """Represents provider config that builds pydantic-ai models."""

    @abstractmethod
    def build_model(self, *, model_config: ConfigT) -> Model:
        """Build a pydantic-ai model instance from the provider."""
