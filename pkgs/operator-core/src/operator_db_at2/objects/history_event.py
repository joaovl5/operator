from typing import TYPE_CHECKING, final

from advanced_alchemy.types import JsonB
from pydantic import JsonValue  # noqa: TC002
from sqlalchemy import ForeignKey, LargeBinary
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IDType, Repo
from .constants import TxtShort  # noqa: TC001
from .types import ForkReconcile, MsgRole, OptJson, OptText
from .utils import PydanticJSON, poly

if TYPE_CHECKING:
    from .history_epoch import HistoryEpoch


class HistoryEvent:
    # IMPORTANT!
    # For the polymorphism to work, we set `nullable` on all subclass fields.
    # SQLAlchemy will handle the rest.
    class Event(Base):
        """Polymorphic single-table relation for events."""

        __tablename__ = "history_epoch_events"

        epoch_id: Mapped[IDType] = mapped_column(
            ForeignKey("history_epochs.id"),
            index=True,
        )
        epoch: Mapped[HistoryEpoch] = relationship(
            uselist=False,
            back_populates="events",
            lazy="selectin",
        )

        if TYPE_CHECKING:
            forks: Mapped[list[HistoryEvent.Event]]
            """Forked events from different histories (branches), if any."""

        type: Mapped[TxtShort] = mapped_column(index=True)

        __mapper_args__ = poly("event", root=True)

    @final
    class ChatStart(Event):
        """Chat has started.

        Only applicable if its the start of the first epoch.
        """

        __mapper_args__ = poly("chat_start")

    @final
    class Compression(Event):
        """Represents a base form of a compressed representation of past epochs.

        This should be at the start of an epoch (aside from the first).
        """

        __mapper_args__ = poly("compression")

    @final
    class Forking(Event):
        """Chat was forked into a new branch.

        The `forked_from_event` value must belong to a different history.
        The `Forking` event must be at the start of the newly-forked history.
        """

        __mapper_args__ = poly("forking")

        forked_from_event_id: Mapped[IDType] = mapped_column(
            ForeignKey("history_epoch_events.id"),
            index=True,
        )
        if TYPE_CHECKING:
            forked_from_event: Mapped[HistoryEvent.Event]

    @final
    class Resuming(Event):
        """Forked branch now reconciling with forked-from branch."""

        __mapper_args__ = poly("resuming")

        reconcile_method: Mapped[ForkReconcile] = mapped_column(
            PydanticJSON(ForkReconcile),
        )

    @final
    class Message(Event):
        """Logged message."""

        __mapper_args__ = poly("message")

        role: Mapped[MsgRole] = mapped_column(index=True, nullable=True)
        """Message author role."""

        text: Mapped[OptText]
        """Text contents if message is text-based."""

        json: Mapped[OptJson]
        """JSON contents if message has structured data."""

        binary_contents: Mapped[bytes | None] = mapped_column(
            LargeBinary(),
            nullable=True,
        )
        """Bytes contents if message is binary-based, like images."""

        extra_metadata: Mapped[dict[str, JsonValue]] = mapped_column(
            JsonB,
            nullable=True,
            default=dict,
        )

    @final
    class UseModel(Event):
        """Model used by agent was updated."""

        __mapper_args__ = poly("use_model")

        model_name: Mapped[TxtShort] = mapped_column(nullable=True)
        model_provider: Mapped[TxtShort] = mapped_column(nullable=True)

    @final
    class UsePermissions(Event):
        """Permissions for the agent were received or updated."""

        __mapper_args__ = poly("use_permissions")

        data: Mapped[JsonValue] = mapped_column(JsonB, nullable=True)

    type _IsEvent[T: Event] = T
    type Type = _IsEvent[
        ChatStart  # .
        | Compression
        | Forking
        | Resuming
        | Message
        | UseModel
        | UsePermissions
    ]


HistoryEvent.Event.forks = relationship(
    HistoryEvent.Forking,
    back_populates="forked_from_event",
    lazy="raise",
)
HistoryEvent.Forking.forked_from_event = relationship(
    HistoryEvent.Event,
    uselist=False,
    back_populates="forks",
    remote_side=lambda: HistoryEvent.Event.id,
    lazy="selectin",
)


class HistoryEventRepo(Repo[HistoryEvent.Event]):
    model_type = HistoryEvent.Event
