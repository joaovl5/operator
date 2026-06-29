from typing import TYPE_CHECKING, Any, final, override

from advanced_alchemy.types import JsonB
from pydantic import JsonValue  # noqa: TC002
from sqlalchemy import ForeignKey, LargeBinary, func, literal, select
from sqlalchemy.orm import Mapped, aliased, mapped_column, relationship

from .base import Base, IDType, Repo, Svc
from .constants import TxtShort  # noqa: TC001
from .types import ForkReconcile, MsgRole, OptJson, OptText
from .utils import PydanticJSON, poly

if TYPE_CHECKING:
    from .context import AgentContext


def get_poly_id(t: type[ContextEvent.Event]) -> str:
    """Returns the polymorphic identity for the class."""
    return t.__mapper_args__["polymorphic_identity"]


if not True and False:
    pass


class ContextEvent:
    # IMPORTANT!
    # For the polymorphism to work, we set `nullable` on all subclass fields.
    # We don't need to set equivalent `| None` in annotations, since SQLAlchemy will
    # handle the rest.
    class Event(Base):
        """Polymorphic single-table relation for events."""

        __tablename__ = "context_events"

        context_id: Mapped[IDType] = mapped_column(
            ForeignKey("contexts.id"),
            index=True,
        )
        context: Mapped[AgentContext] = relationship(
            uselist=False,
            back_populates="events",
            lazy="immediate",
        )

        parent_id: Mapped[IDType | None] = mapped_column(
            ForeignKey("context_events.id"),
            index=True,
            nullable=True,
        )
        if TYPE_CHECKING:
            parent: Mapped[ContextEvent.Event | None]
            children: Mapped[list[ContextEvent.Event]]

        type: Mapped[TxtShort] = mapped_column(index=True)

        __mapper_args__ = poly("event", root=True)

        async def as_dict(self) -> dict[str, Any]:
            """Convert object to dictionary."""
            return {"type": self.type}

    @final
    class EpochStart(Event):
        """Marks the start of an epoch."""

        __mapper_args__ = poly("epoch_start")

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
    class Resuming(Event):
        """Forked branch now reconciling with forked-from branch."""

        __mapper_args__ = poly("resuming")

        reconcile_method: Mapped[ForkReconcile] = mapped_column(
            PydanticJSON(ForkReconcile),
            nullable=True,
        )

        @override
        async def as_dict(self) -> dict[str, Any]:
            return await super().as_dict() | {
                "reconcile_method": self.reconcile_method.model_dump(),
            }

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

        @override
        async def as_dict(self) -> dict[str, Any]:
            return await super().as_dict() | {
                "role": await self.aw.role,
                "text": await self.aw.text,
                "json": await self.aw.json,
                "binary": f"<Binary of length {len(bin_contents)}"
                if (bin_contents := await self.aw.binary_contents)
                else None,
                "extra_metadata": await self.aw.extra_metadata,
            }

    @final
    class UseModel(Event):
        """Model used by agent was updated."""

        __mapper_args__ = poly("use_model")

        model_name: Mapped[TxtShort] = mapped_column(nullable=True)
        model_provider: Mapped[TxtShort] = mapped_column(nullable=True)

        @override
        async def as_dict(self) -> dict[str, Any]:
            return await super().as_dict() | {
                "model_name": await self.aw.model_name,
                "model_provider": await self.aw.model_provider,
            }

    @final
    class UsePermissions(Event):
        """Permissions for the agent were received or updated."""

        __mapper_args__ = poly("use_permissions")

        data: Mapped[JsonValue] = mapped_column(JsonB, nullable=True)

        @override
        async def as_dict(self) -> dict[str, Any]:
            return await super().as_dict() | {
                "data": await self.aw.data,
            }

    type _IsEvent[T: Event] = T
    type Type = _IsEvent[
        EpochStart  # .
        | ChatStart
        | Compression
        | Resuming
        | Message
        | UseModel
        | UsePermissions
    ]


