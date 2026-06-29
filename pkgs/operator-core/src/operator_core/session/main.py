from asyncio import Event, Lock, Task, create_task
from typing import TYPE_CHECKING

from attrs import Factory, define, field
from pydantic_ai.models import Model

from operator_core.session.types import EventPointer, IncomingMessage, StopAgentMethod
from operator_db.objects import Session, SessionAgent, SessionAgentSvc, SessionSvc

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from operator_db.objects.base import IDType
    from operator_db.objects.context_event import CtxEvent
    from operator_shared.settings import OperatorSettings

type _AgentMap = dict[str, SessionAgent]
type _AgentManagerMap = dict[str, SessionAgentManager]
type _AgentLoopTaskMap = dict[str, Task[EventPointer]]


def _bake_model(self: SessionAgentManager) -> Model:
    pass


@define(kw_only=True)
class SessionAgentManager:
    """Proxy for db-side session-agent - stateful.

    This shouldn't hold state for long, and it should keep itself in-sync with database.
    """

    settings: OperatorSettings
    db_session: AsyncSession
    db_obj: SessionAgent

    svc: SessionAgentSvc = Factory(
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

    _pointer: EventPointer | None = field(init=False, default=None)

    async def _sync_db_pointer(self, event_id: IDType) -> None:
        if not self._pointer:
            self._pointer = EventPointer(
                context_id=self.db_obj.context_id,
                event_id=event_id,
            )
        else:
            self._pointer.event_id = event_id
        await self.svc.ctx_svc.set_pointer_id(
            context_id=self.db_obj.context_id,
            event_id=self._pointer.event_id,
        )

    async def get_pointer(self) -> EventPointer:
        """Get current `EventPointer` for agent context.

        Will use a cached pointer if found, otherwise will query database.
        """
        if x := self._pointer:
            return x
        ctx_id = self.db_obj.context_id
        res = await self.svc.ctx_svc.get_pointer_id(
            ctx_id,
        )
        if not res:
            msg = "Was expecting agent to have a non-null event pointer!"
            raise ValueError(msg)

        pointer = EventPointer(
            context_id=ctx_id,
            event_id=res,
        )
        self._pointer = pointer

        return pointer

    _model: Model = Factory(_make_agent_model, takes_self=True)

    def refresh(self, db_obj: SessionAgent) -> None:
        """Replace internal db-object."""
        self.db_obj = db_obj

    async def do_loop(self) -> None:
        """Perform this agent's loop until a termination signal is triggered."""
        self.loop_end_ev.clear()
        async with self.loop_lock:
            await self._do_turn()
        self.loop_end_ev.set()
        return EventPointer()

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
        msg = await self.svc.add_message(
            parent_id=parent_pointer.event_id,
            context_id=parent_pointer.context_id,
            text_data=message.text_data,
            json_data=message.json_data,
            bytes_data=message.bytes_data,
        )
        await self._sync_db_pointer(msg.id)

    async def _get_epoch(self) -> list[CtxEvent]:
        """Get current epoch from the perspective of an `EventPointer`."""
        events: list[CtxEvent] = await self.svc.event_svc.walk_up_epoch(
            event_id=self.pointer.event_id,
        )
        return events


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
    ) -> EventPointer:
        """Does agent loop until termination signal."""
        await self.refresh_agents()
        mgr = self._agent_mgrs[agent_id]
        loop_task: Task[EventPointer]
        if x := self._agent_loop_tasks.get(agent_id):
            loop_task = x
        else:
            loop_task = create_task(mgr.do_loop())
            self._agent_loop_tasks[agent_id] = loop_task
        pointer = await loop_task
        del self._agent_loop_tasks[agent_id]
        return pointer

    async def trigger_stop(
        self,
        agent_id: str,
        stop_method: StopAgentMethod,
        anchor_pointer: EventPointer,
    ) -> EventPointer:
        """Trigger a stop for agent.

        Args:
            agent_id: Agent to be stopped.
            stop_method: Method to handle stopping process.
            anchor_pointer: Base pointer for performing last event search, will be used
                            for a downward search.

        Returns:
            Pointer to last event from agent loop.

        """
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
        out = await mgr.svc.event_svc.walk_down_unforked(
            anchor_event_id=anchor_pointer.event_id,
        )
        if not out:
            msg = (
                "While attempting to find last agent event, no event could be found. "
                "Has a fork somehow occured along the way?"
            )
            raise ValueError(msg)
        return EventPointer(event_id=out.id, context_id=out.context_id)

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
        # This must also handle cases where no events were made after parent_pointer
        # and thus must correctly detect, in that case, that `last_ev_pointer` *is* the
        # parent_pointer.
        last_ev_pointer = await self.trigger_stop(
            agent_id=agent_id,
            stop_method=stop_method,
            anchor_pointer=parent_pointer,
        )
        await self._agent_mgrs[agent_id].add_user_message(
            message=message,
            parent_pointer=last_ev_pointer,
        )
