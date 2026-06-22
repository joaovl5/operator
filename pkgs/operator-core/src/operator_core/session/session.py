from asyncio import CancelledError
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING

from attrs import Factory, define

from operator_core.agent.main import OpAgent
from operator_core.agent.streaming import (
    AgentStreamEvent,
    StreamPartFinished,
    StreamPartStarted,
    StreamTextDelta,
    StreamThinkingDelta,
    StreamToolCallFinished,
    StreamToolCallStarted,
)
from operator_core.agent.types import ORCHESTRATOR_ID, UserMessage
from operator_core.permissions import (
    FilesystemScope,
    Permission,
    PermissionGroup,
    PermissionType,
    TemporalScope,
)
from operator_core.session.errors import (
    SessionAgentUnavailableError,
    SessionMissingAgentError,
    SessionPersistenceUnavailableError,
)
from operator_core.session.events import AgentEventEmitter, SessionEventSink
from operator_core.toolsets.files import FileToolset
from operator_db.objects.agent import AgentRequestSchema, SessionAgentService
from operator_db.objects.history import HistoryService
from operator_db.objects.session import SessionRequestSchema, SessionService
from operator_shared.providers.transforms import (
    OperatorRequestMessage,
    OperatorRequestPart,
    OperatorSystemPromptPart,
    OperatorUserPromptPart,
)
from operator_shared.time.utils import mk_time

if TYPE_CHECKING:
    from pydantic import DirectoryPath

    from operator_db.objects.agent.schema import AgentResponseSchema
    from operator_db.objects.history.schema import (
        HistoryMessageRequestSchema,
        HistoryMessageResponseSchema,
    )
    from operator_db.objects.session.schema import SessionResponseSchema
    from operator_db.utils.services import DbSession
    from operator_shared.settings import OperatorSettings


def get_orchestrator_perms(cwd: Path) -> PermissionGroup:
    """Gather perms for Orchestrator."""
    fs_scope = FilesystemScope(path=cwd)
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


def _get_orchestrator_agent(
    *,
    settings: OperatorSettings,
    history_id: str | None = None,
    cwd: Path,
) -> OpAgent:
    return OpAgent(
        id=ORCHESTRATOR_ID,
        model=build_model_from_config(config=config.model),
        system_prompt=assemble_system_prompt(agent_system_prompt=config.agent.system_prompt),
        permissions=get_orchestrator_perms(cwd=cwd),
        history_id=history_id,
    )


