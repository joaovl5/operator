"""Mail service API."""

from typing import TYPE_CHECKING

from operator_db.utils.services import BaseService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from operator_db.objects.mail.schema import (
        MailDeliveryResponseSchema,
        MailRequestSchema,
        MailResponseSchema,
    )


class MailService(BaseService):
    """Service for agent-to-agent mail delivery."""

    async def queue_message(
        self,
        *,
        request: MailRequestSchema,
        db_session: AsyncSession | None = None,
    ) -> MailResponseSchema:
        """Queue one message for one or more receivers."""
        _ = (..., request, db_session)
        raise NotImplementedError

    async def claim_inbox(
        self,
        *,
        session_id: str,
        receiver_local_id: str,
        db_session: AsyncSession | None = None,
    ) -> list[MailResponseSchema]:
        """Return queued messages and mark deliveries read."""
        _ = (..., session_id, receiver_local_id, db_session)
        raise NotImplementedError

    async def render_mailbox(
        self,
        *,
        session_id: str,
        receiver_local_id: str,
        reverse_order: bool = False,
        db_session: AsyncSession | None = None,
    ) -> list[MailResponseSchema]:
        """Return visible mailbox messages without mutating state."""
        _ = (..., session_id, receiver_local_id, reverse_order, db_session)
        raise NotImplementedError

    async def mark_delivery_read(
        self,
        *,
        session_id: str,
        mail_message_id: str,
        sender_local_id: str,
        receiver_local_id: str,
        db_session: AsyncSession | None = None,
    ) -> MailDeliveryResponseSchema:
        """Mark one delivery row as read."""
        _ = (..., session_id, mail_message_id, sender_local_id, receiver_local_id, db_session)
        raise NotImplementedError


__all__ = ["MailService"]
