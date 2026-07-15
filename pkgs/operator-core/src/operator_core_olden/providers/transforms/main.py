"""Provider message transform interfaces."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
  from collections.abc import Sequence

  from operator_shared.providers.transforms import OperatorMessage


class ProviderMessageTransform[ProviderMessageT](ABC):
  """Translate between stable Operator DTOs and provider-native messages."""

  @abstractmethod
  def to_provider_message(
    self, *, message: OperatorMessage
  ) -> ProviderMessageT:
    """Convert one stable Operator message to a provider-native message."""

  @abstractmethod
  def from_provider_message(
    self, *, message: ProviderMessageT
  ) -> OperatorMessage:
    """Convert one provider-native message to a stable Operator message."""

  def to_provider_messages(
    self,
    *,
    messages: Sequence[OperatorMessage],
  ) -> list[ProviderMessageT]:
    """Convert stable Operator messages to provider-native messages."""
    return [
      self.to_provider_message(message=message)
      for message in messages
    ]

  def from_provider_messages(
    self,
    *,
    messages: Sequence[ProviderMessageT],
  ) -> list[OperatorMessage]:
    """Convert provider-native messages to stable Operator messages."""
    return [
      self.from_provider_message(message=message)
      for message in messages
    ]


__all__ = ["ProviderMessageTransform"]
