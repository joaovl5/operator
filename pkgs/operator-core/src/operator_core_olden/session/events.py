"""Session lifecycle events for UI and script consumers."""

from attrs import define

from operator_shared.event_sink import EventSink


@define(frozen=True, kw_only=True)
class AgentTurnStarted:
  """Agent turn is beginning."""

  agent_id: str
  history_id: str | None = None


@define(frozen=True, kw_only=True)
class HistoryLoaded:
  """Persisted history was loaded for replay."""

  agent_id: str
  history_id: str
  message_count: int


@define(frozen=True, kw_only=True)
class SystemPromptSeeded:
  """Initial system prompt was persisted for an empty history."""

  agent_id: str
  history_id: str


@define(frozen=True, kw_only=True)
class UserMessagePersisted:
  """User prompt was persisted before model execution."""

  agent_id: str
  history_id: str
  author_id: str


@define(frozen=True, kw_only=True)
class AgentRunStarted:
  """Model execution is about to begin."""

  agent_id: str
  history_id: str
  replay_message_count: int


@define(frozen=True, kw_only=True)
class AgentStreamPartStarted:
  """A transient model response part started streaming."""

  agent_id: str
  history_id: str
  part_index: int
  part_kind: str


@define(frozen=True, kw_only=True)
class AgentStreamTextDelta:
  """A transient assistant text delta streamed from the model."""

  agent_id: str
  history_id: str
  part_index: int
  content_delta: str


@define(frozen=True, kw_only=True)
class AgentStreamThinkingDelta:
  """A transient assistant thinking delta streamed from the model."""

  agent_id: str
  history_id: str
  part_index: int
  content_delta: str


@define(frozen=True, kw_only=True)
class AgentStreamPartFinished:
  """A transient model response part finished streaming."""

  agent_id: str
  history_id: str
  part_index: int
  part_kind: str


@define(frozen=True, kw_only=True)
class AgentStreamToolCallStarted:
  """A function tool call started during model execution."""

  agent_id: str
  history_id: str
  tool_call_id: str
  tool_name: str
  args: str | None = None


@define(frozen=True, kw_only=True)
class AgentStreamToolCallFinished:
  """A function tool call finished during model execution."""

  agent_id: str
  history_id: str
  tool_call_id: str
  tool_name: str | None
  outcome: str
  result: str | None = None


@define(frozen=True, kw_only=True)
class AgentRunFinished:
  """Model execution finished and returned messages to persist."""

  agent_id: str
  history_id: str
  history_request_count: int


@define(frozen=True, kw_only=True)
class AgentRunFailed:
  """Model execution failed before final messages were persisted."""

  agent_id: str
  history_id: str
  error_type: str
  error_message: str


@define(frozen=True, kw_only=True)
class AgentRunCancelled:
  """Model execution was cancelled before final messages were persisted."""

  agent_id: str
  history_id: str


@define(frozen=True, kw_only=True)
class HistoryMessagePersisted:
  """A returned model/tool message was persisted."""

  agent_id: str
  history_id: str
  role: str
  message_index: int


@define(frozen=True, kw_only=True)
class AgentTurnFinished:
  """Agent turn finished after persistence."""

  agent_id: str
  history_id: str
  persisted_message_count: int


type SessionEvent = (
  AgentTurnStarted
  | HistoryLoaded
  | SystemPromptSeeded
  | UserMessagePersisted
  | AgentRunStarted
  | AgentStreamPartStarted
  | AgentStreamTextDelta
  | AgentStreamThinkingDelta
  | AgentStreamPartFinished
  | AgentStreamToolCallStarted
  | AgentStreamToolCallFinished
  | AgentRunFinished
  | AgentRunFailed
  | AgentRunCancelled
  | HistoryMessagePersisted
  | AgentTurnFinished
)


type SessionEventSink = EventSink[SessionEvent]


