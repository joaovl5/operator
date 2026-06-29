from typing import TYPE_CHECKING, Any

from sqlalchemy import ForeignKey, select, update
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, IDType, Repo, Svc
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

    For keeping track of where we are at the context tree, we use *pointers*, which are
    basically a "last event" tracking measure for gathering epoch events upwards, and it
    must be kept updated as new events arise.

    """

    __tablename__ = "contexts"

    pointer_event_id: Mapped[IDType | None] = mapped_column(
        ForeignKey("context_events.id"),
        index=True,
        nullable=True,
    )
    pointer_event: Mapped[CtxEvent | None] = relationship(
        uselist=False,
    )

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


class AgentContextSvc(Svc[AgentContext]):
    class _Repo(Repo[AgentContext]):
        model_type = AgentContext

    repository_type = _Repo

    async def get_pointer_id(self, context_id: IDType) -> IDType | None:
        """Get value for that context's `pointer_event_id`."""
        pointer_event_query = (
            select(
                AgentContext.pointer_event_id,
            )
            .where(AgentContext.id == context_id)
            .limit(1)
        )
        return await self._session.scalar(pointer_event_query)

    async def set_pointer_id(self, context_id: IDType, event_id: IDType) -> None:
        """Move the pointer of context."""
        pointer_set_query = (
            update(AgentContext)
            .where(
                AgentContext.id == context_id,
            )
            .values(pointer_event_id=event_id)
        )

        await self._session.execute(pointer_set_query)
        await self._session.commit()
