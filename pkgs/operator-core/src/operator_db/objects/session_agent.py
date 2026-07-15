from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from operator_db.objects import ContextEvent
from operator_shared.constants import ORCHESTRATOR_AGENT_ID

from .base import Base, IDType, Repo, Svc
from .constants import TxtShort  # noqa: TC001
from .context import AgentContext, AgentContextSvc
from .context_event import ContextEventSvc, CtxEvent, get_poly_id
from .mail import MailMapping
from .types import MsgRole

if TYPE_CHECKING:
  from pydantic import JsonValue

  from .session import Session


class SessionAgent(Base):
  __tablename__ = "session_agents"

  agent_id: Mapped[TxtShort] = mapped_column(index=True)

  context_id: Mapped[IDType] = mapped_column(
    ForeignKey("contexts.id"),
    index=True,
  )
  context: Mapped[AgentContext] = relationship(
    uselist=False,
    back_populates="agent",
    lazy="immediate",
  )

  session_id: Mapped[IDType] = mapped_column(
    ForeignKey("sessions.id"),
    index=True,
  )
  session: Mapped[Session] = relationship(
    uselist=False,
    back_populates="session_agents",
    lazy="immediate",
  )

  mail_sent: Mapped[list[MailMapping]] = relationship(
    back_populates="sender",
    foreign_keys=lambda: [MailMapping.sender_id],
  )
  mail_received: Mapped[list[MailMapping]] = relationship(
    back_populates="receiver",
    foreign_keys=lambda: [MailMapping.receiver_id],
  )

  async def as_dict(self) -> dict[str, Any]:
    """Convert object to dictionary."""
    mail_sent: list[MailMapping] = await self.aw.mail_sent
    mail_received: list[MailMapping] = await self.aw.mail_received
    return {
      "agent_id": await self.aw.agent_id,
      "context": await (await self.aw.context).as_dict(),
      "mail_sent": [await x.as_dict() for x in mail_sent],
      "mail_received": [await x.as_dict() for x in mail_received],
    }


class SessionAgentRepo(Repo[SessionAgent]):
  model_type = SessionAgent


class SessionAgentSvc(Svc[SessionAgent]):
  repository_type = SessionAgentRepo

  @property
  def event_svc(self) -> ContextEventSvc:
    """Event service instance."""
    return self._get_svc(ContextEventSvc)

  @property
  def ctx_svc(self) -> AgentContextSvc:
    """Context service instance."""
    return self._get_svc(AgentContextSvc)

  def _bake_initial_events(
    self,
    *,
    system_prompt: str,
    model_name: str,
    model_provider: str,
    permissions: dict[str, Any],
  ) -> list[ContextEvent.Type]:
    """Make initial set of events for the first epoch."""
    _base: list[ContextEvent.Type] = [
      ContextEvent.ChatStart(),
      ContextEvent.EpochStart(),
      ContextEvent.Message(role=MsgRole.SYSTEM, text=system_prompt),
      ContextEvent.UsePermissions(data=permissions),
      ContextEvent.UseModel(
        model_name=model_name, model_provider=model_provider
      ),
    ]

    self.event_svc.bake_into_tree(_base)

    return _base

  def bake_orchestrator_agent(
    self,
    *,
    agent_id: str = ORCHESTRATOR_AGENT_ID,
    system_prompt: str,
    model_name: str,
    model_provider: str,
    permissions: dict[str, Any],
  ) -> dict[str, Any]:
    """Bake data for making an orchestrator agent as part of a larger query."""
    events = self._bake_initial_events(
      system_prompt=system_prompt,
      model_name=model_name,
      model_provider=model_provider,
      permissions=permissions,
    )

    return {
      "agent_id": agent_id,
      "context": {
        "events": events,
        "pointer_event": events[-1],
      },
    }

  async def add_message(  # noqa: PLR0913
    self,
    *,
    parent_id: IDType,
    context_id: IDType,
    text_data: str | None = None,
    json_data: JsonValue | None = None,
    bytes_data: bytes | None = None,
    role: MsgRole = MsgRole.USER,
  ) -> ContextEvent.Message:
    """Add a message."""
    msg_ev = ContextEvent.Message(
      role=role,
      text=text_data,
      json=json_data,
      binary_contents=bytes_data,
      parent_id=parent_id,
      context_id=context_id,
    )
    self._session.add(msg_ev)
    await self._session.commit()
    await self._session.refresh(msg_ev, attribute_names=("id",))
    return msg_ev

  async def get_last_event(
    self, *, agent: SessionAgent
  ) -> CtxEvent | None:
    """Return last event or `None` if forks are found along the way."""
    query = (
      select(CtxEvent)
      .where(
        CtxEvent.context_id == agent.context_id,
        CtxEvent.type == get_poly_id(ContextEvent.ChatStart),
      )
      .limit(1)
    )

    res = await self._session.scalar(query)

    if not res:
      msg = "Session doesn't have a `ChatStart` event!"
      raise ValueError(msg)

    return await self.event_svc.walk_down_unforked(
      anchor_event_id=res.id
    )