@define(kw_only=True)
class AgentEventEmitter:
  """Emits agent-scoped session events with common IDs injected."""

  event_sink: SessionEventSink | None
  agent_id: str
  history_id: str | None = None

  async def agent_turn_started(self) -> None:
    """Emit an agent turn start event."""
    await self._emit(
      AgentTurnStarted(
        agent_id=self.agent_id,
        history_id=self.history_id,
      ),
    )

  async def history_loaded(self, *, message_count: int) -> None:
    """Emit a history loaded event."""
    await self._emit(
      HistoryLoaded(
        agent_id=self.agent_id,
        history_id=self._require_history_id(),
        message_count=message_count,
      ),
    )

  async def system_prompt_seeded(self) -> None:
    """Emit a system prompt seeded event."""
    await self._emit(
      SystemPromptSeeded(
        agent_id=self.agent_id,
        history_id=self._require_history_id(),
      ),
    )

  async def user_message_persisted(self, *, author_id: str) -> None:
    """Emit a user message persisted event."""
    await self._emit(
      UserMessagePersisted(
        agent_id=self.agent_id,
        history_id=self._require_history_id(),
        author_id=author_id,
      ),
    )

  async def agent_run_started(
    self, *, replay_message_count: int
  ) -> None:
    """Emit an agent run start event."""
    await self._emit(
      AgentRunStarted(
        agent_id=self.agent_id,
        history_id=self._require_history_id(),
        replay_message_count=replay_message_count,
      ),
    )

  async def agent_stream_part_started(
    self, *, part_index: int, part_kind: str
  ) -> None:
    """Emit a stream part started event."""
    await self._emit(
      AgentStreamPartStarted(
        agent_id=self.agent_id,
        history_id=self._require_history_id(),
        part_index=part_index,
        part_kind=part_kind,
      ),
    )

  async def agent_stream_text_delta(
    self, *, part_index: int, content_delta: str
  ) -> None:
    """Emit a stream text delta event."""
    await self._emit(
      AgentStreamTextDelta(
        agent_id=self.agent_id,
        history_id=self._require_history_id(),
        part_index=part_index,
        content_delta=content_delta,
      ),
    )

  async def agent_stream_thinking_delta(
    self, *, part_index: int, content_delta: str
  ) -> None:
    """Emit a stream thinking delta event."""
    await self._emit(
      AgentStreamThinkingDelta(
        agent_id=self.agent_id,
        history_id=self._require_history_id(),
        part_index=part_index,
        content_delta=content_delta,
      ),
    )

  async def agent_stream_part_finished(
    self, *, part_index: int, part_kind: str
  ) -> None:
    """Emit a stream part finished event."""
    await self._emit(
      AgentStreamPartFinished(
        agent_id=self.agent_id,
        history_id=self._require_history_id(),
        part_index=part_index,
        part_kind=part_kind,
      ),
    )

  async def agent_stream_tool_call_started(
    self,
    *,
    tool_call_id: str,
    tool_name: str,
    args: str | None = None,
  ) -> None:
    """Emit a stream tool call started event."""
    await self._emit(
      AgentStreamToolCallStarted(
        agent_id=self.agent_id,
        history_id=self._require_history_id(),
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        args=args,
      ),
    )

  async def agent_stream_tool_call_finished(
    self,
    *,
    tool_call_id: str,
    tool_name: str | None,
    outcome: str,
    result: str | None = None,
  ) -> None:
    """Emit a stream tool call finished event."""
    await self._emit(
      AgentStreamToolCallFinished(
        agent_id=self.agent_id,
        history_id=self._require_history_id(),
        tool_call_id=tool_call_id,
        tool_name=tool_name,
        outcome=outcome,
        result=result,
      ),
    )

  async def agent_run_finished(
    self, *, history_request_count: int
  ) -> None:
    """Emit an agent run finished event."""
    await self._emit(
      AgentRunFinished(
        agent_id=self.agent_id,
        history_id=self._require_history_id(),
        history_request_count=history_request_count,
      ),
    )

  async def agent_run_failed(
    self, *, error_type: str, error_message: str
  ) -> None:
    """Emit an agent run failed event."""
    await self._emit(
      AgentRunFailed(
        agent_id=self.agent_id,
        history_id=self._require_history_id(),
        error_type=error_type,
        error_message=error_message,
      ),
    )

  async def agent_run_cancelled(self) -> None:
    """Emit an agent run cancelled event."""
    await self._emit(
      AgentRunCancelled(
        agent_id=self.agent_id,
        history_id=self._require_history_id(),
      ),
    )

  async def history_message_persisted(
    self, *, role: str, message_index: int
  ) -> None:
    """Emit a history message persisted event."""
    await self._emit(
      HistoryMessagePersisted(
        agent_id=self.agent_id,
        history_id=self._require_history_id(),
        role=role,
        message_index=message_index,
      ),
    )

  async def agent_turn_finished(
    self, *, persisted_message_count: int
  ) -> None:
    """Emit an agent turn finished event."""
    await self._emit(
      AgentTurnFinished(
        agent_id=self.agent_id,
        history_id=self._require_history_id(),
        persisted_message_count=persisted_message_count,
      ),
    )

  async def _emit(self, event: SessionEvent) -> None:
    if self.event_sink:
      await self.event_sink(event=event)

  def _require_history_id(self) -> str:
    if self.history_id is None:
      message = (
        "history_id is required for history-scoped session events"
      )
      raise RuntimeError(message)
    return self.history_id


__all__ = [
  "AgentEventEmitter",
  "AgentRunCancelled",
  "AgentRunFailed",
  "AgentRunFinished",
  "AgentRunStarted",
  "AgentStreamPartFinished",
  "AgentStreamPartStarted",
  "AgentStreamTextDelta",
  "AgentStreamThinkingDelta",
  "AgentStreamToolCallFinished",
  "AgentStreamToolCallStarted",
  "AgentTurnFinished",
  "AgentTurnStarted",
  "HistoryLoaded",
  "HistoryMessagePersisted",
  "SessionEvent",
  "SessionEventSink",
  "SystemPromptSeeded",
  "UserMessagePersisted",
]
