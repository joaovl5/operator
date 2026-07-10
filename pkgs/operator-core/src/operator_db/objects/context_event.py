from collections.abc import Mapping
from typing import (
    TYPE_CHECKING,
    Any,
    Literal,
    Self,
    cast,
    final,
    overload,
    override,
)

from advanced_alchemy.types import JsonB
from pydantic import JsonValue  # noqa: TC002
from pydantic_ai import (
    BinaryContent,
    FilePart,
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    ModelResponsePart,
    RetryPromptPart,
    SystemPromptPart,
    TextContent,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserContent,
    UserPromptPart,
)
from sqlalchemy import ForeignKey, LargeBinary, func, literal, select
from sqlalchemy.orm import Mapped, aliased, mapped_column, relationship

from operator_shared.utils import ensure, present_json

from .base import Base, IDType, Repo, Svc
from .constants import TxtShort  # noqa: TC001
from .types import ForkReconcile, MsgAgent, MsgMetadata, MsgRole, MsgUser, OptJson, OptText
from .utils import PydanticJSON, poly

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession

    from .context import AgentContext

    _L = Literal

if TYPE_CHECKING:
    type _BinCnt = BinaryContent
else:
    _BinCnt = BinaryContent


def get_poly_id(t: type[ContextEvent.Event]) -> str:
    """Returns the polymorphic identity for the class."""
    return t.__mapper_args__["polymorphic_identity"]


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

        extra_metadata: Mapped[MsgMetadata] = mapped_column(
            PydanticJSON(MsgMetadata),
            default=MsgMetadata,
            nullable=True,
        )

        def _get_media_type(self) -> str:
            """Return the media type for the binary contents of the message.

            Raises error if no `binary_contents` or no media type found.
            """
            if not self.binary_contents:
                msg = "Missing `binary_contents`"
                raise ValueError(msg)
            if (x := self.extra_metadata.mimetype) is not None:
                return x
            msg = "Missing `mimetype`"
            raise ValueError(msg)

        @overload
        def _get_bin_cnt(self, *, force: _L[True] = True) -> _BinCnt: ...
        @overload
        def _get_bin_cnt(self, *, force: _L[False] = False) -> _BinCnt | None: ...

        def _get_bin_cnt(
            self,
            *,
            force: bool = False,
        ) -> BinaryContent | None:
            """Get binary content into Pydantic AI form."""
            data = self.binary_contents
            if not force and data is None:
                return None
            return BinaryContent(
                data=ensure(data),
                media_type=self._get_media_type(),
            )

        def _get_parts_req(self) -> tuple[_L[True], Sequence[ModelRequestPart]] | None:
            parts: Sequence[ModelRequestPart]
            match self.role:
                case MsgRole.SYSTEM:
                    parts = (SystemPromptPart(content=ensure(self.text)),)
                case MsgRole.USER | MsgRole.AGENT_OTHER:
                    h = (self.text, self.json, self._get_bin_cnt(force=False))
                    h = (x for x in h if x is not None)
                    h = (
                        TextContent(present_json(x), metadata={"raw_data": x})
                        if not isinstance(x, _BinCnt)
                        else x
                        for x in h
                    )
                    cnts = list(h)
                    if not cnts:
                        msg = "Message has no content!"
                        raise ValueError(msg)
                    msg_kw = {"content": cnts}
                    cons = MsgUser
                    if self.role == MsgRole.AGENT_OTHER:
                        cons = MsgAgent
                        ag_id = self.extra_metadata.agent_id
                        msg_kw["agent_id"] = ensure(ag_id)
                    msg = cons.model_construct(**msg_kw)
                    parts = (msg.to_part(),)
                case MsgRole.TOOL_REPLY:
                    tool_name = ensure(self.extra_metadata.tool_name)
                    cnt = ensure(self.json)
                    parts = (ToolReturnPart(tool_name=tool_name, content=cnt),)
                case MsgRole.RETRY:
                    tool_name = ensure(self.extra_metadata.tool_name)
                    # prioritize json, assumes it will be validation errors if so,
                    # otherwise fallback to obligatory `self.text` or raising
                    cnt = self.json or ensure(self.text)
                    parts = (RetryPromptPart(tool_name=tool_name, content=cnt),)
                case MsgRole.FILE_OTHER:
                    parts = (UserPromptPart(content=self._get_bin_cnt()),)
                case _:
                    return None
            return True, parts

        def _get_parts_res(self) -> tuple[_L[False], Sequence[ModelResponsePart]] | None:
            match self.role:
                case MsgRole.AGENT_SELF:
                    parts = []
                    if x := self.text:
                        parts.append(TextPart(x))
                    if x := self.json:
                        parts.append(TextPart(present_json(x)))
                    if x := self.binary_contents:
                        parts.append(self._get_bin_cnt())
                case MsgRole.AGENT_SELF_THINKING:
                    parts = (ThinkingPart(ensure(self.text)),)
                case MsgRole.TOOL_CALL:
                    tool_name = ensure(self.extra_metadata.tool_name)
                    args = ensure(self.json)
                    parts = (ToolCallPart(tool_name=tool_name, args=args),)
                case MsgRole.FILE_SELF:
                    parts = (FilePart(content=self._get_bin_cnt()),)
                case _:
                    return None
            return False, parts

        async def to_pyai_msg(
            self,
            *,
            session: AsyncSession,
            refresh: bool = True,
        ) -> ModelMessage:
            """Convert into Pydantic AI message.

            If `refresh` is NOT set, won't force-refresh session to load params and may
            error in case that required attributes aren't loaded.
            """
            attrs = ("role", "text", "json", "binary", "extra_metadata", "created_at")
            if refresh:
                await session.refresh(self, attribute_names=attrs)
            out = self._get_parts_req() or self._get_parts_res()
            if not out:
                msg = "Couldn't make parts for message!"
                raise ValueError(msg)

            is_req, parts = out
            cons = ModelRequest if is_req else ModelResponse
            kwargs = self.extra_metadata.pydantic_metadata.as_kwargs()
            obj = cons(
                parts,
                **kwargs,
            )
            # smuggling `AGENT_OTHER` role data
            if self.role == MsgRole.AGENT_OTHER:
                if obj.metadata is None:
                    obj.metadata = {}
                obj.metadata["agent_id"] = ensure(self.extra_metadata.agent_id)
            return obj

        @classmethod
        def _get_kw_pyai_req(cls, msg: ModelRequest) -> dict[str, Any]:
            parts = msg.parts
            kw = {
                "role": None,
                "text": None,
                "json": None,
                "binary_contents": None,
                "extra_metadata": {},
            }
            parts_len = len(parts)

            if parts_len == 0:
                error_msg = "Parts shouldn't be empty!"
                raise ValueError(error_msg)
            if parts_len != 1:
                # if pyai does this we will have to refactor this function to return
                # multiple `Self` instances
                error_msg = "Parts isn't expected to have more than one thing!"
                raise ValueError(error_msg)

            part = parts[0]
            user_cnts: Sequence[UserContent] | str | None = None
            match part:
                case SystemPromptPart(text):
                    kw["text"] = text
                    kw["role"] = MsgRole.SYSTEM
                case ToolReturnPart(tool_name=tool_name, content=cnt):
                    kw["role"] = MsgRole.TOOL_REPLY
                    kw["json"] = cnt
                    kw["extra_metadata"]["tool_name"] = tool_name
                case RetryPromptPart(tool_name=tool_name, content=cnt):
                    kw["role"] = MsgRole.RETRY
                    kw["text" if isinstance(cnt, str) else "json"] = cnt
                    kw["extra_metadata"]["tool_name"] = tool_name
                case UserPromptPart(content=cnts):
                    user_cnts = cnts
                case _:
                    error_msg = "Unexpected part!"
                    raise ValueError(error_msg)
            if user_cnts is None:
                return kw
            # smuggling `AGENT_OTHER` role data
            if agent_id := (msg.metadata or {}).get("agent_id"):
                kw["extra_metadata"]["agent_id"] = agent_id
            role = MsgRole.AGENT_OTHER if agent_id else MsgRole.USER
            if isinstance(user_cnts, str):
                kw["text"] = user_cnts
                kw["role"] = role
                return kw
            user_cnts_len = len(user_cnts)
            if user_cnts_len == 0:
                error_msg = "User content was empty!"
                raise ValueError(error_msg)
            raw_data_items = (
                raw_data
                for x in user_cnts
                if (
                    not isinstance(x, str)
                    and isinstance(x.metadata, Mapping)
                    and (raw_data := x.metadata.get("raw_data")) is not None
                )
            )
            bin_cnt_lst = [cast("_BinCnt", x) for x in user_cnts if isinstance(x, _BinCnt)]
            match len(bin_cnt_lst):
                case 0:
                    pass
                case 1:
                    bin_cnt: _BinCnt = bin_cnt_lst.pop()
                    kw["binary_contents"] = bin_cnt.data
                    kw["extra_metadata"]["mimetype"] = bin_cnt.media_type
                case _:
                    error_msg = "Unexpected more than one `BinaryContent` in parts!"
                    raise ValueError(error_msg)
            for x in raw_data_items:
                if isinstance(x, str):
                    if kw["text"]:
                        error_msg = "Unexpected two strings in raw data parts!"
                        raise ValueError(error_msg)
                    kw["text"] = x
                    continue
                if kw["json"]:
                    error_msg = "Unexpected two json values in raw data parts!"
                    raise ValueError(error_msg)
                kw["json"] = x

        @classmethod
        async def from_pyai_msg(
            cls,
            msg: ModelMessage,
            *,
            session: AsyncSession | None = None,
            commit: bool = False,
        ) -> Self:
            """Convert Pydantic AI message into db object.

            Args:
                msg: `ModelMessage` instance
                session: if passed, will add returned object into session
                commit: if set, will commit the session (requires `session`)

            Returns:
                Instance of `ContextEvent.Message`
            """
            if isinstance(msg, ModelRequest):
                kw = cls._get_kw_pyai_req(msg)
            else:
                pass

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
        EpochStart  # D
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

    @overload
    async def walk_up_to[EventT: CtxEvent](
        self,
        *,
        event_id: IDType,
        stop_at: type[EventT] = ContextEvent.EpochStart,
        return_only_start: _L[False] = False,
    ) -> list[CtxEvent]: ...

    @overload
    async def walk_up_to[EventT: CtxEvent](
        self,
        *,
        event_id: IDType,
        stop_at: type[EventT] = ContextEvent.EpochStart,
        return_only_start: _L[True] = True,
    ) -> EventT | None: ...

    async def walk_up_to[EventT: CtxEvent](
        self,
        *,
        event_id: IDType,
        stop_at: type[EventT] = ContextEvent.EpochStart,
        return_only_start: bool = False,
    ) -> list[CtxEvent] | EventT | None:
        """Walks up ancestry of event until reaching the first `stop_at` event type.

        By default, `stop_at` is `EpochStart`, meaning it will gather all events of the
        current epoch.

        If `return_only_start` is set, will return a list containing only the top of the
        list, thus a event of type `stop_at`.
        """
        stop_poly_id = get_poly_id(stop_at)

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
            .where(chain.c.type != stop_poly_id)
        )

        query = (
            select(CtxEvent)
            .join(
                chain,
                CtxEvent.id == chain.c.id,
            )
            .order_by(chain.c.depth.desc())
        )

        if return_only_start:
            query = query.where(CtxEvent.type == stop_poly_id).limit(1)
            return cast("EventT | None", await self._session.scalar(query))

        return list(await self._session.scalars(query))
