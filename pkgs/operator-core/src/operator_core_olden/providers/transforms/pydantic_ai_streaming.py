"""PydanticAI streaming event adapters."""

import json
from typing import TYPE_CHECKING

from pydantic_ai import (
  BuiltinToolCallPart,
  BuiltinToolReturnPart,
  FilePart,
  FunctionToolCallEvent,
  FunctionToolResultEvent,
  PartDeltaEvent,
  PartEndEvent,
  PartStartEvent,
  RetryPromptPart,
  TextPart,
  TextPartDelta,
  ThinkingPart,
  ThinkingPartDelta,
  ToolCallPart,
  ToolReturnPart,
)

from operator_core_olden.agent.streaming import (
  AgentStreamEvent,
  AgentStreamSink,
  StreamPartFinished,
  StreamPartStarted,
  StreamTextDelta,
  StreamThinkingDelta,
  StreamToolCallFinished,
  StreamToolCallStarted,
)

if TYPE_CHECKING:
  from collections.abc import AsyncIterable


class PydanticAIStreamTransform:
  """Translate PydanticAI stream events into transient Operator
  stream events.
  """

  async def forward_events(
    self,
    *,
    events: AsyncIterable[object],
    sink: AgentStreamSink,
  ) -> None:
    """Forward translated stream events to a sink."""
    async for event in events:
      for stream_event in _stream_events_from_provider(event):
        await sink(event=stream_event)


def _stream_events_from_provider(
  event: object,
) -> list[AgentStreamEvent]:
  match event:
    case PartStartEvent(index=index, part=part):
      return _part_started_events(index=index, part=part)
    case PartDeltaEvent(index=index, delta=delta):
      return _part_delta_events(index=index, delta=delta)
    case PartEndEvent(index=index, part=part):
      return [
        StreamPartFinished(
          part_index=index, part_kind=_part_kind(part)
        )
      ]
    case FunctionToolCallEvent(part=part):
      return [
        StreamToolCallStarted(
          tool_call_id=part.tool_call_id,
          tool_name=part.tool_name,
          args=_preview_value(part.args),
        ),
      ]
    case FunctionToolResultEvent(result=result):
      return [_tool_call_finished_event(result)]
    case _:
      return []


def _part_started_events(
  *, index: int, part: object
) -> list[AgentStreamEvent]:
  stream_events: list[AgentStreamEvent] = [
    StreamPartStarted(part_index=index, part_kind=_part_kind(part)),
  ]
  if isinstance(part, TextPart) and part.content:
    stream_events.append(
      StreamTextDelta(part_index=index, content_delta=part.content)
    )
  elif isinstance(part, ThinkingPart) and part.content:
    stream_events.append(
      StreamThinkingDelta(
        part_index=index, content_delta=part.content
      )
    )
  return stream_events


def _part_delta_events(
  *, index: int, delta: object
) -> list[AgentStreamEvent]:
  match delta:
    case TextPartDelta(content_delta=content_delta) if content_delta:
      return [
        StreamTextDelta(part_index=index, content_delta=content_delta)
      ]
    case ThinkingPartDelta(content_delta=content_delta) if (
      content_delta
    ):
      return [
        StreamThinkingDelta(
          part_index=index, content_delta=content_delta
        )
      ]
    case _:
      return []


def _tool_call_finished_event(
  result: ToolReturnPart | RetryPromptPart,
) -> StreamToolCallFinished:
  match result:
    case ToolReturnPart():
      return StreamToolCallFinished(
        tool_call_id=result.tool_call_id,
        tool_name=result.tool_name,
        outcome=result.outcome,
        result=_preview_value(result.content),
      )
    case RetryPromptPart():
      return StreamToolCallFinished(
        tool_call_id=result.tool_call_id,
        tool_name=result.tool_name,
        outcome="retry",
        result=_preview_value(result.content),
      )


def _part_kind(part: object) -> str:
  part_kind: str
  match part:
    case TextPart():
      part_kind = "text"
    case ThinkingPart():
      part_kind = "thinking"
    case BuiltinToolCallPart():
      part_kind = "builtin_tool_call"
    case BuiltinToolReturnPart():
      part_kind = "builtin_tool_return"
    case ToolCallPart():
      part_kind = "tool_call"
    case ToolReturnPart():
      part_kind = "tool_return"
    case FilePart():
      part_kind = "file"
    case _:
      part_kind = type(part).__name__
  return part_kind


def _preview_value(
  value: object, *, max_chars: int = 2_000
) -> str | None:
  if value is None:
    return None
  if isinstance(value, str):
    preview = value
  else:
    preview = json.dumps(
      value, default=str, ensure_ascii=False, sort_keys=True
    )
  if len(preview) <= max_chars:
    return preview
  omitted = len(preview) - max_chars
  return f"{preview[:max_chars]}... <truncated {omitted} chars>"


__all__ = ["PydanticAIStreamTransform"]
