"""Session lifecycle events for UI and script consumers."""

from typing import Protocol

from attrs import define


@define(frozen=True, kw_only=True)
class AgentTurnStarted:
    """Agent turn is beginning."""

    agent_id: str


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
class AgentRunFinished:
    """Model execution finished and returned messages to persist."""

    agent_id: str
    history_id: str
    history_request_count: int


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
    | AgentRunFinished
    | HistoryMessagePersisted
    | AgentTurnFinished
)


class SessionEventSink(Protocol):
    """Receives session lifecycle events."""

    async def __call__(self, *, event: SessionEvent) -> None:
        """Handle one session lifecycle event."""


__all__ = [
    "AgentRunFinished",
    "AgentRunStarted",
    "AgentTurnFinished",
    "AgentTurnStarted",
    "HistoryLoaded",
    "HistoryMessagePersisted",
    "SessionEvent",
    "SessionEventSink",
    "SystemPromptSeeded",
    "UserMessagePersisted",
]
