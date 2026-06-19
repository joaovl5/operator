from asyncio import Lock
from functools import partial
from typing import TYPE_CHECKING

from attrs import Factory, define, field
from pydantic_ai import Agent

from operator_core.providers.transforms import (
    HistoryMessageTransform,
    PydanticAIMessageTransform,
    PydanticAIStreamTransform,
)
from operator_shared.providers.transforms import (
    OperatorMessage,
    OperatorRequestMessage,
    OperatorSystemPromptPart,
    OperatorUserPromptPart,
)

if TYPE_CHECKING:
    from collections.abc import AsyncIterable, Sequence

    from pydantic_ai import AgentStreamEvent
    from pydantic_ai.models import Model

    from operator_core.agent.streaming import AgentStreamSink
    from operator_core.permissions import PermissionGroup
    from operator_core.toolsets.base import ToolsetPydanticExport
    from operator_db.objects.history.schema import (
        HistoryMessageRequestSchema,
        HistoryMessageResponseSchema,
    )


type _PromptPart = OperatorSystemPromptPart | OperatorUserPromptPart
type _PromptPartKey = tuple[str, str, str | None]


async def _forward_streaming_events(
    _run_context: object,
    events: AsyncIterable[AgentStreamEvent],
    *,
    stream_transform: PydanticAIStreamTransform,
    sink: AgentStreamSink,
) -> None:
    await stream_transform.forward_events(events=events, sink=sink)


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
    stream_transform: PydanticAIStreamTransform = Factory(PydanticAIStreamTransform)

    def __attrs_post_init__(self) -> None:
        """Initialize internal pydantic-ai agent."""
        self.agent = Agent(
            model=self.model,
            name=self.id,
        )

    def register_toolsets(
        self,
        tools: ToolsetPydanticExport,
    ) -> None:
        """Register toolsets to agent."""
        _ = [self.agent.tool_plain(tool) for tool in tools]

    async def run(
        self,
        *,
        messages: Sequence[HistoryMessageResponseSchema] = (),
        stream_sink: AgentStreamSink | None = None,
    ) -> list[HistoryMessageRequestSchema]:
        """Run a turn with persisted message history."""
        # we use pydantic_ai transforms to keep intermediary types (publicly-exposed)
        # generic, if/when we change LLM backend it doesnt screw up db data
        operator_messages = self.history_transform.to_operator_messages(messages=messages)
        message_history = self.pydantic_ai_transform.to_provider_messages(
            messages=operator_messages,
        )
        if stream_sink is None:
            # if we're not listening to them, we don't care about streaming events,
            # so we just run request plainly
            agent_result = await self.agent.run(message_history=message_history)
        else:
            # otherwise, we emit streaming events
            event_stream_handler = partial(
                _forward_streaming_events,
                stream_transform=self.stream_transform,
                sink=stream_sink,
            )

            agent_result = await self.agent.run(
                message_history=message_history,
                event_stream_handler=event_stream_handler,
            )
        new_messages = self.pydantic_ai_transform.from_provider_messages(
            messages=agent_result.new_messages(),
        )
        # deduplicate returning messages that were already present at request time
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

    candidate_prompt_parts = _prompt_parts_from_request(message=candidate_message)
    if candidate_prompt_parts is None:
        return False

    previous_prompt_parts: list[_PromptPart] = []
    for message in previous_messages:
        if not isinstance(message, OperatorRequestMessage):
            continue
        previous_prompt_parts.extend(
            part
            for part in message.parts
            if isinstance(part, OperatorSystemPromptPart | OperatorUserPromptPart)
        )

    part_count = len(candidate_prompt_parts)
    return _prompt_part_keys(parts=previous_prompt_parts[-part_count:]) == _prompt_part_keys(
        parts=candidate_prompt_parts,
    )


def _prompt_parts_from_request(*, message: OperatorRequestMessage) -> list[_PromptPart] | None:
    prompt_parts: list[_PromptPart] = []
    for part in message.parts:
        if not isinstance(part, OperatorSystemPromptPart | OperatorUserPromptPart):
            return None
        prompt_parts.append(part)
    return prompt_parts


def _prompt_part_keys(*, parts: Sequence[_PromptPart]) -> list[_PromptPartKey]:
    return [_prompt_part_key(part=part) for part in parts]


def _prompt_part_key(*, part: _PromptPart) -> _PromptPartKey:
    match part:
        case OperatorSystemPromptPart():
            return (part.part_kind, part.content, part.dynamic_ref)
        case OperatorUserPromptPart():
            return (part.part_kind, part.content, None)
