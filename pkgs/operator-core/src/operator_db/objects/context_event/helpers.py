from collections.abc import Iterator, Mapping, Sequence
from typing import TYPE_CHECKING, Any, Literal, cast, overload

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

from le_pipes.builtins import collect, holo, where
from le_pipes.utils import is_something
from operator_db.objects.types import MsgAgent, MsgRole, MsgUser
from operator_shared.utils import (
    ensure,
    ensure_singleton,
    get_one_or_none,
    isinstp,
    present_json,
    where_inst,
)

if TYPE_CHECKING:
    from pydantic import JsonValue
    from sqlalchemy.ext.asyncio import AsyncSession

    from operator_db.objects.base import IDType

    from .model import ContextEvent

    _L = Literal
    type _BinCnt = BinaryContent
    type _Msg = ContextEvent.Message
    type _UserCnt = Sequence[UserContent] | str | None
else:
    _BinCnt = BinaryContent


@overload
def _get_bin_cnt(ev: _Msg, *, force: _L[True] = True) -> _BinCnt: ...
@overload
def _get_bin_cnt(ev: _Msg, *, force: _L[False] = False) -> _BinCnt | None: ...


def _get_bin_cnt(
    ev: _Msg,
    *,
    force: bool = False,
) -> _BinCnt | None:
    """Get binary content into Pydantic AI form."""
    data = ev.binary_contents
    if not force and data is None:
        return None
    return BinaryContent(
        data=ensure(data),
        media_type=_get_media_type(ev),
    )


def _get_media_type(ev: _Msg) -> str:
    """Return the media type for the binary contents of the message.

    Raises error if no `binary_contents` or no media type found.
    """
    if not ev.binary_contents:
        msg = "Missing `binary_contents`"
        raise ValueError(msg)
    if (x := ev.extra_metadata.mimetype) is not None:
        return x
    msg = "Missing `mimetype`"
    raise ValueError(msg)


def _mk_txt(x: JsonValue) -> TextContent:
    return TextContent(present_json(x), metadata={"raw_data": x})


def _get_parts_req(ev: _Msg) -> tuple[_L[True], Sequence[ModelRequestPart]] | None:
    """Get ModelRequestPart objects from `ev` or return `None`."""
    parts: Sequence[ModelRequestPart]
    match ev.role:
        case MsgRole.SYSTEM:
            parts = (SystemPromptPart(content=ensure(ev.text)),)
        case MsgRole.USER | MsgRole.AGENT_OTHER:
            cnts = (
                (ev.text, ev.json, _get_bin_cnt(ev, force=False))
                | where(Any, is_something)
                | holo(Any, lambda x: x if isinstance(x, _BinCnt) else _mk_txt(x))
                | collect(Any)
            )

            if not cnts:
                msg = "Message has no content!"
                raise ValueError(msg)
            msg_kw = {"content": cnts}
            cons = MsgUser
            if ev.role == MsgRole.AGENT_OTHER:
                cons = MsgAgent
                ag_id = ev.extra_metadata.agent_id
                msg_kw["agent_id"] = ensure(ag_id)
            msg = cons.model_construct(**msg_kw)
            parts = (msg.to_part(),)
        case MsgRole.TOOL_REPLY:
            tool_name = ensure(ev.extra_metadata.tool_name)
            cnt = ensure(ev.json)
            parts = (ToolReturnPart(tool_name=tool_name, content=cnt),)
        case MsgRole.RETRY:
            tool_name = ensure(ev.extra_metadata.tool_name)
            # prioritize json, assumes it will be validation errors if so,
            # otherwise fallback to obligatory `ev.text` or raising
            cnt = ev.json or ensure(ev.text)
            parts = (RetryPromptPart(tool_name=tool_name, content=cnt),)
        case MsgRole.FILE_OTHER:
            parts = (UserPromptPart(content=_get_bin_cnt(ev)),)
        case _:
            return None
    return True, parts


def _get_parts_res(ev: _Msg) -> tuple[_L[False], Sequence[ModelResponsePart]] | None:
    """Get ModelResponsePart objects from `ev` or return `None`."""
    match ev.role:
        case MsgRole.AGENT_SELF:
            parts = []
            if x := ev.text:
                parts.append(TextPart(x))
            if x := ev.json:
                parts.append(TextPart(present_json(x)))
            if x := ev.binary_contents:
                parts.append(_get_bin_cnt(ev))
        case MsgRole.AGENT_SELF.THINKING:
            parts = (ThinkingPart(ensure(ev.text)),)
        case MsgRole.TOOL_CALL:
            tool_name = ensure(ev.extra_metadata.tool_name)
            args = ensure(ev.json)
            parts = (ToolCallPart(tool_name=tool_name, args=args),)
        case MsgRole.FILE_SELF:
            parts = (FilePart(content=_get_bin_cnt(ev)),)
        case _:
            return None
    return False, parts


