from typing import TYPE_CHECKING, Any

from sqlalchemy.orm import Mapped, relationship

from .base import Base
from .context_event import CtxEvent  # noqa: TC001

if TYPE_CHECKING:
    from operator_db.objects.session_agent import SessionAgent


class AgentContext(Base):
    """Agent-unique context owner.

    Context has a tree-like structure of *events*:
        - some events might not be rendered to the LLM, but are useful to store, whereas
          others will be actively translated into a LLM-safe representation.
        - we want to generally keep events as append-only in structure, so data analysis
          can be done without requiring an audit log.

    Each node in the context tree belongs to an *epoch*, which is a unit akin to
    an open or closed interval:
        - It has `A` and `B` nodes, where `B` is the latest and `A` is its ancestor, and
          the parent nodes collected until reaching the ancestor `A` represent a part of
          the overall *epoch*
        - The epoch is what is given to the LLM at a time, so in events of compression
          a new epoch must be made, representing a new open interval and closing the
          interval of the previous one
        - We want events to be append-only and to minimize the amount of overwrites, so
          in the event of a compression, the previous epoch gets compressed, and the
          compressed representation, whatever it may be, gets added as a new event for
          the new epoch
        - This way we manage to keep a log of how compactions and context is handled.

    Epochs are implicit and the manner in which we define its messages is the following:
        - For a given event `A`, we trace its ancestors until reaching in a new epoch
          event
        - Anything traced up until said event is considered part of the epoch
        - For creation of a new epoch, the new epoch event must be created, and any
          events like compression must be appended as nodes there-in.

    """

    __tablename__ = "contexts"

    agent: Mapped[SessionAgent] = relationship(
        uselist=False,
        back_populates="context",
    )

    events: Mapped[list[CtxEvent]] = relationship(
        back_populates="context",
    )

    async def as_dict(self) -> dict[str, Any]:
        """Convert object to dictionary."""
        events: list[CtxEvent] = await self.aw.events
        cap = 100
        return {
            "events": f"<{len_events}> events"
            if (len_events := len(events)) > cap
            else [await x.as_dict() for x in events],
        }
