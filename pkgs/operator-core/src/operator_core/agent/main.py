from asyncio import Lock
from typing import TYPE_CHECKING

from attrs import Factory, define, field
from pydantic_ai import Agent

from operator_core.providers.transforms import (
    HistoryMessageTransform,
    PydanticAIMessageTransform,
)
from operator_core.toolsets.main import file_read, file_search, file_write
from operator_shared.providers.transforms import (
    OperatorMessage,
    OperatorRequestMessage,
    OperatorSystemPromptPart,
    OperatorUserPromptPart,
)

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic_ai.models import Model

    from operator_core.permissions import PermissionGroup
    from operator_db.objects.history.schema import (
        HistoryMessageRequestSchema,
        HistoryMessageResponseSchema,
    )


@define(kw_only=True)
class OpAgent:
    """Runtime agent wrapper around pydantic-ai."""

    id: str
    model: Model
    system_prompt: str
    permissions: PermissionGroup
    history_id: str | None = None
    lock: Lock = Factory(Lock)
    agent: Agent = field(init=False)
    pydantic_ai_transform: PydanticAIMessageTransform = Factory(PydanticAIMessageTransform)
    history_transform: HistoryMessageTransform = Factory(HistoryMessageTransform)

    def __attrs_post_init__(self) -> None:
        """Initialize internal pydantic-ai agent."""
        self.agent = Agent(
            model=self.model,
            name=self.id,
            tools=(file_read, file_write, file_search),
        )

    async def run(
        self,
        *,
        messages: Sequence[HistoryMessageResponseSchema] = (),
    ) -> list[HistoryMessageRequestSchema]:
        """Run a turn with persisted message history."""
        operator_messages = self.history_transform.to_operator_messages(messages=messages)
        message_history = self.pydantic_ai_transform.to_provider_messages(
            messages=operator_messages,
        )
        agent_result = await self.agent.run(message_history=message_history)
        new_messages = self.pydantic_ai_transform.from_provider_messages(
            messages=agent_result.new_messages(),
        )
        new_messages = _without_replayed_prefix(
            previous_messages=operator_messages,
            candidate_messages=new_messages,
        )
        return self.history_transform.to_history_requests(
            messages=new_messages,
            author_id=self.id,
        )


def _without_replayed_prefix(
    *,
    previous_messages: Sequence[OperatorMessage],
    candidate_messages: Sequence[OperatorMessage],
) -> list[OperatorMessage]:
    candidates = list(candidate_messages)
    previous = list(previous_messages)
    max_overlap = min(len(previous), len(candidates))
    for overlap in range(max_overlap, 0, -1):
        if previous[-overlap:] == candidates[:overlap]:
            candidates = candidates[overlap:]
            break

    while candidates and _is_replayed_prompt_request(
        previous_messages=previous,
        candidate_message=candidates[0],
    ):
        candidates = candidates[1:]

    return candidates


def _is_replayed_prompt_request(
    *,
    previous_messages: Sequence[OperatorMessage],
    candidate_message: OperatorMessage,
) -> bool:
    if not isinstance(candidate_message, OperatorRequestMessage):
        return False
    if not candidate_message.parts:
        return False
    if not all(
        isinstance(part, OperatorSystemPromptPart | OperatorUserPromptPart)
        for part in candidate_message.parts
    ):
        return False

    previous_prompt_parts = [
        part
        for message in previous_messages
        if isinstance(message, OperatorRequestMessage)
        for part in message.parts
        if isinstance(part, OperatorSystemPromptPart | OperatorUserPromptPart)
    ]
    part_count = len(candidate_message.parts)
    return previous_prompt_parts[-part_count:] == candidate_message.parts
