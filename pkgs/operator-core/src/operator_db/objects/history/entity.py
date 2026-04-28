"""History entities."""

from typing import TYPE_CHECKING, final

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from operator_db.constants import SHORT_STR_LEN
from operator_db.constants.role import HistoryMessageRole  # noqa: TC001
from operator_db.utils.db.base import Entity
from operator_db.utils.db.json import JSONColumn
from operator_db.utils.db.mixins import ArbitraryMetadata, MetadataMixin, OptStr, OptStrLong
from operator_db.utils.json import JsonValue

if TYPE_CHECKING:
    from operator_db.objects.agent.entity import SessionAgentEnt

_JSON_VALUE = JsonValue


@final
class HistoryEnt(MetadataMixin, Entity):
    """Refers to conversation log for a single agent."""

    __tablename__ = "histories"

    agent: Mapped[SessionAgentEnt] = relationship(
        "SessionAgentEnt",
        back_populates="history",
        uselist=False,
    )

    epochs: Mapped[list[HistoryEpochEnt]] = relationship(
        "HistoryEpochEnt",
        back_populates="history",
        order_by=lambda: HistoryEpochEnt.epoch_iteration,
    )
    """Messages contained in this epoch."""


@final
class HistoryEpochEnt(MetadataMixin, Entity):
    """Single 'epoch' of an agent's conversation log.

    'Epoch' referring to an iteration/period of the chat preserving its current structure,
    meaning that when a conversation goes through compaction in some way, it becomes
    another epoch.

    When conversations get compacted and epochs progress, we want to keep track of which
    messages in an epoch relate to messages in previous epochs, to preserve how the
    compaction process affected the conversation. A compaction 'message' should link
    back to all its messages that got compacted from it.
    """

    __tablename__ = "history_epochs"
    __table_args__ = (
        UniqueConstraint(
            "history_id",
            "epoch_iteration",
            name="uq_history_epochs_history_id_epoch_iteration",
        ),
        CheckConstraint(
            "epoch_iteration >= 0",
            name="ck_history_epochs_epoch_iteration_nonnegative",
        ),
    )

    history_id: Mapped[str] = mapped_column(
        ForeignKey("histories.id"),
        nullable=False,
    )
    """ID of parent history."""

    history: Mapped[HistoryEnt] = relationship(
        "HistoryEnt",
        back_populates="epochs",
    )
    """Parent history."""

    epoch_iteration: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
    )
    """Iteration of current epoch.

    After compaction, a new epoch is created, incrementing this number by one.
    """

    messages: Mapped[list[HistoryEpochMessageEnt]] = relationship(
        "HistoryEpochMessageEnt",
        back_populates="epoch",
        order_by=lambda: HistoryEpochMessageEnt.message_index,
    )
    """Messages contained in this epoch."""


@final
class HistoryEpochMessageEnt(Entity):
    __tablename__ = "history_epoch_messages"
    __table_args__ = (
        UniqueConstraint(
            "epoch_id",
            "message_index",
            name="uq_history_epoch_messages_epoch_id_message_index",
        ),
        CheckConstraint(
            "message_index >= 0",
            name="ck_history_epoch_messages_message_index_nonnegative",
        ),
        Index(
            "ix_history_epoch_messages_compacted_by_id",
            "compacted_by_id",
        ),
        Index(
            "ix_history_epoch_messages_author_id",
            "author_id",
        ),
    )

    epoch_id: Mapped[str] = mapped_column(
        ForeignKey("history_epochs.id"),
        nullable=False,
    )
    """ID of parent history epoch."""

    epoch: Mapped[HistoryEpochEnt] = relationship(
        "HistoryEpochEnt",
        back_populates="messages",
    )
    """Parent epoch."""

    message_index: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
    )
    """Position of this message within its parent epoch."""

    role: Mapped[HistoryMessageRole] = mapped_column(
        String(SHORT_STR_LEN),
        nullable=False,
    )
    """Message author role."""

    author_id: Mapped[OptStr]
    """Message author ID, specific to harness and to session, not any DB-related ID."""

    text_contents: Mapped[OptStrLong]
    """Text contents if message is text-based."""

    binary_contents: Mapped[bytes | None] = mapped_column(
        LargeBinary(),
        nullable=True,
    )
    """Bytes contents if message is binary-based, like images."""

    json_contents: Mapped[
        dict[str, object] | list[object] | str | int | float | bool | None
    ] = mapped_column(
        JSONColumn,
        nullable=True,
    )
    """JSON contents if message has structured data."""

    extra_metadata: Mapped[ArbitraryMetadata]
    """Additional metadata for storing misc. values."""

    compacted_by_id: Mapped[str | None] = mapped_column(
        ForeignKey("history_epoch_messages.id"),
        nullable=True,
    )
    """ID of message that compacted this current one, if any.

    This is set after a compaction yields a new epoch with new messages, so this refers
    to the compacted message's ID.
    """

    compacted_by: Mapped[HistoryEpochMessageEnt | None] = relationship(
        "HistoryEpochMessageEnt",
        back_populates="compacted_messages",
        remote_side=lambda: [HistoryEpochMessageEnt.id],
    )
    """Message that compacted this current message."""

    compacted_messages: Mapped[list[HistoryEpochMessageEnt]] = relationship(
        "HistoryEpochMessageEnt",
        back_populates="compacted_by",
    )
    """Messages the current message has compacted from."""
