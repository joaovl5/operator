from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, select
from sqlalchemy.orm import Mapped, mapped_column, relationship

from operator_db.objects.history_epoch import HistoryEvent

from .base import Base, IDType, Repo
from .history_epoch import HistoryEpoch

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from .session_agent import SessionAgent


class History(Base):
    __tablename__ = "histories"

    epochs: Mapped[list[HistoryEpoch]] = relationship(
        back_populates="history",
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
        lazy="immediate",
    )
    forks: Mapped[list[History]] = relationship(
        back_populates="forked_from",
    )

    session_agent: Mapped[SessionAgent] = relationship(
        uselist=False,
        back_populates="history",
        lazy="immediate",
    )

    async def get_current_epoch(
        self,
        session: AsyncSession,
    ) -> HistoryEpoch:
        """Gets currently-used history epoch - only one is active at a time."""
        query = (
            select(HistoryEpoch)
            .join(
                HistoryEvent.Event,
                HistoryEvent.Event.epoch_id == HistoryEpoch.id,
            )
            .where(HistoryEpoch.history_id == self.id)
            .order_by(HistoryEvent.Event.created_at.desc())
            .limit(1)
        )
        epoch = await session.scalar(query)
        if not epoch:
            msg = "History doesn't have epochs with events!"
            raise ValueError(msg)
        return epoch

    async def as_dict(self) -> dict[str, Any]:
        """Convert object to dictionary."""
        epochs: list[HistoryEpoch] = await self._at.epochs
        forks: list[History] = await self._at.forks
        return {
            "epochs": [await x.as_dict() for x in epochs],
            "forks": [await x.as_dict() for x in forks],
        }


class HistoryRepo(Repo[History]):
    model_type = History
