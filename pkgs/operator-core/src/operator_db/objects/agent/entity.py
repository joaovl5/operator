# pyright: reportImportCycles=false

"""Session agent entities."""

from typing import TYPE_CHECKING, final

from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from operator_db.utils.db.base import Entity
from operator_db.utils.db.mixins import MetadataMixin, OptJson, OptStr, OptStrLong, ReqStr
from operator_db.utils.json import JsonValue

if TYPE_CHECKING:
    from operator_db.objects.history.entity import HistoryEnt
    from operator_db.objects.mail.entity import MailboxMapping
    from operator_db.objects.session.entity import SessionEnt

_JSON_VALUE = JsonValue


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
        "SessionEnt",
        back_populates="agents",
    )
    """Associated session."""

    history_id: Mapped[str] = mapped_column(
        ForeignKey("histories.id"),
        nullable=False,
    )
    history: Mapped[HistoryEnt] = relationship(
        "HistoryEnt",
        back_populates="agent",
    )

    sent_mail_mappings: Mapped[list[MailboxMapping]] = relationship(
        "MailboxMapping",
        back_populates="sender_agent",
        foreign_keys="MailboxMapping.sender_agent_id",
    )
    """Mail delivery rows where this agent is a sender."""

    received_mail_mappings: Mapped[list[MailboxMapping]] = relationship(
        "MailboxMapping",
        back_populates="receiver_agent",
        foreign_keys="MailboxMapping.receiver_agent_id",
    )
    """Mail delivery rows where this agent is a receiver."""