@define(kw_only=True)
class Session:
    settings: OperatorSettings
    db_session: DbSession | None = None
    session_id: str | None = None
    agents: dict[str, OpAgent] = Factory(dict)  # pyright: ignore[reportUnknownVariableType]
    session_service: SessionService = Factory(SessionService)
    agent_service: SessionAgentService = Factory(SessionAgentService)
    history_service: HistoryService = Factory(HistoryService)
    event_sink: SessionEventSink | None = None
    working_directory: DirectoryPath = Factory(Path)

    def __attrs_post_init__(self) -> None:
        """Initialize agents, if necessary."""
        if ORCHESTRATOR_ID not in self.agents:
            self.agents[ORCHESTRATOR_ID] = _get_orchestrator_agent(
                settings=self.settings,
                cwd=self.working_directory,
            )
        self._register_tooling()

    @property
    def orchestrator(self) -> OpAgent:
        """Main orchestrator agent."""
        return self.agents[ORCHESTRATOR_ID]

    def _register_tooling(self) -> None:
        """Handle registering default tooling to agents."""
        self.orchestrator.register_toolsets(
            FileToolset(
                working_directory=self.working_directory,
            ).export_to_pydantic(),
        )

    @classmethod
    async def create(
        cls,
        *,
        settings: OperatorSettings,
        db_session: DbSession,
        event_sink: SessionEventSink | None = None,
        working_directory: DirectoryPath | None = None,
    ) -> Session:
        """Create a persisted runtime session with its orchestrator agent."""
        session_service = SessionService()
        agent_service = SessionAgentService()
        working_directory = working_directory or Path.cwd()
        session_response = await session_service.create_session(
            request=SessionRequestSchema(),
            db_session=db_session,
        )
        agent = _get_orchestrator_agent(
            settings=settings,
            cwd=working_directory,
        )
        agent_response = await _create_persisted_agent(
            agent=agent,
            settings=settings,
            session_response=session_response,
            agent_service=agent_service,
            db_session=db_session,
        )
        agent.history_id = agent_response.history_id
        return cls(
            settings=settings,
            db_session=db_session,
            session_id=session_response.id,
            agents={agent.id: agent},
            session_service=session_service,
            agent_service=agent_service,
            event_sink=event_sink,
            working_directory=working_directory,
        )

    async def send_user_message(self, msg: UserMessage) -> list[HistoryMessageResponseSchema]:
        """Send an user-sourced message to an agent, prompting/queue-ing agent's turn."""
        return await self.agent_loop(agent_id=msg.target_agent_id, user_message=msg)

    async def _check_agent_may_run(self, _agent: OpAgent) -> None:
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
            return await self._agent_turn(agent=agent, user_message=user_message)

    async def _agent_turn(
        self,
        *,
        agent: OpAgent,
        user_message: UserMessage | None = None,
    ) -> list[HistoryMessageResponseSchema]:
        """Run a single persisted agent step."""
        await self._check_agent_may_run(agent)
        emit = AgentEventEmitter(event_sink=self.event_sink, agent_id=agent.id)
        await emit.agent_turn_started()

        # Load message history
        history_id, messages = await self._get_agent_history_messages(agent=agent)
        emit.history_id = history_id
        await emit.history_loaded(message_count=len(messages))

        # REBUILD MESSAGE HISTORY
        # messages built from this turn
        turn_messages: list[HistoryMessageResponseSchema] = []

        # 1) If first turn, add sys. prompt
        if not messages:
            # TODO: SHOULD BE IN OpAgent CODE NOT HERE FOR FUCKS SAKE
            system_message = await self._add_system_message(
                agent=agent,
                history_id=history_id,
            )
            messages.append(system_message)
            turn_messages.append(system_message)
            await emit.system_prompt_seeded()

        # 2) Add the user message, if it exists
        if user_message:
            user_response = await self._add_user_message(
                agent=agent,
                history_id=history_id,
                message=user_message,
            )
            messages.append(user_response)
            turn_messages.append(user_response)
            await emit.user_message_persisted(author_id=user_message.source_user_id)

        # RUN AGENT W/ MESSAGES
        history_requests = await self._handle_agent_run(
            emit=emit,
            messages=messages,
            agent=agent,
        )

        # SAVE AGENT RESPONSE MESSAGES
        for history_request in history_requests:
            history_response = await self.history_service.append_message(
                history_id=history_id,
                request=history_request,
                db_session=self._expect_db_session(),
            )
            turn_messages.append(history_response)
            await emit.history_message_persisted(
                role=history_response.role.value,
                message_index=history_response.message_index,
            )
        await emit.agent_turn_finished(persisted_message_count=len(turn_messages))
        return turn_messages

    async def _handle_agent_run(
        self,
        *,
        emit: AgentEventEmitter,
        messages: list[HistoryMessageResponseSchema],
        agent: OpAgent,
    ) -> list[HistoryMessageRequestSchema]:
        await emit.agent_run_started(replay_message_count=len(messages))
        agent_stream_sink = partial(self._emit_agent_stream_event, emitter=emit)
        try:
            history_requests = await agent.run(messages=messages, stream_sink=agent_stream_sink)
        except CancelledError:
            await emit.agent_run_cancelled()
            raise
        except Exception as error:
            await emit.agent_run_failed(
                error_type=type(error).__name__,
                error_message=str(error),
            )
            raise
        await emit.agent_run_finished(history_request_count=len(history_requests))
        return history_requests

    async def _get_agent_history_messages(
        self, *, agent: OpAgent
    ) -> tuple[str, list[HistoryMessageResponseSchema]]:
        history_id = await self._get_agent_history_id(agent=agent)
        messages = await self.history_service.list_messages(
            history_id=history_id,
            db_session=self._expect_db_session(),
        )
        return history_id, messages

    async def _get_agent_history_id(self, *, agent: OpAgent) -> str:
        if agent.history_id:
            return agent.history_id
        if self.session_id is None:
            message = "session_id is required for history lifecycle"
            raise SessionPersistenceUnavailableError(message)
        db_session = self._expect_db_session()

        persisted_agent = await self.agent_service.get_agent_by_local_id(
            session_id=self.session_id,
            local_id=agent.id,
            db_session=db_session,
        )
        if persisted_agent is None:
            persisted_agent = await _create_persisted_agent(
                agent=agent,
                settings=self.settings,
                session_response=_SessionIdResponse(id=self.session_id),
                agent_service=self.agent_service,
                db_session=db_session,
            )
        agent.history_id = persisted_agent.history_id
        return persisted_agent.history_id

    async def _add_message(
        self,
        *request_parts: OperatorRequestPart,
        agent: OpAgent,
        history_id: str,
    ) -> HistoryMessageResponseSchema:
        now = mk_time()
        request_msg = OperatorRequestMessage(
            parts=[*request_parts],
            timestamp=now,
            author_id=agent.id,
        )
        request = agent.history_transform.to_history_request(
            message=request_msg,
            author_id=agent.id,
        )
        return await self.history_service.append_message(
            history_id=history_id,
            request=request,
            db_session=self._expect_db_session(),
        )

    async def _add_system_message(
        self,
        *,
        agent: OpAgent,
        history_id: str,
    ) -> HistoryMessageResponseSchema:
        return await self._add_message(
            OperatorSystemPromptPart(content=agent.system_prompt),
            agent=agent,
            history_id=history_id,
        )

    async def _add_user_message(
        self,
        *,
        agent: OpAgent,
        history_id: str,
        message: UserMessage,
    ) -> HistoryMessageResponseSchema:
        return await self._add_message(
            OperatorUserPromptPart(content=message.contents, timestamp=message.sent_at),
            agent=agent,
            history_id=history_id,
        )

    async def _emit_agent_stream_event(
        self,
        *,
        emitter: AgentEventEmitter,
        event: AgentStreamEvent,
    ) -> None:
        match event:
            case StreamPartStarted(part_index=part_index, part_kind=part_kind):
                await emitter.agent_stream_part_started(
                    part_index=part_index,
                    part_kind=part_kind,
                )
            case StreamTextDelta(part_index=part_index, content_delta=content_delta):
                await emitter.agent_stream_text_delta(
                    part_index=part_index,
                    content_delta=content_delta,
                )
            case StreamThinkingDelta(part_index=part_index, content_delta=content_delta):
                await emitter.agent_stream_thinking_delta(
                    part_index=part_index,
                    content_delta=content_delta,
                )
            case StreamPartFinished(part_index=part_index, part_kind=part_kind):
                await emitter.agent_stream_part_finished(
                    part_index=part_index,
                    part_kind=part_kind,
                )
            case StreamToolCallStarted(tool_call_id=tool_call_id, tool_name=tool_name, args=args):
                await emitter.agent_stream_tool_call_started(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    args=args,
                )
            case StreamToolCallFinished(
                tool_call_id=tool_call_id,
                tool_name=tool_name,
                outcome=outcome,
                result=result,
            ):
                await emitter.agent_stream_tool_call_finished(
                    tool_call_id=tool_call_id,
                    tool_name=tool_name,
                    outcome=outcome,
                    result=result,
                )

    def _expect_db_session(self) -> DbSession:
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
    settings: OperatorSettings,
    session_response: SessionResponseSchema | _SessionIdResponse,
    agent_service: SessionAgentService,
    db_session: DbSession,
) -> AgentResponseSchema:
    return await agent_service.create_agent(
        request=AgentRequestSchema(
            session_id=session_response.id,
            local_id=agent.id,
            model=settings.model.name,
            system_prompt=settings.agent.system_prompt,
            serialized_permissions=None,
        ),
        db_session=db_session,
    )
