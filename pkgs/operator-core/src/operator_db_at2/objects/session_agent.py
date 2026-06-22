from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IDType, Repo
from .constants import TxtShort  # noqa: TC001

if TYPE_CHECKING:
    from .history import History
    from .mail import MailMapping
    from .session import Session


class SessionAgent(Base):
    __tablename__ = "session_agents"

    agent_id: Mapped[TxtShort] = mapped_column(index=True)

    # IMPORTANT:
    # We only set `history_id` for the *main* or initial branch.
    # Any forks and their relations go into History.forked_from_id
    history_id: Mapped[IDType] = mapped_column(
        ForeignKey("histories.id"),
        index=True,
    )
    history: Mapped[History] = relationship(
        uselist=False,
        back_populates="session_agent",
        lazy="selectin",
    )

    session_id: Mapped[IDType] = mapped_column(
        ForeignKey("sessions.id"),
        index=True,
    )
    session: Mapped[Session] = relationship(
        uselist=False,
        back_populates="session_agents",
        lazy="selectin",
    )

    mail_sent: Mapped[list[MailMapping]] = relationship(
        back_populates="sender",
        lazy="raise",
    )
    mail_received: Mapped[list[MailMapping]] = relationship(
        back_populates="receiver",
        lazy="raise",
    )


class SessionAgentRepo(Repo[SessionAgent]):
    model_type = SessionAgent
