from typing import TYPE_CHECKING

from sqlalchemy.orm import Mapped, relationship

from .base import Base, Repo

if TYPE_CHECKING:
    from .session_agent import SessionAgent


class Session(Base):
    __tablename__ = "sessions"

    session_agents: Mapped[list[SessionAgent]] = relationship(
        back_populates="session",
        lazy="raise",
    )


class SessionRepo(Repo[Session]):
    model_type = Session
