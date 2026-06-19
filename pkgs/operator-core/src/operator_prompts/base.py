from abc import ABC, abstractmethod
from enum import StrEnum

from attrs import define


class PromptTrait(StrEnum):
    ROOT_PROMPT = "root-prompt"


@define
class BasePrompt(ABC):
    trait: str
    variation: str

    @abstractmethod
    def render() -> str:
        """Render prompt."""
