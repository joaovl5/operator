from abc import ABC

from operator_prompts.loaders.base import PromptLoaderRequest, PromptLoaderResponse


class OpTemplatePromptLoader(ABC):
    """Loader for prompts for OpTemplate."""

    async def load_prompt(self, *, req: PromptLoaderRequest) -> PromptLoaderResponse:
        """Load an OpTemplate file."""
