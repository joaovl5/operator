from enum import StrEnum
from typing import TYPE_CHECKING, Any

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
        lazy="immediate",
    )

    sender_id: Mapped[IDType] = mapped_column(
        ForeignKey("session_agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sender: Mapped[SessionAgent] = relationship(
        uselist=False,
        back_populates="mail_sent",
        foreign_keys=lambda: [MailMapping.sender_id],
        lazy="immediate",
    )

    receiver_id: Mapped[IDType] = mapped_column(
        ForeignKey("session_agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    receiver: Mapped[SessionAgent] = relationship(
        uselist=False,
        back_populates="mail_received",
        foreign_keys=lambda: [MailMapping.receiver_id],
        lazy="immediate",
    )

    state: Mapped[MailMessageState] = mapped_column(
        String(TXT_SHORT),
        nullable=False,
        default=MailMessageState.QUEUED,
    )

    async def as_dict(self) -> dict[str, Any]:
        """Convert object to dictionary."""
        return {
            "title": self.message.title,
            "body": self.message.body,
            "sender_agent_id": (await self._at.sender).agent_id,
            "receiver_agent_id": (await self._at.receiver).agent_id,
            "state": self.state.value,
        }


class MailMappingRepo(Repo[MailMapping]):
    model_type = MailMapping
