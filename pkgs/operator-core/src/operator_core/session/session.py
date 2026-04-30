from asyncio import CancelledError
from pathlib import Path
from typing import TYPE_CHECKING

from attrs import Factory, define

from operator_core.agent.main import OpAgent
from operator_core.agent.streaming import (
    AgentStreamEvent,
    StreamPartFinished,
    StreamPartStarted,
    StreamTextDelta,
    StreamToolCallFinished,
    StreamToolCallStarted,
)
from operator_core.agent.types import ORCHESTRATOR_ID, UserMessage
from operator_core.config import DEFAULT_OPERATOR_SYSTEM_PROMPT, OperatorConfig
from operator_core.mail.mail import Mailbox
from operator_core.permissions import (
    FilesystemScope,
    Permission,
    PermissionGroup,
    PermissionType,
    TemporalScope,
)
from operator_core.providers.factory import build_model_from_config
from operator_core.session.errors import (
    SessionAgentUnavailableError,
    SessionMissingAgentError,
    SessionPersistenceUnavailableError,
)
from operator_core.session.events import (
    AgentRunCancelled,
    AgentRunFailed,
    AgentRunFinished,
    AgentRunStarted,
    AgentStreamPartFinished,
    AgentStreamPartStarted,
    AgentStreamTextDelta,
    AgentStreamToolCallFinished,
    AgentStreamToolCallStarted,
    AgentTurnFinished,
    AgentTurnStarted,
    HistoryLoaded,
    HistoryMessagePersisted,
    SessionEvent,
    SessionEventSink,
    SystemPromptSeeded,
    UserMessagePersisted,
)
from operator_db.objects.agent import AgentRequestSchema, SessionAgentService
from operator_db.objects.history import HistoryService
from operator_db.objects.session import SessionRequestSchema, SessionService
from operator_shared.providers.transforms import (
    OperatorRequestMessage,
    OperatorSystemPromptPart,
    OperatorUserPromptPart,
)
from operator_shared.time.utils import mk_time

if TYPE_CHECKING:
    from datetime import datetime, timedelta

    from operator_db.objects.agent.schema import AgentResponseSchema
    from operator_db.objects.history.schema import HistoryMessageResponseSchema
    from operator_db.objects.session.schema import SessionResponseSchema
    from operator_db.utils.services import DbSession


def get_orchestrator_perms() -> PermissionGroup:
    """Gather perms for Orchestrator."""
    cwd_stub = Path()
    fs_scope = FilesystemScope(path=cwd_stub)
    t_scope = TemporalScope.All()
    perms: list[PermissionType] = [
        Permission.Filesystem.Read(scope=fs_scope),
        Permission.Filesystem.Edit(scope=fs_scope),
        Permission.Subagent(),
    ]
    return PermissionGroup(
        perms=[t_scope.wrap_permission(perm) for perm in perms],
    )


def assemble_system_prompt(*, agent_system_prompt: str) -> str:
    """Assemble Operator and agent-specific system prompts."""
    agent_prompt = agent_system_prompt.strip()
    if not agent_prompt:
        return DEFAULT_OPERATOR_SYSTEM_PROMPT
    return f"{DEFAULT_OPERATOR_SYSTEM_PROMPT}\n\n{agent_prompt}"


def get_orchestrator_agent(*, config: OperatorConfig, history_id: str | None = None) -> OpAgent:
    """Create Orchestrator `OpAgent`."""
    return OpAgent(
        id=ORCHESTRATOR_ID,
        model=build_model_from_config(config=config.model),
        system_prompt=assemble_system_prompt(agent_system_prompt=config.agent.system_prompt),
        permissions=get_orchestrator_perms(),
        history_id=history_id,
    )


def _empty_mailbox() -> Mailbox:
    return Mailbox(messages=[])


