from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IDType, Repo, Svc
from .history_event import HistoryEvent  # noqa: TC001

if TYPE_CHECKING:
    from .history import History


class HistoryEpoch(Base):
    __tablename__ = "history_epochs"

    history_id: Mapped[IDType] = mapped_column(
        ForeignKey("histories.id"),
        index=True,
    )
    history: Mapped[History] = relationship(
        uselist=False,
        back_populates="epochs",
        lazy="immediate",
    )

    events: Mapped[list[HistoryEvent.Event]] = relationship(
        back_populates="epoch",
    )

    async def as_dict(self) -> dict[str, Any]:
        """Convert object to dictionary."""
        events: list[HistoryEvent.Type] = await self._at.events
        return {"events": [await x.as_dict() for x in events]}


class HistoryEpochRepo(Repo[HistoryEpoch]):
    model_type = HistoryEpoch


class HistoryEpochSvc(Svc[HistoryEpoch]):
    repository_type = HistoryEpochRepo
