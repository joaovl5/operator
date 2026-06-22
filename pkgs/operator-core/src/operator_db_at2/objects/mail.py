from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IDType, Repo
from .constants import TXT_SHORT, TxtLarge, TxtShort

if TYPE_CHECKING:
    from .session_agent import SessionAgent


class MailMessageState(StrEnum):
    QUEUED = "queued"
    READ = "read"


class MailMessage(Base):
    __tablename__ = "mail_messages"

    title: Mapped[TxtShort]
    body: Mapped[TxtLarge]

    mappings: Mapped[list[MailMapping]] = relationship(
        back_populates="message",
        lazy="raise",
    )


class MailMessageRepo(Repo[MailMessage]):
    model_type = MailMessage


class MailMapping(Base):
    """Intermediary table for mail relationships."""

    __tablename__ = "mail_mappings"
    __table_args__ = (
        Index(
            "ix_mail_sender",
            "sender_id",
        ),
        Index(
            "ix_mail_receiver_state",
            "receiver_id",
            "state",
        ),
    )

    message_id: Mapped[IDType] = mapped_column(
        ForeignKey("mail_messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    message: Mapped[MailMessage] = relationship(
        uselist=False,
        back_populates="mappings",
        lazy="selectin",
    )

    sender_id: Mapped[IDType] = mapped_column(
        ForeignKey("session_agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sender: Mapped[SessionAgent] = relationship(
        uselist=False,
        back_populates="mail_sent",
        lazy="selectin",
    )

    receiver_id: Mapped[IDType] = mapped_column(
        ForeignKey("session_agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    receiver: Mapped[SessionAgent] = relationship(
        uselist=False,
        back_populates="mail_received",
        lazy="selectin",
    )

    state: Mapped[MailMessageState] = mapped_column(
        String(TXT_SHORT),
        nullable=False,
        default=MailMessageState.QUEUED,
    )


class MailMappingRepo(Repo[MailMapping]):
    model_type = MailMapping
