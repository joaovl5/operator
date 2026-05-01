"""Transient agent stream events for UI consumers."""

from typing import Protocol

from attrs import define


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


@define(frozen=True, kw_only=True)
class StreamToolCallFinished:
    """A function tool call finished during a streamed turn."""

    tool_call_id: str
    tool_name: str | None
    outcome: str


type AgentStreamEvent = (
    StreamPartStarted
    | StreamTextDelta
    | StreamThinkingDelta
    | StreamPartFinished
    | StreamToolCallStarted
    | StreamToolCallFinished
)


class AgentStreamSink(Protocol):
    """Receives transient agent stream events."""

    async def __call__(self, *, event: AgentStreamEvent) -> None:
        """Handle one transient agent stream event."""


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
