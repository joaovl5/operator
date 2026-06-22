from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IDType, Repo

if TYPE_CHECKING:
    from .history_epoch import HistoryEpoch


class History(Base):
    __tablename__ = "histories"

    epochs: Mapped[list[HistoryEpoch]] = relationship(
        back_populates="history",
        lazy="raise",
    )

    forked_from_id: Mapped[IDType] = mapped_column(
        ForeignKey("histories.id"),
        index=True,
    )
    forked_from: Mapped[History] = relationship(
        uselist=False,
        back_populates="forks",
        lazy="selectin",
    )
    forks: Mapped[list[History]] = relationship(
        back_populates="forked_from",
        lazy="raise",
    )


class HistoryRepo(Repo[History]):
    model_type = History