@define(kw_only=True)
class Session:
    config: OperatorConfig
    db_session: DbSession | None = None
    session_id: str | None = None
    agents: dict[str, OpAgent] = Factory(dict)  # pyright: ignore[reportUnknownVariableType]
    mailbox: Mailbox = Factory(_empty_mailbox)
    session_service: SessionService = Factory(SessionService)
    agent_service: SessionAgentService = Factory(SessionAgentService)
    history_service: HistoryService = Factory(HistoryService)
    event_sink: SessionEventSink | None = None

    time_start: datetime = Factory(mk_time)

    def __attrs_post_init__(self) -> None:
        """Initialize agents, if necessary."""
        if ORCHESTRATOR_ID not in self.agents:
            self.agents[ORCHESTRATOR_ID] = get_orchestrator_agent(config=self.config)

    @classmethod
    async def create(
        cls,
        *,
        config: OperatorConfig,
        db_session: DbSession,
        mailbox: Mailbox | None = None,
        event_sink: SessionEventSink | None = None,
    ) -> Session:
        """Create a persisted runtime session with its orchestrator agent."""
        session_service = SessionService()
        agent_service = SessionAgentService()
        session_response = await session_service.create_session(
            request=SessionRequestSchema(),
            db_session=db_session,
        )
        agent = get_orchestrator_agent(config=config)
        agent_response = await _create_persisted_agent(
            agent=agent,
            config=config,
            session_response=session_response,
            agent_service=agent_service,
            db_session=db_session,
        )
        agent.history_id = agent_response.history_id
        return cls(
            config=config,
            db_session=db_session,
            session_id=session_response.id,
            agents={agent.id: agent},
            mailbox=_empty_mailbox() if mailbox is None else mailbox,
            session_service=session_service,
            agent_service=agent_service,
            event_sink=event_sink,
        )

    @property
    def time_elapsed(self) -> timedelta:
        """Returns elapsed time from `time_start`."""
        time_now = mk_time()
        return time_now - self.time_start

    async def send_user_message(self, msg: UserMessage) -> list[HistoryMessageResponseSchema]:
        """Send an user-sourced message to an agent, prompting/queue-ing agent's turn."""
        self.mailbox.add(
            msg=msg.to_mail_message(),
        )
        return await self.agent_loop(agent_id=msg.target_agent_id, user_message=msg)

    async def _verify_agent_may_run(self, _agent: OpAgent) -> None:
        """Verifies an agent can proceed to a turn. (Currently a stub).

        This is done for checking:
        - is context window near exhaustion?
        - is max turn count reached?

        In these circumstances, special exceptions are raised for handling cases:
        - context needs compaction: raise a SessionRequiresCompaction signal
        - max turn count reached: raise a SessionTurnsExhausted signal
        """

    async def agent_loop(
        self,
        *,
        agent_id: str,
        user_message: UserMessage | None = None,
    ) -> list[HistoryMessageResponseSchema]:
        """Does agent turns (mostly) indefinitely."""
        agent = self.agents.get(agent_id)
        if agent is None:
            raise SessionMissingAgentError
        if agent.lock.locked():
            raise SessionAgentUnavailableError
        async with agent.lock:
            return await self.agent_turn(agent=agent, user_message=user_message)

    async def agent_turn(
        self,
        *,
        agent: OpAgent,
        user_message: UserMessage | None = None,
    ) -> list[HistoryMessageResponseSchema]:
        """Run a single persisted agent step."""
        await self._verify_agent_may_run(agent)
        await self._emit_event(event=AgentTurnStarted(agent_id=agent.id))
        history_id = await self._ensure_agent_history_id(agent=agent)
        messages = await self.history_service.list_messages(
            history_id=history_id,
            db_session=self._require_db_session(),
        )
        await self._emit_event(
            event=HistoryLoaded(
                agent_id=agent.id,
                history_id=history_id,
                message_count=len(messages),
            ),
        )
        persisted_messages: list[HistoryMessageResponseSchema] = []
        if not messages:
            system_message = await self._append_initial_system_prompt(
                agent=agent,
                history_id=history_id,
            )
            messages.append(system_message)
            persisted_messages.append(system_message)
            await self._emit_event(
                event=SystemPromptSeeded(agent_id=agent.id, history_id=history_id),
            )
        if user_message is not None:
            user_response = await self._append_user_message(
                agent=agent,
                history_id=history_id,
                message=user_message,
            )
            messages.append(user_response)
            persisted_messages.append(user_response)
            await self._emit_event(
                event=UserMessagePersisted(
                    agent_id=agent.id,
                    history_id=history_id,
                    author_id=user_message.source_user_id,
                ),
            )
        await self._emit_event(
            event=AgentRunStarted(
                agent_id=agent.id,
                history_id=history_id,
                replay_message_count=len(messages),
            ),
        )
        async def stream_sink(*, event: AgentStreamEvent) -> None:
            await self._emit_agent_stream_event(
                agent_id=agent.id,
                history_id=history_id,
                event=event,
            )

        try:
            history_requests = await agent.run(messages=messages, stream_sink=stream_sink)
        except CancelledError:
            await self._emit_event(
                event=AgentRunCancelled(agent_id=agent.id, history_id=history_id),
            )
            raise
        except Exception as error:
            await self._emit_event(
                event=AgentRunFailed(
                    agent_id=agent.id,
                    history_id=history_id,
                    error_type=type(error).__name__,
                    error_message=str(error),
                ),
            )
            raise
        await self._emit_event(
            event=AgentRunFinished(
                agent_id=agent.id,
                history_id=history_id,
                history_request_count=len(history_requests),
            ),
        )
        for history_request in history_requests:
            history_response = await self.history_service.append_message(
                history_id=history_id,
                request=history_request,
                db_session=self._require_db_session(),
            )
            persisted_messages.append(history_response)
            await self._emit_event(
                event=HistoryMessagePersisted(
                    agent_id=agent.id,
                    history_id=history_id,
                    role=history_response.role.value,
                    message_index=history_response.message_index,
                ),
            )
        await self._emit_event(
            event=AgentTurnFinished(
                agent_id=agent.id,
                history_id=history_id,
                persisted_message_count=len(persisted_messages),
            ),
        )
        return persisted_messages

    async def _ensure_agent_history_id(self, *, agent: OpAgent) -> str:
        if agent.history_id is not None:
            return agent.history_id
        db_session = self._require_db_session()
        if self.session_id is None:
            message = "session_id is required for history lifecycle"
            raise SessionPersistenceUnavailableError(message)

        persisted_agent = await self.agent_service.get_agent_by_local_id(
            session_id=self.session_id,
            local_id=agent.id,
            db_session=db_session,
        )
        if persisted_agent is None:
            persisted_agent = await _create_persisted_agent(
                agent=agent,
                config=self.config,
                session_response=_SessionIdResponse(id=self.session_id),
                agent_service=self.agent_service,
                db_session=db_session,
            )
        agent.history_id = persisted_agent.history_id
        return persisted_agent.history_id

    async def _append_initial_system_prompt(
        self,
        *,
        agent: OpAgent,
        history_id: str,
    ) -> HistoryMessageResponseSchema:
        now = mk_time()
        request = agent.history_transform.to_history_request(
            message=OperatorRequestMessage(
                parts=[OperatorSystemPromptPart(content=agent.system_prompt, timestamp=now)],
                timestamp=now,
                author_id=agent.id,
            ),
            author_id=agent.id,
        )
        return await self.history_service.append_message(
            history_id=history_id,
            request=request,
            db_session=self._require_db_session(),
        )

    async def _append_user_message(
        self,
        *,
        agent: OpAgent,
        history_id: str,
        message: UserMessage,
    ) -> HistoryMessageResponseSchema:
        request = agent.history_transform.to_history_request(
            message=OperatorRequestMessage(
                parts=[
                    OperatorUserPromptPart(content=message.contents, timestamp=message.sent_at),
                ],
                timestamp=message.sent_at,
                author_id=message.source_user_id,
            ),
            author_id=message.source_user_id,
        )
        return await self.history_service.append_message(
            history_id=history_id,
            request=request,
            db_session=self._require_db_session(),
        )

    async def _emit_agent_stream_event(
        self,
        *,
        agent_id: str,
        history_id: str,
        event: AgentStreamEvent,
    ) -> None:
        match event:
            case StreamPartStarted(part_index=part_index, part_kind=part_kind):
                session_event = AgentStreamPartStarted(
                    agent_id=agent_id,
                    history_id=history_id,
                    part_index=part_index,
                    part_kind=part_kind,
                )
            case StreamTextDelta(part_index=part_index, content_delta=content_delta):
                session_event = AgentStreamTextDelta(
                    agent_id=agent_id,
                    history_id=history_id,
                    part_index=part_index,
                    content_delta=content_delta,
                )
            case StreamPartFinished(part_index=part_index, part_kind=part_kind):
                session_event = AgentStreamPartFinished(
                    agent_id=agent_id,
                    history_id=history_id,
                    part_index=part_index,
                    part_kind=part_kind,
                )
            case StreamToolCallStarted(tool_call_id=tool_call_id, tool_name=tool_name):
                session_event = AgentStreamToolCallStarted(
                    agent_id=agent_id,
                    history_id=history_id,
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                )
            case StreamToolCallFinished(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                outcome=outcome,
            ):
                session_event = AgentStreamToolCallFinished(
                    agent_id=agent_id,
                    history_id=history_id,
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    outcome=outcome,
                )
        await self._emit_event(event=session_event)


    async def _emit_event(self, *, event: SessionEvent) -> None:
        if self.event_sink is not None:
            await self.event_sink(event=event)


    def _require_db_session(self) -> DbSession:
        if self.db_session is None:
            message = "db_session is required for history lifecycle"
            raise SessionPersistenceUnavailableError(message)
        return self.db_session


@define(kw_only=True)
class _SessionIdResponse:
    id: str


async def _create_persisted_agent(
    *,
    agent: OpAgent,
    config: OperatorConfig,
    session_response: SessionResponseSchema | _SessionIdResponse,
    agent_service: SessionAgentService,
    db_session: DbSession,
) -> AgentResponseSchema:
    return await agent_service.create_agent(
        request=AgentRequestSchema(
            session_id=session_response.id,
            local_id=agent.id,
            model=config.model.name,
            system_prompt=config.agent.system_prompt,
            serialized_permissions=None,
        ),
        db_session=db_session,
    )
