"""Mail entities."""

from typing import TYPE_CHECKING, final

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from operator_db.constants import SHORT_STR_LEN
from operator_db.constants.mail import MailMessageState
from operator_db.utils.db.base import Base, Entity
from operator_db.utils.db.mixins import ArbitraryMetadata, OptStr, ReqStrLong  # noqa: TC001
from operator_db.utils.json import JsonValue

if TYPE_CHECKING:
    from operator_db.objects.agent.entity import SessionAgentEnt

_JSON_VALUE = JsonValue


@final
class MailMessageEnt(Entity):
    """Mailbox message."""

    __tablename__ = "mail_messages"

    title: Mapped[OptStr]
    body: Mapped[ReqStrLong]
    extra_metadata: Mapped[ArbitraryMetadata]

    mailbox_mappings: Mapped[list[MailboxMapping]] = relationship(
        "MailboxMapping",
        back_populates="mail_message",
        cascade="save-update, merge, delete, delete-orphan",
    )
    """Delivery rows for this mail message."""


@final
class MailboxMapping(Base):
    """Intermediary table for saving mail relationships."""

    __tablename__ = "mailbox_mappings"
    __table_args__ = (
        Index(
            "ix_mailbox_mappings_sender_agent_id",
            "sender_agent_id",
        ),
        Index(
            "ix_mailbox_mappings_receiver_agent_id_state",
            "receiver_agent_id",
            "state",
        ),
    )

    mail_message_id: Mapped[str] = mapped_column(
        ForeignKey("mail_messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sender_agent_id: Mapped[str] = mapped_column(
        ForeignKey("session_agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    receiver_agent_id: Mapped[str] = mapped_column(
        ForeignKey("session_agents.id", ondelete="CASCADE"),
        primary_key=True,
    )

    state: Mapped[MailMessageState] = mapped_column(
        String(SHORT_STR_LEN),
        nullable=False,
        default=MailMessageState.QUEUED,
    )
    """Per-receiver state for this mail delivery."""

    mail_message: Mapped[MailMessageEnt] = relationship(
        "MailMessageEnt",
        back_populates="mailbox_mappings",
    )
    """Message delivered by this row."""

    sender_agent: Mapped[SessionAgentEnt] = relationship(
        "SessionAgentEnt",
        back_populates="sent_mail_mappings",
        foreign_keys=lambda: [MailboxMapping.sender_agent_id],
    )
    """Agent sending this delivery row."""

    receiver_agent: Mapped[SessionAgentEnt] = relationship(
        "SessionAgentEnt",
        back_populates="received_mail_mappings",
        foreign_keys=lambda: [MailboxMapping.receiver_agent_id],
    )
    """Agent receiving this delivery row."""

    # Same-session semantics are validated before persistence; portable SQL constraints
    # cannot compare sender/receiver session_id through referenced rows without storing
    # session_id here or using database-specific triggers.