CtxEvent = ContextEvent.Event
CtxEvent.parent = relationship(
    CtxEvent,
    remote_side=lambda: [ContextEvent.Event.id],
    back_populates="children",
    lazy="immediate",
)
CtxEvent.children = relationship(
    CtxEvent,
    back_populates="parent",
)


class ContextEventSvc(Svc[CtxEvent]):
    class _Repo(Repo[CtxEvent]):
        model_type = CtxEvent

    repository_type = _Repo

    def bake_into_tree(self, events: list[ContextEvent.Type]) -> None:
        """Converts a linear sequence of events into tree-like structure.

        This will modify the `events` list in-place.

        The last element will be the inner-most, and the first will be the ancestor.
        If the sequence is empty, will raise an error.

        This has two important nuances:
            - Won't clear parent of the first event
            - Won't propagate context_id, expects it to already be set
        """
        event_iter = reversed(events)

        try:
            child = next(event_iter)
        except StopIteration:
            msg = "Can't bake into tree structure if `events` is empty."
            raise ValueError(msg) from None

        for parent in event_iter:
            child.parent = parent
            child = parent

    async def walk_down_unforked(self, anchor_event_id: IDType) -> CtxEvent | None:
        """Walk down, from anchor event, until the last event is found and returned.

        If forks are found while walking down, returns `None`.
        """
        child_count_probe = aliased(CtxEvent)

        chain = (
            select(
                CtxEvent.id.label("id"),
                CtxEvent.context_id.label("context_id"),
                literal(0).label("depth"),
                (
                    select(func.count(child_count_probe.id))
                    .where(
                        child_count_probe.context_id == CtxEvent.context_id,
                        child_count_probe.parent_id == CtxEvent.id,
                    )
                    .scalar_subquery()
                ).label("child_count"),
            )
            .where(CtxEvent.id == anchor_event_id)
            .cte("ctx_event_down_chain")
        )

        child = aliased(CtxEvent)
        next_child_count_probe = aliased(CtxEvent)

        chain = chain.union_all(
            select(
                child.id,
                child.context_id,
                (chain.c.depth + 1).label("depth"),
                (
                    select(func.count(next_child_count_probe.id))
                    .where(
                        next_child_count_probe.context_id == child.context_id,
                        next_child_count_probe.parent_id == child.id,
                    )
                    .scalar_subquery()
                ).label("child_count"),
            )
            .join(chain, child.parent_id == chain.c.id)
            .where(
                child.context_id == chain.c.context_id,
                chain.c.child_count == 1,
            )
        )

        rows = list(
            await self._session.execute(
                select(CtxEvent, chain.c.child_count)
                .join(chain, CtxEvent.id == chain.c.id)
                .order_by(chain.c.depth.desc())
            )
        )

        if not rows or any(child_count > 1 for _, child_count in rows):
            return None

        return rows[0][0]

    async def walk_up_epoch(
        self,
        event_id: IDType,
    ) -> list[CtxEvent]:
        """Walks up ancestry of event until reaching the beginning of epoch."""
        chain = (
            select(
                CtxEvent.id.label("id"),
                CtxEvent.parent_id.label("parent_id"),
                CtxEvent.context_id.label("context_id"),
                CtxEvent.type.label("type"),
                literal(0).label("depth"),
            )
            .where(CtxEvent.id == event_id)
            .cte("ctx_event_epoch_chain", recursive=True)
        )
        parent = aliased(CtxEvent)
        chain = chain.union_all(
            select(
                parent.id,
                parent.parent_id,
                parent.context_id,
                parent.type,
                (chain.c.depth + 1).label("depth"),
            )
            .join(chain, parent.id == chain.c.parent_id)
            .where(parent.context_id == chain.c.context_id)
            .where(chain.c.type != get_poly_id(ContextEvent.EpochStart))
        )

        query = (
            select(CtxEvent)
            .join(
                chain,
                CtxEvent.id == chain.c.id,
            )
            .order_by(chain.c.depth.desc())
        )

        return list(await self._session.scalars(query))
