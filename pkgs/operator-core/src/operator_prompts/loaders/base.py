from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from attrs import define

if TYPE_CHECKING:
    import anyio


@define(frozen=True, kw_only=True)
class PromptLoaderRequest:
    """Generic request for loading a prompt file."""

    prompt_file: anyio.Path
    """Prompt file to be loaded, as an `anyio` Path."""

    prompt_context: dict[str, Any] | None = None
    """Extra context, if any, to be injected into prompt file.

    This will only be valid for PromptLoader implementations that support it.
    """


@define(frozen=True, kw_only=True)
class PromptLoaderResponse:
    """Generic response from a loaded prompt file."""

    prompt_text: str
    """Text of prompt."""


class BasePromptLoader(ABC):
    """Base class for loading prompts."""

    @abstractmethod
    async def load_prompt(self, *, req: PromptLoaderRequest) -> PromptLoaderResponse:
        """Load a prompt through a `PromptLoaderRequest`."""
