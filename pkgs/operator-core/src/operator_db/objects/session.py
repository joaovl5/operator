from typing import TYPE_CHECKING, Any

from sqlalchemy import select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from operator_db.objects.session_agent import SessionAgentSvc
from operator_shared.constants import ORCHESTRATOR_AGENT_ID

from .base import Base, Repo, Svc
from .constants import TxtShort  # noqa: TC001
from .session_agent import SessionAgent

if TYPE_CHECKING:
  from sqlalchemy.ext.asyncio import AsyncSession


class Session(Base):
  __tablename__ = "sessions"

  session_title: Mapped[TxtShort | None] = mapped_column(
    nullable=True
  )

  session_agents: Mapped[list[SessionAgent]] = relationship(
    back_populates="session",
  )

  async def get_agent_by_id(
    self,
    session: AsyncSession,
    agent_id: str,
  ) -> SessionAgent | None:
    """Gets this session's agent through its id."""
    query = (
      select(SessionAgent)
      .join(
        Session,
        SessionAgent.session_id == Session.id,
      )
      .where(
        SessionAgent.session_id == self.id,
        SessionAgent.agent_id == agent_id,
      )
      .limit(1)
    )
    return await session.scalar(query)

  async def get_orchestrator(
    self,
    session: AsyncSession,
    agent_id: str = ORCHESTRATOR_AGENT_ID,
  ) -> SessionAgent:
    """Gets this session's orchestrator, errors if not found."""
    agent = await self.get_agent_by_id(
      session=session,
      agent_id=agent_id,
    )
    if not agent:
      msg = "Couldn't find orchestrator agent for this session."
      raise ValueError(msg)
    return agent

  async def as_dict(self) -> dict[str, Any]:
    """Convert object to dictionary."""
    agents: list[SessionAgent] = await self.aw.session_agents
    return {
      "session_title": self.session_title,
      "session_agents": [await x.as_dict() for x in agents],
    }


class SessionRepo(Repo[Session]):
  model_type = Session


class SessionSvc(Svc[Session]):
  repository_type = SessionRepo

  @property
  def _agent_svc(self) -> SessionAgentSvc:
    return self._get_svc(SessionAgentSvc)

  def _mk_orchestrator_agent(self) -> dict[str, Any]:
    system_prompt = self._settings.agents.compute_effective_prompt(
      archetype="orchestrator",
    )
    model_preset = self._settings.get_archetype_model("orchestrator")
    permissions = self._settings.agents.archetypes[
      "orchestrator"
    ].permissions

    return self._agent_svc.bake_orchestrator_agent(
      system_prompt=system_prompt,
      model_name=model_preset.model_name,
      model_provider=model_preset.provider_key,
      permissions=permissions,
    )

  async def make_session(
    self,
    *,
    session_title: str | None = None,
    with_orchestrator: bool = True,
  ) -> Session:
    """Create a session and its dependencies.

    Args:
        session_title: If set, will use this session title.
        with_orchestrator: Whether to auto-generate an orchestrator
            agent.

    Returns:
        Created Session instance.
    """
    data: dict[str, Any] = {}
    if session_title:
      data["session_title"] = session_title
    if with_orchestrator:
      orch_agent = self._mk_orchestrator_agent()
      data["session_agents"] = [orch_agent]
    session = await self.create(
      data=data,
    )

    return session
