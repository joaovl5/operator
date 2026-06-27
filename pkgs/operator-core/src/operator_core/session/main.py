from asyncio import Event, Lock, Task, create_task
from typing import TYPE_CHECKING

from attrs import Factory, define, field

from operator_core.session.types import EventPointer, IncomingMessage, StopAgentMethod
from operator_db.objects import Session, SessionAgent, SessionAgentSvc, SessionSvc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from operator_shared.settings import OperatorSettings

type _AgentMap = dict[str, SessionAgent]
type _AgentManagerMap = dict[str, SessionAgentManager]
type _AgentLoopTaskMap = dict[str, Task[None]]


@define(kw_only=True)
class SessionAgentManager:
    """Proxy for db-side session-agent.

    This shouldn't hold state for long, and it should keep itself in-sync with database.
    """

    settings: OperatorSettings
    db_session: AsyncSession
    db_obj: SessionAgent

    service: SessionAgentSvc = Factory(
        lambda s: SessionAgentSvc(
            settings=s.settings,
            session=s.db_session,
        ),
        takes_self=True,
    )

    loop_lock: Lock = Factory(Lock)
    """Locked when `do_loop` is running."""

    loop_end_ev: Event = Factory(Event)
    """Fired after loop ends."""

    turn_lock: Lock = Factory(Lock)
    """Locked per-turn during loop."""

    turn_end_ev: Event = Factory(Event)
    """Fired per-turn endings."""

    def refresh(self, db_obj: SessionAgent) -> None:
        """Replace internal db-object."""
        self.db_obj = db_obj

    async def do_loop(self) -> None:
        """Perform this agent's loop until a termination signal is triggered."""
        self.loop_end_ev.clear()
        async with self.loop_lock:
            await self._do_turn()
        self.loop_end_ev.set()

    async def _do_turn(self) -> None:
        self.turn_end_ev.clear()
        async with self.turn_lock:
            pass
        self.turn_end_ev.set()

    async def add_user_message(
        self,
        *,
        parent_pointer: EventPointer,
        message: IncomingMessage,
    ) -> None:
        """Adds user message to context."""
        await self.service.add_message(
            parent_id=parent_pointer.event_id,
            context_id=parent_pointer.context_id,
            text_data=message.text_data,
            json_data=message.json_data,
            bytes_data=message.bytes_data,
        )


@define(kw_only=True)
class SessionManager:
    """Management of a single session."""

    settings: OperatorSettings
    db_session: AsyncSession

    service: SessionSvc = Factory(
        lambda s: SessionSvc(
            settings=s.settings,
            session=s.db_session,
        ),
        takes_self=True,
    )
    _obj: Session = field(init=False)
    _ready: bool = field(init=False, default=False)
    _agents: _AgentMap = field(init=False, factory=dict)
    _agent_mgrs: _AgentManagerMap = field(init=False, factory=dict)
    _agent_loop_tasks: _AgentLoopTaskMap = field(init=False, factory=dict)

    async def _ensure_ok(self) -> None:
        """Ensure async-part of initialization is done."""
        if self._ready:
            return
        self._obj = await self.service.make_session(
            session_title=None,
            with_orchestrator=True,
        )
        self._ready = True

    def _refresh_agent_managers(self) -> None:
        for k, db_agent in self._agents.items():
            if mgr := self._agent_mgrs.get(k):
                mgr.refresh(db_agent)
                continue
            self._agent_mgrs[k] = SessionAgentManager(
                settings=self.settings,
                db_session=self.db_session,
                db_obj=db_agent,
            )

    async def refresh_agents(self) -> None:
        """Refreshes agents."""
        await self._ensure_ok()
        lst: list[SessionAgent] = await self._obj.awaitable_attrs.session_agents
        self._agents = {x.agent_id: x for x in lst}
        self._refresh_agent_managers()

    async def do_agent_loop(
        self,
        agent_id: str,
    ) -> None:
        """Does agent loop until termination signal."""
        await self.refresh_agents()
        mgr = self._agent_mgrs[agent_id]
        loop_task: Task[None]
        if x := self._agent_loop_tasks.get(agent_id):
            loop_task = x
        else:
            loop_task = create_task(mgr.do_loop())
            self._agent_loop_tasks[agent_id] = loop_task
        await loop_task
        del self._agent_loop_tasks[agent_id]

    async def trigger_stop(self, agent_id: str, stop_method: StopAgentMethod) -> None:
        """Trigger a stop for that agent based on the `stop_method` value."""
        await self.refresh_agents()
        mgr = self._agent_mgrs[agent_id]
        match stop_method:
            case StopAgentMethod.KILL:
                if task := self._agent_loop_tasks.get(agent_id):
                    task.cancel()
            case StopAgentMethod.WAIT_LOOP:
                await mgr.loop_end_ev.wait()
            case StopAgentMethod.WAIT_TURN:
                await mgr.turn_end_ev.wait()

    async def add_user_message(
        self,
        agent_id: str,
        parent_pointer: EventPointer,
        message: IncomingMessage,
        stop_method: StopAgentMethod = StopAgentMethod.WAIT_LOOP,
    ) -> None:
        """Adds a user message to an agent's context.

        This does not make the loop start/restart afterwards.
        """
        await self.trigger_stop(
            agent_id=agent_id,
            stop_method=stop_method,
        )
        await self._agent_mgrs[agent_id].add_user_message(
            message=message,
            parent_pointer=parent_pointer,
        )
