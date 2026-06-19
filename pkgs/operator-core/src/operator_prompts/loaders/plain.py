"""Plain file prompt loading logic."""

from operator_prompts.loaders.base import (
    BasePromptLoader,
    PromptLoaderRequest,
    PromptLoaderResponse,
)


class PlainFilePromptLoader(BasePromptLoader):
    """Loads plain files as prompts without preprocessing."""

    async def load_prompt(self, *, req: PromptLoaderRequest) -> PromptLoaderResponse:
        """Load a file file."""
