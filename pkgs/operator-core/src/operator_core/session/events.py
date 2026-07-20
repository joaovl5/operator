from abc import ABC, abstractmethod
from typing import Any

from msgspec import Struct, field
from pydantic_ai import (
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
)


class _SessionEv(Struct, kw_only=True):
  agent_id: str

  extra_metadata: dict[str, Any] = field(default_factory=dict)


class _AgentPartEv(_SessionEv):
  part_index: int


class _AgentDeltaEv(_AgentPartEv):
  content: str | None = None
  replace: bool = False
  """Whether the delta should be treated as an append or replace
  operation.

    When `False`, will treat as 'append', and when `True` will be
    'replace'.
    """


class _AgentToolEv(_SessionEv):
  tool_call_id: str
  tool_name: str | None = None


class AgentTurnStart(_SessionEv):
  """Agent turn has begun."""


class AgentTurnEnd(_SessionEv):
  """Agent turn has ended."""


class AgentPartStart(_AgentPartEv):
  """Stream part has begun."""


class AgentPartEnd(_AgentPartEv):
  """Stream part has ended."""


class AgentTextDelta(_AgentDeltaEv):
  """Received text delta from model."""


class AgentThinkingDelta(_AgentDeltaEv):
  """Received thinking delta from model."""


class AgentToolCallStart(_AgentToolEv):
  """Function tool call has started."""

  args: object | None = None


class AgentToolCallEnd(_AgentToolEv, kw_only=True):
  """Function tool call has ended."""

  outcome: str
  result: object | None = None


class AgentRunFail(_SessionEv):
  """Model execution failed."""

  error_type: str
  error_message: str


class UserMessageSent(_SessionEv):
  """User prompt was persisted."""


type SessionEventType = (
  AgentTurnStart
  | AgentPartStart
  | AgentPartEnd
  | AgentTurnEnd
  | AgentTextDelta
  | AgentThinkingDelta
  | AgentToolCallStart
  | AgentToolCallEnd
  | AgentRunFail
)


class SessionEventSink(ABC):
  """Receiver of stream events."""

  @abstractmethod
  def handle(
    self,
    event: SessionEventType,
  ) -> None:
    """Handle an event.

    This is intentionally made non-async - any async logic should be
    made elsewhere,
    given this function will be called a lot and should be
    non-blocking.
    """


def from_pyai_event(
  agent_id: str,
  ev: object,
) -> list[SessionEventType]:
  """Attempt converting a PydanticAI event into a SessionEventType."""
  events: list[SessionEventType] = []
  match ev:
    case (
      PartStartEvent(
        index=index,
        part=delta,
      )
      | PartDeltaEvent(
        index=index,
        delta=delta,
      )
    ):
      if is_start := isinstance(ev, PartStartEvent):
        events.append(
          AgentPartStart(
            agent_id=agent_id,
            part_index=index,
          )
        )
      events += _from_delta_event(
        agent_id=agent_id,
        index=index,
        delta=delta,
        is_start=is_start,
      )
    case PartEndEvent(index=index):
      events.append(AgentPartEnd(agent_id=agent_id, part_index=index))
    case FunctionToolCallEvent(part=part):
      events.append(
        AgentToolCallStart(
          agent_id=agent_id,
          tool_call_id=part.tool_call_id,
          tool_name=part.tool_name,
          args=part.args,
        )
      )
    case FunctionToolResultEvent(part=part):
      kwargs = {
        "agent_id": agent_id,
        "tool_call_id": part.tool_call_id,
        "tool_name": part.tool_name,
        "outcome": "retry"
        if isinstance(part, RetryPromptPart)
        else part.outcome,
        "result": part.content,
      }
      events.append(AgentToolCallEnd(**kwargs))
    case _:
      pass

  return events


def _from_delta_event(
  agent_id: str,
  index: int,
  delta: object,
  *,
  is_start: bool,
) -> list[SessionEventType]:
  events: list[SessionEventType] = []
  match delta:
    case TextPart(content=cnt) | TextPartDelta(content_delta=cnt):
      events.append(
        AgentTextDelta(
          agent_id=agent_id,
          part_index=index,
          content=cnt,
          replace=is_start,
        )
      )
    case (
      ThinkingPart(content=cnt) | ThinkingPartDelta(content_delta=cnt)
    ):
      events.append(
        AgentThinkingDelta(
          agent_id=agent_id,
          part_index=index,
          content=cnt,
          replace=is_start,
        )
      )
    case _:
      pass

  return events
