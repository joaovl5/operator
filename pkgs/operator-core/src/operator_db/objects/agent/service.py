"""Session-agent service API."""

from typing import TYPE_CHECKING

from operator_db.utils.services import BaseService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from operator_db.objects.agent.schema import AgentRequestSchema, AgentResponseSchema


class SessionAgentService(BaseService):
    """Service for session-scoped agents."""

    async def create_agent(
        self,
        *,
        request: AgentRequestSchema,
        db_session: AsyncSession | None = None,
    ) -> AgentResponseSchema:
        """Create a session agent and its history."""
        _ = (..., request, db_session)
        raise NotImplementedError

    async def get_agent(
        self,
        *,
        agent_id: str,
        db_session: AsyncSession | None = None,
    ) -> AgentResponseSchema | None:
        """Return an agent by database ID."""
        _ = (..., agent_id, db_session)
        raise NotImplementedError

    async def get_agent_by_local_id(
        self,
        *,
        session_id: str,
        local_id: str,
        db_session: AsyncSession | None = None,
    ) -> AgentResponseSchema | None:
        """Return an agent by session-local ID."""
        _ = (..., session_id, local_id, db_session)
        raise NotImplementedError

    async def list_agents(
        self,
        *,
        session_id: str,
        db_session: AsyncSession | None = None,
    ) -> list[AgentResponseSchema]:
        """List agents in a session."""
        _ = (..., session_id, db_session)
        raise NotImplementedError


__all__ = ["SessionAgentService"]
