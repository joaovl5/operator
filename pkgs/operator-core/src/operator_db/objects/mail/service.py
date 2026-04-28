"""Mail service API."""

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from operator_db.constants.mail import MailMessageState
from operator_db.objects.agent.entity import SessionAgentEnt
from operator_db.objects.mail.entity import MailboxMapping, MailMessageEnt
from operator_db.objects.mail.schema import (
    MailDeliveryResponseSchema,
    MailRequestSchema,
    MailResponseSchema,
)
from operator_db.utils.services import BaseService, DbSession

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from operator_db.utils.json import JsonValue


class MailService(BaseService):
    """Service for agent-to-agent mail delivery."""

    async def queue_message(
        self,
        *,
        request: MailRequestSchema,
        db_session: DbSession | None = None,
    ) -> MailResponseSchema:
        """Queue one message for one or more receivers."""
        sender_local_ids = self._unique_local_ids(
            request.sender_local_ids,
            empty_message="sender_local_ids must not be empty",
        )
        receiver_local_ids = self._unique_local_ids(
            request.receiver_local_ids,
            empty_message="receiver_local_ids must not be empty",
        )

        async with self.session(db_session) as session:
            sender_agents = await self._resolve_agents(
                session,
                session_id=request.session_id,
                local_ids=sender_local_ids,
            )
            receiver_agents = await self._resolve_agents(
                session,
                session_id=request.session_id,
                local_ids=receiver_local_ids,
            )

            timestamp = datetime.now(UTC).replace(tzinfo=None)
            message_ent = MailMessageEnt(
                title=request.title,
                body=request.body,
                extra_metadata=request.extra_metadata,
                created_at=timestamp,
                updated_at=timestamp,
            )
            mappings = [
                MailboxMapping(
                    mail_message=message_ent,
                    sender_agent_id=sender_agent.id,
                    receiver_agent_id=receiver_agent.id,
                )
                for sender_agent in sender_agents.values()
                for receiver_agent in receiver_agents.values()
            ]
            session.add(message_ent)
            session.add_all(mappings)
            await session.flush()

            loaded = await self._get_message(session, mail_message_id=message_ent.id)
            return self._to_mail_response(loaded)

    async def claim_inbox(
        self,
        *,
        session_id: str,
        receiver_local_id: str,
        db_session: DbSession | None = None,
    ) -> list[MailResponseSchema]:
        """Return queued messages and mark deliveries read."""
        async with self.session(db_session) as session:
            receiver_agent = await self._resolve_agent(
                session,
                session_id=session_id,
                local_id=receiver_local_id,
            )
            messages = await self._list_messages_for_receiver(
                session,
                receiver_agent_id=receiver_agent.id,
                queued_only=True,
            )

            for message_ent in messages:
                for delivery in message_ent.mailbox_mappings:
                    if (
                        delivery.receiver_agent_id == receiver_agent.id
                        and delivery.state == MailMessageState.QUEUED
                    ):
                        delivery.state = MailMessageState.READ

            await session.flush()
            return [self._to_mail_response(message_ent) for message_ent in messages]

    async def render_mailbox(
        self,
        *,
        session_id: str,
        receiver_local_id: str,
        reverse_order: bool = False,
        db_session: DbSession | None = None,
    ) -> list[MailResponseSchema]:
        """Return visible mailbox messages without mutating state."""
        async with self.session(db_session, transaction=False) as session:
            receiver_agent = await self._resolve_agent(
                session,
                session_id=session_id,
                local_id=receiver_local_id,
            )
            messages = await self._list_messages_for_receiver(
                session,
                receiver_agent_id=receiver_agent.id,
                reverse_order=reverse_order,
            )
            return [self._to_mail_response(message_ent) for message_ent in messages]

    async def mark_delivery_read(
        self,
        *,
        session_id: str,
        mail_message_id: str,
        sender_local_id: str,
        receiver_local_id: str,
        db_session: DbSession | None = None,
    ) -> MailDeliveryResponseSchema:
        """Mark one delivery row as read."""
        async with self.session(db_session) as session:
            sender_agent, receiver_agent = await self._resolve_sender_receiver_agents(
                session,
                session_id=session_id,
                sender_local_id=sender_local_id,
                receiver_local_id=receiver_local_id,
            )
            delivery = await session.get(
                MailboxMapping,
                (mail_message_id, sender_agent.id, receiver_agent.id),
            )
            if delivery is None:
                message = (
                    "mail delivery not found for "
                    f"message={mail_message_id}, sender={sender_local_id}, receiver={receiver_local_id}"
                )
                raise LookupError(message)

            delivery.state = MailMessageState.READ
            await session.flush()
            return self._to_delivery_response(
                delivery,
                sender_local_id=sender_agent.local_id,
                receiver_local_id=receiver_agent.local_id,
            )

    async def _resolve_sender_receiver_agents(
        self,
        session: AsyncSession,
        *,
        session_id: str,
        sender_local_id: str,
        receiver_local_id: str,
    ) -> tuple[SessionAgentEnt, SessionAgentEnt]:
        sender_agent = await self._resolve_agent(
            session,
            session_id=session_id,
            local_id=sender_local_id,
        )
        receiver_agent = await self._resolve_agent(
            session,
            session_id=session_id,
            local_id=receiver_local_id,
        )
        return sender_agent, receiver_agent

    async def _resolve_agent(
        self,
        session: AsyncSession,
        *,
        session_id: str,
        local_id: str,
    ) -> SessionAgentEnt:
        agents = await self._resolve_agents(
            session,
            session_id=session_id,
            local_ids=(local_id,),
        )
        return agents[local_id]

    async def _resolve_agents(
        self,
        session: AsyncSession,
        *,
        session_id: str,
        local_ids: tuple[str, ...],
    ) -> dict[str, SessionAgentEnt]:
        agent_result = await session.scalars(
            select(SessionAgentEnt).where(
                SessionAgentEnt.session_id == session_id,
                SessionAgentEnt.local_id.in_(local_ids),
            )
        )
        agent_list = list(agent_result)
        agents = {agent.local_id: agent for agent in agent_list}
        missing_local_ids = [local_id for local_id in local_ids if local_id not in agents]
        if missing_local_ids:
            message = f"unknown session-local agents for session {session_id}: {', '.join(missing_local_ids)}"
            raise LookupError(message)
        return agents

    async def _get_message(
        self,
        session: AsyncSession,
        *,
        mail_message_id: str,
    ) -> MailMessageEnt:
        message_ent = await session.scalar(
            select(MailMessageEnt)
            .where(MailMessageEnt.id == mail_message_id)
            .options(
                selectinload(MailMessageEnt.mailbox_mappings).selectinload(MailboxMapping.sender_agent),
                selectinload(MailMessageEnt.mailbox_mappings).selectinload(MailboxMapping.receiver_agent),
            )
        )
        if message_ent is None:
            message = f"mail message not found: {mail_message_id}"
            raise LookupError(message)
        return message_ent

    async def _list_messages_for_receiver(
        self,
        session: AsyncSession,
        *,
        receiver_agent_id: str,
        queued_only: bool = False,
        reverse_order: bool = False,
    ) -> list[MailMessageEnt]:
        order_by = MailMessageEnt.created_at.desc() if reverse_order else MailMessageEnt.created_at.asc()
        stmt = (
            select(MailMessageEnt)
            .join(MailboxMapping, MailboxMapping.mail_message_id == MailMessageEnt.id)
            .where(MailboxMapping.receiver_agent_id == receiver_agent_id)
            .order_by(order_by, MailMessageEnt.id)
            .options(
                selectinload(MailMessageEnt.mailbox_mappings).selectinload(MailboxMapping.sender_agent),
                selectinload(MailMessageEnt.mailbox_mappings).selectinload(MailboxMapping.receiver_agent),
            )
        )
        if queued_only:
            stmt = stmt.where(MailboxMapping.state == MailMessageState.QUEUED)

        message_result = await session.scalars(stmt)
        return list(message_result.unique().all())

    def _to_mail_response(self, message_ent: MailMessageEnt) -> MailResponseSchema:
        return MailResponseSchema(
            id=message_ent.id,
            title=message_ent.title,
            body=message_ent.body,
            extra_metadata=self._copy_extra_metadata(message_ent.extra_metadata),
            created_at=message_ent.created_at,
            updated_at=message_ent.updated_at,
            deliveries=[self._to_delivery_response(delivery) for delivery in message_ent.mailbox_mappings],
        )

    def _to_delivery_response(
        self,
        delivery: MailboxMapping,
        *,
        sender_local_id: str | None = None,
        receiver_local_id: str | None = None,
    ) -> MailDeliveryResponseSchema:
        resolved_sender_local_id = sender_local_id
        if resolved_sender_local_id is None:
            resolved_sender_local_id = delivery.sender_agent.local_id

        resolved_receiver_local_id = receiver_local_id
        if resolved_receiver_local_id is None:
            resolved_receiver_local_id = delivery.receiver_agent.local_id

        return MailDeliveryResponseSchema(
            mail_message_id=delivery.mail_message_id,
            sender_agent_id=delivery.sender_agent_id,
            receiver_agent_id=delivery.receiver_agent_id,
            sender_local_id=resolved_sender_local_id,
            receiver_local_id=resolved_receiver_local_id,
            state=delivery.state,
        )

    def _copy_extra_metadata(self, source: dict[str, JsonValue]) -> dict[str, object]:
        return dict[str, object](source)


    def _unique_local_ids(
        self,
        local_ids: list[str] | tuple[str, ...],
        *,
        empty_message: str,
    ) -> tuple[str, ...]:
        unique_local_ids = tuple(dict.fromkeys(local_ids))
        if not unique_local_ids:
            raise ValueError(empty_message)
        return unique_local_ids


__all__ = ["MailService"]
