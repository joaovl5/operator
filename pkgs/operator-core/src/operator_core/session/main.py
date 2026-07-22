from asyncio import Event, Lock, Task, create_task
from time import time
from typing import TYPE_CHECKING, Any

from attrs import Factory, define, field
from pydantic_ai import Agent, AgentRunResultEvent, ModelMessage
from pydantic_ai.models.openai import OpenAIChatModel

from operator_core.events.transform import events_to_msgs
from operator_core.session.agent import (
  AgentType,
  ToolDeps,
)
from operator_core.session.events import (
  AgentTurnEnd,
  AgentTurnStart,
  SessionEventSink,
  SessionEventType,
  from_pyai_event,
)
from operator_core.session.types import (
  EventPointer,
  IncomingMessage,
  StopAgentMethod,
)
from operator_db.objects import (
  ContextEvent,
  Session,
  SessionAgent,
  SessionAgentSvc,
  SessionSvc,
)
from operator_db.objects.context_event import from_pyai_msg

if TYPE_CHECKING:
  from collections.abc import Callable

  from pydantic_ai.models import Model
  from sqlalchemy.ext.asyncio import AsyncSession

  from operator_db.objects.base import IDType
  from operator_db.objects.context_event import CtxEvent
  from operator_shared.settings import OperatorSettings

type _AgentMap = dict[str, SessionAgent]
type _AgentManagerMap = dict[str, SessionAgentManager]
type _AgentLoopTaskMap = dict[str, Task[EventPointer]]


@define(kw_only=True)
class SessionAgentManager:
  """Proxy for db-side session-agent - stateful.

  This shouldn't hold state for long, and it should keep itself
  in-sync with database.
  """

  settings: OperatorSettings
  event_sink: SessionEventSink
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

  _has_run: bool = field(init=False, default=False)
  _pointer: EventPointer | None = field(init=False, default=None)
  _model: Model | None = field(init=False, default=None)
  _agent: AgentType | None = field(init=False, default=None)

  @property
  def has_run(self) -> bool:
    """Whether agent has started its loop at least once."""
    return self._has_run

  def _get_model_from_event(
    self,
    *,
    event: ContextEvent.UseModel,
  ) -> Model:
    provider = self.settings.providers.entries.get(
      event.model_provider
    )
    if not provider:
      msg = f"Missing model provider: `{event.model_provider}`"
      raise ValueError(msg)

    return OpenAIChatModel(
      model_name=event.model_name,
      provider=provider.get_pydantic_ai_provider(),
    )

  def _get_deps(self) -> ToolDeps:
    """ToolDeps for agent."""
    return ToolDeps(
      settings=self.settings,
      db_session=self.db_session,
      db_obj=self.db_obj,
    )

  async def _get_model(
    self,
    *,
    force_refresh: bool = False,
  ) -> Model:
    """Return cached model or fetch history events to create one.

    If `force_refresh` is set, will fetch history regardless of
    caching or not.
    """
    if self._model and not force_refresh:
      return self._model
    pointer = await self.get_pointer()
    event: (
      ContextEvent.UseModel | None
    ) = await self.svc.event_svc.walk_up_to(
      event_id=pointer.event_id,
      stop_at=ContextEvent.UseModel,
      return_only_start=True,
    )
    if not event:
      # We always expect SOMETHING here at least, because we populate
      # the history at the start of session with this.
      msg = "Unexpectedly missing `UseModel` event."
      raise ValueError(msg)
    return self._get_model_from_event(event=event)

  async def _get_agent(self) -> AgentType:
    return Agent(
      model=await self._get_model(),
      deps_type=ToolDeps,
    )

  async def _get_msg_history(self) -> list[ModelMessage]:
    """Turn epoch into provider-safe Pydantic AI messages."""
    pointer = await self.get_pointer()
    events = await self.svc.event_svc.walk_up_to(
      event_id=pointer.event_id
    )
    return await events_to_msgs(events)

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

  def refresh(self, db_obj: SessionAgent) -> None:
    """Replace internal db-object."""
    self.db_obj = db_obj

  async def do_loop(self) -> EventPointer:
    """Perform agent loop until termination signal is triggered."""
    self._has_run = True
    self.loop_end_ev.clear()
    async with self.loop_lock:
      # For now, a "loop" is just a single turn.
      # PydanticAI already deals with loops.
      await self._do_turn()
    self.loop_end_ev.set()
    return await self.get_pointer()

  async def _do_turn(self) -> None:
    """Perform a single agent turn."""
    self.turn_end_ev.clear()
    self._emit(AgentTurnStart)
    async with self.turn_lock:
      await self._do_turn_locked()

    self.turn_end_ev.set()
    self._emit(AgentTurnEnd)

  def _emit[EvT: SessionEventType](
    self,
    event_cls: Callable[..., EvT],
    **kwargs: Any,
  ) -> None:
    kwargs |= {
      "agent_id": self._id,
    }
    if "extra_metadata" not in kwargs:
      kwargs["extra_metadata"] = {}
    kwargs["extra_metadata"] |= {
      "timestamp": time(),
    }
    event = event_cls(**kwargs)
    self.event_sink.handle(event)

  @property
  def _id(self) -> str:
    """Session-wide `agent_id`."""
    return self.db_obj.agent_id

  async def _do_turn_locked(self) -> None:
    """Handle turn operations while locked."""
    agent = await self._get_agent()
    pointer = await self.get_pointer()
    parent_id = pointer.event_id
    async with agent.run_stream_events(
      deps=self._get_deps(),
      message_history=await self._get_msg_history(),
    ) as stream:
      async for event in stream:
        for ev in from_pyai_event(agent_id=self._id, ev=event):
          self.event_sink.handle(ev)
        if not isinstance(event, AgentRunResultEvent):
          continue
        new_msgs = event.result.new_messages()
        for msg in new_msgs:
          persisted = await from_pyai_msg(
            msg=msg,
            context_id=self.db_obj.context_id,
            parent_id=parent_id,
            session=self.db_session,
          )
          parent_id = persisted[-1].id
        await self._sync_db_pointer(parent_id)  # calls `.commit`

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
    pointer = await self.get_pointer()
    events: list[CtxEvent] = await self.svc.event_svc.walk_up_to(
      event_id=pointer.event_id,
    )
    return events


