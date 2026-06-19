"""Transient agent stream events for UI consumers."""

from attrs import define

from operator_shared.event_sink import EventSink


@define(frozen=True, kw_only=True)
class StreamPartStarted:
    """A streamed model response part started."""

    part_index: int
    part_kind: str


@define(frozen=True, kw_only=True)
class StreamTextDelta:
    """A transient streamed assistant text delta."""

    part_index: int
    content_delta: str


@define(frozen=True, kw_only=True)
class StreamThinkingDelta:
    """A transient streamed assistant thinking delta."""

    part_index: int
    content_delta: str


@define(frozen=True, kw_only=True)
class StreamPartFinished:
    """A streamed model response part finished."""

    part_index: int
    part_kind: str


@define(frozen=True, kw_only=True)
class StreamToolCallStarted:
    """A function tool call started during a streamed turn."""

    tool_call_id: str
    tool_name: str
    args: str | None = None


@define(frozen=True, kw_only=True)
class StreamToolCallFinished:
    """A function tool call finished during a streamed turn."""

    tool_call_id: str
    tool_name: str | None
    outcome: str
    result: str | None = None


type AgentStreamEvent = (
    StreamPartStarted
    | StreamTextDelta
    | StreamThinkingDelta
    | StreamPartFinished
    | StreamToolCallStarted
    | StreamToolCallFinished
)


type AgentStreamSink = EventSink[AgentStreamEvent]


__all__ = [
    "AgentStreamEvent",
    "AgentStreamSink",
    "StreamPartFinished",
    "StreamPartStarted",
    "StreamTextDelta",
    "StreamThinkingDelta",
    "StreamToolCallFinished",
    "StreamToolCallStarted",
]
