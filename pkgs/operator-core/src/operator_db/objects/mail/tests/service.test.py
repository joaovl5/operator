import pytest

from operator_db.constants.mail import MailMessageState
from operator_db.objects.agent import AgentRequestSchema, SessionAgentService
from operator_db.objects.mail import MailRequestSchema, MailService
from operator_db.objects.session import SessionRequestSchema, SessionService
from operator_db.utils.db.testing import tmp_sqlite_db


async def test_mail_service_queues_claims_and_renders_mail() -> None:
    """Mail service queues messages, claims inboxes, and renders stable mailbox views."""
    async with tmp_sqlite_db() as db:
        sessions = SessionService()
        agents = SessionAgentService()
        mail = MailService()

        session = await sessions.create_session(
            request=SessionRequestSchema(),
            db_session=db.sessionmaker,
        )
        _ = await agents.create_agent(
            request=AgentRequestSchema(session_id=session.id, local_id="sender"),
            db_session=db.sessionmaker,
        )
        _ = await agents.create_agent(
            request=AgentRequestSchema(session_id=session.id, local_id="receiver"),
            db_session=db.sessionmaker,
        )

        first = await mail.queue_message(
            request=MailRequestSchema(
                session_id=session.id,
                sender_local_ids=["sender", "sender"],
                receiver_local_ids=["receiver", "receiver"],
                body="hello",
            ),
            db_session=db.sessionmaker,
        )
        second = await mail.queue_message(
            request=MailRequestSchema(
                session_id=session.id,
                sender_local_ids=["sender"],
                receiver_local_ids=["receiver"],
                body="follow-up",
            ),
            db_session=db.sessionmaker,
        )

        assert first.body == "hello"
        assert [delivery.receiver_local_id for delivery in first.deliveries] == ["receiver"]
        assert [delivery.sender_local_id for delivery in first.deliveries] == ["sender"]

        rendered = await mail.render_mailbox(
            session_id=session.id,
            receiver_local_id="receiver",
            db_session=db.sessionmaker,
        )
        assert [message.id for message in rendered] == [first.id, second.id]

        rendered_reverse = await mail.render_mailbox(
            session_id=session.id,
            receiver_local_id="receiver",
            reverse_order=True,
            db_session=db.sessionmaker,
        )
        assert [message.id for message in rendered_reverse] == [second.id, first.id]

        claimed = await mail.claim_inbox(
            session_id=session.id,
            receiver_local_id="receiver",
            db_session=db.sessionmaker,
        )
        assert [message.id for message in claimed] == [first.id, second.id]

        claimed_again = await mail.claim_inbox(
            session_id=session.id,
            receiver_local_id="receiver",
            db_session=db.sessionmaker,
        )
        assert claimed_again == []

        rendered_after_claim = await mail.render_mailbox(
            session_id=session.id,
            receiver_local_id="receiver",
            db_session=db.sessionmaker,
        )
        assert [message.id for message in rendered_after_claim] == [first.id, second.id]
        assert all(
            delivery.state is MailMessageState.READ
            for message in rendered_after_claim
            for delivery in message.deliveries
            if delivery.receiver_local_id == "receiver"
        )


async def test_mail_service_marks_specific_delivery_read_and_rejects_empty_participants() -> None:
    """Mail service rejects empty participants and updates one receiver delivery at a time."""
    async with tmp_sqlite_db() as db:
        sessions = SessionService()
        agents = SessionAgentService()
        mail = MailService()

        session = await sessions.create_session(
            request=SessionRequestSchema(),
            db_session=db.sessionmaker,
        )
        _ = await agents.create_agent(
            request=AgentRequestSchema(session_id=session.id, local_id="sender"),
            db_session=db.sessionmaker,
        )
        _ = await agents.create_agent(
            request=AgentRequestSchema(session_id=session.id, local_id="receiver-a"),
            db_session=db.sessionmaker,
        )
        _ = await agents.create_agent(
            request=AgentRequestSchema(session_id=session.id, local_id="receiver-b"),
            db_session=db.sessionmaker,
        )

        with pytest.raises(ValueError, match="sender"):
            _ = await mail.queue_message(
                request=MailRequestSchema(
                    session_id=session.id,
                    sender_local_ids=[],
                    receiver_local_ids=["receiver-a"],
                    body="missing sender",
                ),
                db_session=db.sessionmaker,
            )

        with pytest.raises(ValueError, match="receiver"):
            _ = await mail.queue_message(
                request=MailRequestSchema(
                    session_id=session.id,
                    sender_local_ids=["sender"],
                    receiver_local_ids=[],
                    body="missing receiver",
                ),
                db_session=db.sessionmaker,
            )

        queued = await mail.queue_message(
            request=MailRequestSchema(
                session_id=session.id,
                sender_local_ids=["sender"],
                receiver_local_ids=["receiver-a", "receiver-b"],
                body="fanout",
            ),
            db_session=db.sessionmaker,
        )

        marked = await mail.mark_delivery_read(
            session_id=session.id,
            mail_message_id=queued.id,
            sender_local_id="sender",
            receiver_local_id="receiver-b",
            db_session=db.sessionmaker,
        )
        assert marked.receiver_local_id == "receiver-b"
        assert marked.state is MailMessageState.READ

        claimed_a = await mail.claim_inbox(
            session_id=session.id,
            receiver_local_id="receiver-a",
            db_session=db.sessionmaker,
        )
        assert [message.id for message in claimed_a] == [queued.id]

        claimed_b = await mail.claim_inbox(
            session_id=session.id,
            receiver_local_id="receiver-b",
            db_session=db.sessionmaker,
        )
        assert claimed_b == []

        rendered_b = await mail.render_mailbox(
            session_id=session.id,
            receiver_local_id="receiver-b",
            db_session=db.sessionmaker,
        )
        assert [message.id for message in rendered_b] == [queued.id]
        receiver_b_delivery = next(
            delivery
            for delivery in rendered_b[0].deliveries
            if delivery.receiver_local_id == "receiver-b"
        )
        assert receiver_b_delivery.state is MailMessageState.READ
