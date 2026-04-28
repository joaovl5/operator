from operator_db.constants.role import HistoryMessageRole
from operator_db.objects.agent import AgentRequestSchema, SessionAgentService
from operator_db.objects.history import HistoryMessageRequestSchema, HistoryService
from operator_db.objects.session import SessionRequestSchema, SessionService
from operator_db.utils.db.testing import tmp_sqlite_db


async def test_history_service_appends_ordered_messages_and_compaction_links() -> None:
    """History service appends ordered messages and exposes compaction links."""
    async with tmp_sqlite_db() as db:
        sessions = SessionService()
        agents = SessionAgentService()
        history = HistoryService()

        session = await sessions.create_session(
            request=SessionRequestSchema(),
            db_session=db.sessionmaker,
        )
        agent = await agents.create_agent(
            request=AgentRequestSchema(session_id=session.id, local_id="worker"),
            db_session=db.sessionmaker,
        )

        first = await history.append_message(
            history_id=agent.history_id,
            request=HistoryMessageRequestSchema(
                role=HistoryMessageRole.USER,
                text_contents="one",
            ),
            db_session=db.sessionmaker,
        )
        second = await history.append_message(
            history_id=agent.history_id,
            request=HistoryMessageRequestSchema(
                role=HistoryMessageRole.AGENT_SELF,
                text_contents="two",
            ),
            compacted_message_ids=[first.id],
            db_session=db.sessionmaker,
        )

        next_epoch = await history.create_next_epoch(
            history_id=agent.history_id,
            db_session=db.sessionmaker,
        )
        third = await history.append_message(
            history_id=agent.history_id,
            request=HistoryMessageRequestSchema(
                role=HistoryMessageRole.AGENT_SELF,
                text_contents="three",
            ),
            db_session=db.sessionmaker,
        )

        fetched_history = await history.get_history(
            history_id=agent.history_id,
            db_session=db.sessionmaker,
        )
        history_for_agent = await history.get_history_for_agent(
            session_id=session.id,
            agent_local_id="worker",
            db_session=db.sessionmaker,
        )
        messages = await history.list_messages(
            history_id=agent.history_id,
            db_session=db.sessionmaker,
        )
        epoch_messages = await history.list_messages(
            history_id=agent.history_id,
            epoch_iteration=next_epoch.epoch_iteration,
            db_session=db.sessionmaker,
        )

        assert fetched_history is not None
        assert history_for_agent == fetched_history
        assert next_epoch.epoch_iteration == 1
        assert [message.message_index for message in messages] == [0, 1, 0]
        assert [message.id for message in messages] == [first.id, second.id, third.id]
        assert epoch_messages == [third]
        assert messages[0].compacted_by_id == second.id
