"""Session entities."""

from typing import TYPE_CHECKING, final

from sqlalchemy.orm import Mapped, relationship

from operator_db.utils.db.base import Entity
from operator_db.utils.db.mixins import MetadataMixin

if TYPE_CHECKING:
    from operator_db.objects.agent.entity import SessionAgentEnt


@final
class SessionEnt(MetadataMixin, Entity):
    """Encompasses multi-agent session collaboration."""

    __tablename__ = "sessions"

    agents: Mapped[list[SessionAgentEnt]] = relationship(
        "SessionAgentEnt",
        back_populates="session",
    )
    """Agents derived in session."""
