"""Session-agent service API."""

from sqlalchemy import select

from operator_db.objects.agent.entity import SessionAgentEnt
from operator_db.objects.agent.schema import AgentRequestSchema, AgentResponseSchema
from operator_db.objects.history.entity import HistoryEnt
from operator_db.utils.services import BaseService, DbSession


class SessionAgentService(BaseService):
    """Service for session-scoped agents."""

    async def create_agent(
        self,
        *,
        request: AgentRequestSchema,
        db_session: DbSession | None = None,
    ) -> AgentResponseSchema:
        """Create a session agent and its history."""
        async with self.session(db_session) as session:
            history_ent = HistoryEnt()
            agent_ent = SessionAgentEnt(
                session_id=request.session_id,
                local_id=request.local_id,
                model=request.model,
                system_prompt=request.system_prompt,
                serialized_permissions=request.serialized_permissions,
                title=request.title,
                description=request.description,
                extra_detail=request.extra_detail,
                history=history_ent,
            )
            session.add_all([history_ent, agent_ent])
            await session.flush()
            await session.refresh(agent_ent)
            return AgentResponseSchema.model_validate(agent_ent)

    async def get_agent(
        self,
        *,
        agent_id: str,
        db_session: DbSession | None = None,
    ) -> AgentResponseSchema | None:
        """Return an agent by database ID."""
        async with self.session(db_session, transaction=False) as session:
            agent_ent = await session.get(SessionAgentEnt, agent_id)
            if agent_ent is None:
                return None
            return AgentResponseSchema.model_validate(agent_ent)

    async def get_agent_by_local_id(
        self,
        *,
        session_id: str,
        local_id: str,
        db_session: DbSession | None = None,
    ) -> AgentResponseSchema | None:
        """Return an agent by session-local ID."""
        async with self.session(db_session, transaction=False) as session:
            result = await session.execute(
                select(SessionAgentEnt).where(
                    SessionAgentEnt.session_id == session_id,
                    SessionAgentEnt.local_id == local_id,
                )
            )
            agent_ent = result.scalar_one_or_none()
            if agent_ent is None:
                return None
            return AgentResponseSchema.model_validate(agent_ent)

    async def list_agents(
        self,
        *,
        session_id: str,
        db_session: DbSession | None = None,
    ) -> list[AgentResponseSchema]:
        """List agents in a session."""
        async with self.session(db_session, transaction=False) as session:
            result = await session.execute(
                select(SessionAgentEnt)
                .where(SessionAgentEnt.session_id == session_id)
                .order_by(SessionAgentEnt.local_id)
            )
            return [
                AgentResponseSchema.model_validate(agent_ent)
                for agent_ent in result.scalars().all()
            ]


__all__ = ["SessionAgentService"]
