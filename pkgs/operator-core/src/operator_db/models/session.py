"""Session-related models."""

from typing import final

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
from operator_db.messages.mail import MailMessageState
from operator_db.messages.role import HistoryMessageRole  # noqa: TC001
from operator_db.models.json import JSONColumn, JsonValue

from .base import Base, Entity
from .mixins import (
    ArbitraryMetadata,
    MetadataMixin,
    OptJson,
    OptStr,
    OptStrLong,
    ReqStr,
    ReqStrLong,
)


@final
class SessionEnt(MetadataMixin, Entity):
    """Encompasses multi-agent session collaboration."""

    __tablename__ = "sessions"

    agents: Mapped[list[SessionAgentEnt]] = relationship(
        back_populates="session",
    )
    """Agents derived in session."""


@final
class SessionAgentEnt(MetadataMixin, Entity):
    """Represents an instantiated agent within a session.

    An agent is 'instantiated' in a way that session-local agent params are derived from
    a configuration-based recipe, but parameters may be overriden in a per-session basis
    and persisted. Basically, an agent is instantiated/created through some preset, but
    after that it is independent and can be tweaked without affecting said preset.
    """

    __tablename__ = "session_agents"
    __table_args__ = (
        UniqueConstraint(
            "session_id",
            "local_id",
            name="uq_session_agents_session_id_local_id",
        ),
        UniqueConstraint(
            "history_id",
            name="uq_session_agents_history_id",
        ),
    )

    local_id: Mapped[ReqStr]
    """ID referring to agent within session.

    This ID is unique through the session only.
    """

    model: Mapped[OptStr]
    system_prompt: Mapped[OptStrLong]
    serialized_permissions: Mapped[OptJson]

    session_id: Mapped[str] = mapped_column(
        ForeignKey("sessions.id"),
        nullable=False,
    )
    """ID of associated session."""

    session: Mapped[SessionEnt] = relationship(
        back_populates="agents",
    )
    """Associated session."""

    history_id: Mapped[str] = mapped_column(
        ForeignKey("histories.id"),
        nullable=False,
    )
    history: Mapped[HistoryEnt] = relationship(
        back_populates="agent",
    )

    sent_mail_mappings: Mapped[list[MailboxMapping]] = relationship(
        back_populates="sender_agent",
        foreign_keys=lambda: [MailboxMapping.sender_agent_id],
    )
    """Mail delivery rows where this agent is a sender."""

    received_mail_mappings: Mapped[list[MailboxMapping]] = relationship(
        back_populates="receiver_agent",
        foreign_keys=lambda: [MailboxMapping.receiver_agent_id],
    )
    """Mail delivery rows where this agent is a receiver."""


@final
class MailMessageEnt(Entity):
    """Mailbox message."""

    __tablename__ = "mail_messages"

    title: Mapped[OptStr]
    body: Mapped[ReqStrLong]
    extra_metadata: Mapped[ArbitraryMetadata]

    mailbox_mappings: Mapped[list[MailboxMapping]] = relationship(
        back_populates="mail_message",
        cascade="save-update, merge, delete, delete-orphan",
    )
    """Delivery rows for this mail message."""


@final
class MailboxMapping(Base):
    """Intermediary table for saving mail relationships."""

    __tablename__ = "mailbox_mappings"
    __table_args__ = (
        Index(
            "ix_mailbox_mappings_sender_agent_id",
            "sender_agent_id",
        ),
        Index(
            "ix_mailbox_mappings_receiver_agent_id_state",
            "receiver_agent_id",
            "state",
        ),
    )

    mail_message_id: Mapped[str] = mapped_column(
        ForeignKey("mail_messages.id", ondelete="CASCADE"),
        primary_key=True,
    )
    sender_agent_id: Mapped[str] = mapped_column(
        ForeignKey("session_agents.id", ondelete="CASCADE"),
        primary_key=True,
    )
    receiver_agent_id: Mapped[str] = mapped_column(
        ForeignKey("session_agents.id", ondelete="CASCADE"),
        primary_key=True,
    )

    state: Mapped[MailMessageState] = mapped_column(
        String(SHORT_STR_LEN),
        nullable=False,
        default=MailMessageState.QUEUED,
    )
    """Per-receiver state for this mail delivery."""

    mail_message: Mapped[MailMessageEnt] = relationship(
        back_populates="mailbox_mappings",
    )
    """Message delivered by this row."""

    sender_agent: Mapped[SessionAgentEnt] = relationship(
        back_populates="sent_mail_mappings",
        foreign_keys=lambda: [MailboxMapping.sender_agent_id],
    )
    """Agent sending this delivery row."""

    receiver_agent: Mapped[SessionAgentEnt] = relationship(
        back_populates="received_mail_mappings",
        foreign_keys=lambda: [MailboxMapping.receiver_agent_id],
    )
    """Agent receiving this delivery row."""

    # Same-session semantics are validated before persistence; portable SQL constraints
    # cannot compare sender/receiver session_id through referenced rows without storing
    # session_id here or using database-specific triggers.


@final
class HistoryEnt(MetadataMixin, Entity):
    """Refers to conversation log for a single agent."""

    __tablename__ = "histories"

    agent: Mapped[SessionAgentEnt] = relationship(
        back_populates="history",
        uselist=False,
    )

    epochs: Mapped[list[HistoryEpochEnt]] = relationship(
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

    json_contents: Mapped[JsonValue | None] = mapped_column(
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
        back_populates="compacted_messages",
        remote_side=lambda: [HistoryEpochMessageEnt.id],
    )
    """Message that compacted this current message."""

    compacted_messages: Mapped[list[HistoryEpochMessageEnt]] = relationship(
        back_populates="compacted_by",
    )
    """Messages the current message has compacted from."""
