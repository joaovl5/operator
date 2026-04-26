from asyncio import Lock
from typing import TYPE_CHECKING

from attrs import Factory, define, field
from pydantic_ai import Agent, ModelMessage, ModelRequest, ModelResponse, SystemPromptPart

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic_ai.models import Model

    from operator_core.mail.mail import RenderedMailMessage
    from operator_core.permissions import PermissionGroup


def _mail_to_model_message(self_id: str, rendered_mail: RenderedMailMessage) -> ModelMessage:
    if rendered_mail.author.id == self_id:
        return ModelResponse(
            parts=[rendered_mail.contents.body],
            timestamp=rendered_mail.time,
        )
    return ModelRequest(parts=[])


@define(kw_only=True)
class OpAgent:
    """Simple agent for testing."""

    id: str
    model: Model
    system_prompt: str
    permissions: PermissionGroup
    lock: Lock = Factory(Lock)
    agent: Agent = field(init=False)

    def __attrs_post_init__(self) -> None:
        """Initialize internal pydantic-ai agent."""
        self.agent = Agent(
            model=self.model,
        )

    async def run(self, rendered_mail: Sequence[RenderedMailMessage]) -> None:
        """Run a turn with agent."""
        model_msgs = [_mail_to_model_message(x) for x in rendered_mail]
        model_msgs = [
            ModelRequest(parts=[SystemPromptPart(content=self.system_prompt)]),
            *model_msgs,
        ]