@define(kw_only=True)
class SessionManager:
  """Management of a single session."""

  settings: OperatorSettings
  db_session: AsyncSession
  event_sink: SessionEventSink

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
  _agent_loop_tasks: _AgentLoopTaskMap = field(
    init=False, factory=dict
  )

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
        event_sink=self.event_sink,
        db_session=self.db_session,
        db_obj=db_agent,
      )

  async def refresh_agents(self) -> None:
    """Refreshes agents."""
    await self._ensure_ok()
    lst: list[
      SessionAgent
    ] = await self._obj.awaitable_attrs.session_agents
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
  ) -> EventPointer | None:
    """Trigger a stop for agent.

    Args:
        agent_id: Agent to be stopped.
        stop_method: Method to handle stopping process.
        anchor_pointer: Base pointer for performing last event search,
                        will be used
                        for a downward search.

    Returns:
        Pointer to last event from agent loop, or `None` if it has not
        changed.

    """
    await self.refresh_agents()
    mgr = self._agent_mgrs[agent_id]
    if not mgr.has_run:
      return None
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
        "While attempting to find last agent event, no event could "
        "be found. "
        "Has a fork somehow occured along the way?"
      )
      raise ValueError(msg)
    return EventPointer(event_id=out.id, context_id=out.context_id)

  async def get_agent_pointer(self, agent_id: str) -> EventPointer:
    """Get `EventPointer` for that agent."""
    await self.refresh_agents()
    return await self._agent_mgrs[agent_id].get_pointer()

  async def add_user_message(
    self,
    agent_id: str,
    message: IncomingMessage,
    parent_pointer: EventPointer | None = None,
    stop_method: StopAgentMethod = StopAgentMethod.WAIT_LOOP,
  ) -> None:
    """Adds a user message to an agent's context.

    This does not make the loop start/restart afterwards.

    If `parent_pointer` is None, will get agent pointer by calling the
    `get_agent_pointer` method.
    """
    # This must also handle cases where no events were made after
    # parent_pointer and thus must correctly detect, in that case,
    # that `last_ev_pointer` *is* the  parent_pointer.
    parent_pointer = parent_pointer or (
      await self.get_agent_pointer(agent_id)
    )
    last_ev_pointer = (
      await self.trigger_stop(
        agent_id=agent_id,
        stop_method=stop_method,
        anchor_pointer=parent_pointer,
      )
      # guards against `trigger_stop` "None" case, when agent has not
      # yet ran
      or parent_pointer
    )
    await self._agent_mgrs[agent_id].add_user_message(
      message=message,
      parent_pointer=last_ev_pointer,
    )
