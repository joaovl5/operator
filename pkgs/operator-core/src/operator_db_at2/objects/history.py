from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IDType, Repo
from .session_agent import SessionAgent

if TYPE_CHECKING:
    from .history_epoch import HistoryEpoch


class History(Base):
    __tablename__ = "histories"

    epochs: Mapped[list[HistoryEpoch]] = relationship(
        back_populates="history",
        lazy="raise",
    )

    forked_from_id: Mapped[IDType | None] = mapped_column(
        ForeignKey("histories.id"),
        index=True,
        nullable=True,
        default=None,
    )
    forked_from: Mapped[History | None] = relationship(
        back_populates="forks",
        remote_side=lambda: History.id,
        lazy="selectin",
    )
    forks: Mapped[list[History]] = relationship(
        back_populates="forked_from",
        lazy="raise",
    )

    session_agent: Mapped[SessionAgent] = relationship(
        uselist=False,
        back_populates="history",
        lazy="selectin",
    )


class HistoryRepo(Repo[History]):
    model_type = History