async def ev_to_pyai_msg(
    ev: _Msg,
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
        await session.refresh(ev, attribute_names=attrs)
    out = _get_parts_req(ev) or _get_parts_res(ev)
    if not out:
        msg = "Couldn't make parts for message!"
        raise ValueError(msg)

    is_req, parts = out
    cons = ModelRequest if is_req else ModelResponse
    kwargs = ev.extra_metadata.pydantic_metadata.as_kwargs()
    obj = cons(
        parts,
        **kwargs,
    )
    # smuggling `AGENT_OTHER` role data
    if ev.role == MsgRole.AGENT_OTHER:
        if obj.metadata is None:
            obj.metadata = {}
        obj.metadata["agent_id"] = ensure(ev.extra_metadata.agent_id)
    return obj


def _ensure_req_parts_len(parts: Sequence[Any]) -> None:
    parts_len = len(parts)
    if parts_len == 0:
        error_msg = "Parts shouldn't be empty!"
        raise ValueError(error_msg)
    if parts_len != 1:
        # if pyai does this we will have to refactor this function to return
        # multiple `Self` instances
        error_msg = "Parts isn't expected to have more than one thing!"
        raise ValueError(error_msg)


def _ensure_user_cnts_len(user_cnts: Sequence[Any]) -> None:
    if isinstance(user_cnts, str):
        return
    lst_len = len(user_cnts)
    if lst_len == 0:
        error_msg = "User content was empty!"
        raise ValueError(error_msg)


def _ensure_bin_cnt(bin_cnt_lst: list[_BinCnt]) -> _BinCnt | None:
    lst_len = len(bin_cnt_lst)
    if lst_len == 0:
        return None
    if lst_len > 1:
        error_msg = "Unexpected more than one `BinaryContent` in parts!"
        raise ValueError(error_msg)
    return bin_cnt_lst[0]


def _handle_req_part_partial(part: ModelRequestPart) -> tuple[dict[str, Any], _UserCnt]:
    """Tries determining if `part` falls under simple constructions.

    Will not handle the edge-case for `AGENT_OTHER`/`USER` ambiguity.
    """
    kw = {
        "role": None,
        "text": None,
        "json": None,
        "binary_contents": None,
        "extra_metadata": {},
    }
    user_cnts: _UserCnt = None
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
    return kw, user_cnts


def _get_kw_pyai_req(msg: ModelRequest) -> dict[str, Any]:
    part = _ensure_req_parts_len(parts := msg.parts) or parts[0]

    kw, user_cnts = _handle_req_part_partial(part)
    if user_cnts is None:
        return kw
    _ensure_user_cnts_len(user_cnts)
    kw["text"] = user_cnts if isinstance(user_cnts, str) else None
    if agent_id := (msg.metadata or {}).get("agent_id"):
        kw["extra_metadata"]["agent_id"] = agent_id
    kw["role"] = MsgRole.AGENT_OTHER if agent_id else MsgRole.USER
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
    if bin_cnt := _ensure_bin_cnt(bin_cnt_lst):
        kw["binary_contents"] = bin_cnt.data
        kw["extra_metadata"]["mimetype"] = bin_cnt.media_type
    for x in raw_data_items:
        if isinstance(x, str):
            if kw["text"]:
                error_msg = "Unexpected two strings in raw data parts!"
                raise ValueError(error_msg)
            kw["text"] = x
        elif kw["json"]:
            error_msg = "Unexpected two json values in raw data parts!"
            raise ValueError(error_msg)
        else:
            kw["json"] = x
    return kw


def _raw_data(cnt: TextContent) -> JsonValue:
    return (cnt.metadata or {}).get("raw_data")


def _get_kw_pyai_res(msg: ModelResponse) -> dict[str, Any]:
    kw = {
        "role": None,
        "text": None,
        "json": None,
        "binary_contents": None,
        "extra_metadata": {},
    }

    ps = msg.parts
    txt_parts: Iterator[JsonValue] = ps | where_inst(TextPart) | holo(JsonValue, _raw_data)
    p_text: str | None = txt_parts | where_inst(str) | get_one_or_none
    p_json: JsonValue | None = (
        txt_parts | where(Any, lambda x: not isinstance(x, str)) | get_one_or_none
    )
    p_think: ThinkingPart | None = ps | where_inst(ThinkingPart) | get_one_or_none
    p_file: FilePart | None = ps | where_inst(FilePart) | get_one_or_none
    p_tool: ToolCallPart | None = ps | where_inst(ToolCallPart) | get_one_or_none
    if p_think and p_text:
        error_msg = "Can't have ThinkingPart and TextPart in the same event."
        raise ValueError(error_msg)
    if p_tool and p_json:
        error_msg = "Can't have ToolCallPart and JSON TextPart in the same event."
        raise ValueError(error_msg)
    if p_tool:
        kw["extra_metadata"]["tool_name"] = p_tool.tool_name

    if txt_data := p_think or p_text:
        kw["text"] = txt_data
    if json_data := p_tool.args_as_dict(raise_if_invalid=True) if p_tool else p_json:
        kw["json"] = json_data
    if p_file:
        kw["binary_contents"] = p_file.content.data

    # p_text = ensure_singleton(seq_filter(ps, isinstp(TextPart)), none_ok=True)

    return kw


async def from_pyai_msg(
    msg: ModelMessage,
    *,
    context_id: IDType,
    parent_id: IDType,
    session: AsyncSession | None = None,
    commit: bool = False,
) -> _Msg:
    """Convert Pydantic AI message into db object.

    Args:
        msg: `ModelMessage` instance.
        context_id: linked context ID.
        parent_id: parent event ID.
        session: if passed, will add returned object into session.
        commit: if set, will commit the session (requires `session`) and refresh
                it to populate the event ID.

    Returns:
        Instance of `ContextEvent.Message`
    """
    kw = {
        "context_id": context_id,
        "parent_id": parent_id,
    } | (_get_kw_pyai_req(msg) if isinstance(msg, ModelRequest) else _get_kw_pyai_res(msg))

    inst = cls(**kw)
    if session:
        session.add(inst)
    if commit:
        if not session:
            error_msg = "Cannot set `commit` to True if `session` is absent!"
            raise ValueError(error_msg)
        await session.commit()
        await session.refresh(inst, attribute_names=("id",))
    return inst
