from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IDType, Repo

if TYPE_CHECKING:
    from .history import History
    from .history_event import HistoryEvent


class HistoryEpoch(Base):
    __tablename__ = "history_epochs"

    history_id: Mapped[IDType] = mapped_column(
        ForeignKey("histories.id"),
        index=True,
    )
    history: Mapped[History] = relationship(
        uselist=False,
        back_populates="epochs",
        lazy="selectin",
    )

    events: Mapped[list[HistoryEvent.Type]] = relationship(
        back_populates="epoch",
        lazy="raise",
    )


class HistoryEpochRepo(Repo[HistoryEpoch]):
    model_type = HistoryEpoch
