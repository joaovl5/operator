from operator_db.objects.agent import AgentRequestSchema, SessionAgentService
from operator_db.objects.session import SessionRequestSchema, SessionService
from operator_db.utils.db.testing import tmp_sqlite_db


async def test_agent_service_creates_history_and_lists_agents_by_local_id() -> None:
    """Agent service creates histories and supports stable lookup/list operations."""
    async with tmp_sqlite_db() as db:
        sessions = SessionService()
        agents = SessionAgentService()
        session = await sessions.create_session(
            request=SessionRequestSchema(),
            db_session=db.sessionmaker,
        )

        created_beta = await agents.create_agent(
            request=AgentRequestSchema(
                session_id=session.id,
                local_id="beta",
                title="Beta",
            ),
            db_session=db.sessionmaker,
        )
        created_alpha = await agents.create_agent(
            request=AgentRequestSchema(
                session_id=session.id,
                local_id="alpha",
                title="Alpha",
            ),
            db_session=db.sessionmaker,
        )

        assert created_beta.history_id
        assert created_alpha.history_id

        fetched = await agents.get_agent(
            agent_id=created_beta.id,
            db_session=db.sessionmaker,
        )
        assert fetched == created_beta

        by_local = await agents.get_agent_by_local_id(
            session_id=session.id,
            local_id="alpha",
            db_session=db.sessionmaker,
        )
        assert by_local == created_alpha

        listed = await agents.list_agents(
            session_id=session.id,
            db_session=db.sessionmaker,
        )

        assert [agent.local_id for agent in listed] == ["alpha", "beta"]
