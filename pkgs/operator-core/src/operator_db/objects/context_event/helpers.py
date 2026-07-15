from collections.abc import Mapping, Sequence
from dataclasses import replace
from itertools import pairwise
from typing import TYPE_CHECKING, Any, Literal, overload

from pydantic import JsonValue, TypeAdapter
from pydantic_ai import (
  BinaryContent,
  CachePoint,
  FilePart,
  ModelMessage,
  ModelMessagesTypeAdapter,
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

from operator_db.objects.types import MsgAgent, MsgMetadata, MsgRole
from operator_shared.utils import (
  ensure,
  ensure_singleton,
  present_json,
)

from .model import ContextEvent, MessageGroup

if TYPE_CHECKING:
  from sqlalchemy.ext.asyncio import AsyncSession

  from operator_db.objects.base import IDType

  _L = Literal
  type _BinCnt = BinaryContent
  type _Msg = ContextEvent.Message
  type _UserCnt = Sequence[UserContent] | str | None
else:
  _BinCnt = BinaryContent

_RAW_DATA_KEY = "raw_data"
_RESPONSE_JSON_KEY = "operator_db.response_json"
_JSON_VALUE_ADAPTER = TypeAdapter(JsonValue)


def _get_pydantic_message(msg: ModelMessage) -> dict[str, Any]:
  """Serialize one complete Pydantic AI message for exact replay."""
  payload = ModelMessagesTypeAdapter.dump_python([msg], mode="json")[
    0
  ]
  if not isinstance(payload, dict):
    error_msg = "Pydantic AI emitted an unexpected message payload!"
    raise TypeError(error_msg)
  return payload


@overload
def _get_bin_cnt(ev: _Msg, *, force: _L[True] = True) -> _BinCnt: ...
@overload
def _get_bin_cnt(
  ev: _Msg, *, force: _L[False] = False
) -> _BinCnt | None: ...


def _get_bin_cnt(
  ev: _Msg,
  *,
  force: bool = True,
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
  return TextContent(present_json(x), metadata={_RAW_DATA_KEY: x})


def _get_user_contents(ev: _Msg) -> list[UserContent]:
  cnts: list[UserContent] = []
  if ev.text is not None:
    cnts.append(_mk_txt(ev.text))
  if ev.json is not None:
    cnts.append(_mk_txt(ev.json))
  if (bin_cnt := _get_bin_cnt(ev, force=False)) is not None:
    cnts.append(bin_cnt)
  if not cnts:
    msg = "Message has no content!"
    raise ValueError(msg)
  return cnts


def _get_agent_part(
  ev: _Msg, cnts: list[UserContent]
) -> UserPromptPart:
  """Render agent content while retaining persistence-only raw-data metadata."""
  msg = MsgAgent(
    content=cnts,
    timestamp=ev.created_at,
    agent_id=ensure(ev.extra_metadata.agent_id),
  )
  part = msg.to_part()
  if isinstance(part.content, str):
    msg = "Expected agent content to remain a sequence!"
    raise TypeError(msg)
  for source, rendered in zip(cnts, part.content, strict=True):
    if isinstance(source, TextContent) and isinstance(
      rendered, TextContent
    ):
      rendered.metadata = source.metadata
  return part


def _get_parts_req(
  ev: _Msg,
) -> tuple[_L[True], Sequence[ModelRequestPart]] | None:
  """Get ModelRequestPart objects from `ev` or return `None`."""
  parts: Sequence[ModelRequestPart]
  match ev.role:
    case MsgRole.SYSTEM:
      parts = (
        SystemPromptPart(
          content=ensure(ev.text), timestamp=ev.created_at
        ),
      )
    case MsgRole.USER | MsgRole.AGENT_OTHER:
      cnts = _get_user_contents(ev)
      part = (
        _get_agent_part(ev, cnts)
        if ev.role == MsgRole.AGENT_OTHER
        else UserPromptPart(content=cnts, timestamp=ev.created_at)
      )
      parts = (part,)
    case MsgRole.TOOL_REPLY:
      parts = (
        ToolReturnPart(
          tool_name=ensure(ev.extra_metadata.tool_name),
          content=ensure(ev.json),
          timestamp=ev.created_at,
        ),
      )
    case MsgRole.RETRY:
      content = ev.json if ev.json is not None else ensure(ev.text)
      if not isinstance(content, str | list):
        msg = (
          "Retry content must be text or a list of validation errors!"
        )
        raise TypeError(msg)
      parts = (
        RetryPromptPart(
          tool_name=ensure(ev.extra_metadata.tool_name),
          content=content,
          timestamp=ev.created_at,
        ),
      )
    case MsgRole.FILE_OTHER:
      parts = (
        UserPromptPart(
          content=(_get_bin_cnt(ev),), timestamp=ev.created_at
        ),
      )
    case _:
      return None
  return True, parts


def _get_parts_res(
  ev: _Msg,
) -> tuple[_L[False], Sequence[ModelResponsePart]] | None:
  """Get ModelResponsePart objects from `ev` or return `None`."""
  parts: Sequence[ModelResponsePart]
  match ev.role:
    case MsgRole.AGENT_SELF:
      if ev.binary_contents is not None:
        msg = "Agent content cannot contain a file; use the FILE_SELF role!"
        raise ValueError(msg)
      text_parts: list[ModelResponsePart] = []
      if ev.text is not None:
        text_parts.append(TextPart(ev.text))
      if ev.json is not None:
        text_parts.append(TextPart(present_json(ev.json)))
      if not text_parts:
        msg = "Agent message has no content!"
        raise ValueError(msg)
      parts = text_parts
    case MsgRole.AGENT_SELF_THINKING:
      parts = (ThinkingPart(ensure(ev.text)),)
    case MsgRole.TOOL_CALL:
      args = ev.json if ev.json is not None else ensure(ev.text)
      if not isinstance(args, str | dict):
        msg = "Tool-call arguments must be a string or object!"
        raise TypeError(msg)
      parts = (
        ToolCallPart(
          tool_name=ensure(ev.extra_metadata.tool_name),
          args=args,
        ),
      )
    case MsgRole.FILE_SELF:
      parts = (FilePart(content=_get_bin_cnt(ev)),)
    case _:
      return None
  return False, parts


async def _legacy_ev_to_pyai_msg(
  ev: _Msg,
  *,
  session: AsyncSession | None,
  refresh: bool = True,
) -> ModelMessage:
  """Convert into Pydantic AI message.

  If `refresh` is NOT set, won't force-refresh session to load params and may
  error in case that required attributes aren't loaded.
  """
  attrs = (
    "role",
    "text",
    "json",
    "binary_contents",
    "extra_metadata",
    "created_at",
  )
  if refresh:
    if not session:
      error_msg = "Cannot have `refresh` set if `session` is `None`!"
      raise ValueError(error_msg)
    await session.refresh(ev, attribute_names=attrs)
  out = _get_parts_req(ev) or _get_parts_res(ev)
  if not out:
    msg = "Couldn't make parts for message!"
    raise ValueError(msg)

  is_req, parts = out
  payload = ev.extra_metadata.pydantic_metadata.model_dump(
    mode="json"
  )
  payload["parts"] = parts
  payload["kind"] = "request" if is_req else "response"
  if payload.get("timestamp") is None:
    payload["timestamp"] = ev.created_at
  obj = ModelMessagesTypeAdapter.validate_python([payload])[0]
  if is_req != isinstance(obj, ModelRequest):
    msg = "Pydantic AI constructed an unexpected message kind!"
    raise TypeError(msg)

  if ev.role in (MsgRole.AGENT_OTHER, MsgRole.AGENT_SELF):
    metadata = obj.metadata
    if metadata is None:
      metadata = {}
      obj.metadata = metadata
    if ev.role == MsgRole.AGENT_OTHER:
      metadata["agent_id"] = ensure(ev.extra_metadata.agent_id)
    if ev.role == MsgRole.AGENT_SELF and ev.json is not None:
      metadata[_RESPONSE_JSON_KEY] = {
        "part_index": int(ev.text is not None),
        "value": ev.json,
      }
  return obj


def _validate_grouped_events(
  events: Sequence[_Msg],
  *,
  message_group: MessageGroup,
  message: ModelMessage,
) -> None:
  """Validate that events are one complete on-path message group."""
  if any(
    event.message_group is not message_group for event in events
  ):
    error_msg = "Message events belong to different groups!"
    raise ValueError(error_msg)
  if any(
    event.context_id != message_group.context_id for event in events
  ):
    error_msg = (
      "Message group and events belong to different contexts!"
    )
    raise ValueError(error_msg)

  indices = [event.message_group_index for event in events]
  if indices != list(range(len(events))) or len(message.parts) != len(
    events
  ):
    error_msg = (
      "Message group indices or part cardinality are incomplete!"
    )
    raise ValueError(error_msg)

  member_ids = [member.id for member in message_group.messages]
  event_ids = [event.id for event in events]
  if member_ids != event_ids:
    error_msg = (
      "Message group is incomplete or contains off-path events!"
    )
    raise ValueError(error_msg)
  if any(
    child.parent_id != parent.id for parent, child in pairwise(events)
  ):
    error_msg = (
      "Message group events do not form a linear parent chain!"
    )
    raise ValueError(error_msg)


_REFRESH_ATTRS = (
  "context_id",
  "parent_id",
  "message_group_id",
  "message_group_index",
  "message_group",
  "role",
  "text",
  "json",
  "binary_contents",
  "extra_metadata",
  "created_at",
)


@overload
async def events_to_pyai_msg(
  events: Sequence[_Msg],
  *,
  session: AsyncSession,
  refresh: _L[True] = True,
) -> ModelMessage: ...
@overload
async def events_to_pyai_msg(
  events: Sequence[_Msg],
  *,
  session: AsyncSession | None,
  refresh: _L[False],
) -> ModelMessage: ...


async def events_to_pyai_msg(
  events: Sequence[_Msg],
  *,
  session: AsyncSession | None,
  refresh: bool = True,
) -> ModelMessage:
  """Collapse one complete message-event group into one Pydantic AI message."""
  if not events:
    error_msg = "Cannot construct a message from no events!"
    raise ValueError(error_msg)

  if refresh:
    if not session:
      error_msg = "Cannot have `refresh` set if `session` is `None`!"
      raise ValueError(error_msg)
    for event in events:
      await session.refresh(event, attribute_names=_REFRESH_ATTRS)

  message_group = events[0].message_group
  if message_group is None:
    if any(event.message_group is not None for event in events[1:]):
      error_msg = "Cannot mix grouped and ungrouped message events!"
      raise ValueError(error_msg)
    if len(events) != 1:
      error_msg = "Multiple ungrouped events cannot form one message!"
      raise ValueError(error_msg)
    return await _legacy_ev_to_pyai_msg(
      events[0], session=session, refresh=False
    )

  if refresh:
    if not session:
      error_msg = "Cannot have `refresh` set if `session` is `None`!"
      raise ValueError(error_msg)
    await session.refresh(
      message_group,
      attribute_names=("context_id", "pydantic_message", "messages"),
    )
  message = ModelMessagesTypeAdapter.validate_python(
    [message_group.pydantic_message]
  )[0]
  _validate_grouped_events(
    events, message_group=message_group, message=message
  )
  return message


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


def _ensure_user_cnts_len(user_cnts: Sequence[Any] | str) -> None:
  if not user_cnts:
    error_msg = "User content was empty!"
    raise ValueError(error_msg)


def _get_pydantic_metadata(msg: ModelMessage) -> dict[str, Any]:
  """Serialize message-level Pydantic AI fields for event persistence."""
  payload = ModelMessagesTypeAdapter.dump_python([msg], mode="json")[
    0
  ]
  if not isinstance(payload, dict):
    error_msg = "Pydantic AI emitted an unexpected message payload!"
    raise TypeError(error_msg)
  out: dict[str, Any] = {
    key: value
    for key, value in payload.items()
    if isinstance(key, str) and key not in ("kind", "parts")
  }
  metadata = out.get("metadata")
  if isinstance(metadata, dict):
    metadata.pop("agent_id", None)
    metadata.pop(_RESPONSE_JSON_KEY, None)
    if not metadata:
      out["metadata"] = None
  return out


def _new_event_kw(msg: ModelMessage) -> dict[str, Any]:
  return {
    "role": None,
    "text": None,
    "json": None,
    "binary_contents": None,
    "extra_metadata": {
      "pydantic_metadata": _get_pydantic_metadata(msg)
    },
  }


def _set_raw_content(kw: dict[str, Any], value: object) -> None:
  raw_data = _JSON_VALUE_ADAPTER.validate_python(value)
  key = "text" if isinstance(raw_data, str) else "json"
  current = kw[key]
  if current is None:
    kw[key] = raw_data
  elif key == "text":
    kw[key] = f"{current}\n\n{raw_data}"
  else:
    kw[key] = [current, raw_data]


def _get_serialized_part_content(msg: ModelRequest) -> JsonValue:
  """Extract JSON-mode content from a single serialized request part."""
  payload = _get_pydantic_message(msg)
  parts = payload.get("parts")
  if not isinstance(parts, list) or len(parts) != 1:
    error_msg = (
      "Pydantic AI emitted an unexpected serialized part list!"
    )
    raise TypeError(error_msg)
  part = parts[0]
  if not isinstance(part, Mapping) or "content" not in part:
    error_msg = (
      "Pydantic AI emitted a serialized part without content!"
    )
    raise TypeError(error_msg)
  return _JSON_VALUE_ADAPTER.validate_python(part["content"])


def _handle_req_part_partial(
  msg: ModelRequest,
  part: ModelRequestPart,
) -> tuple[dict[str, Any], _UserCnt]:
  """Handle request parts that map directly onto a single event."""
  kw = _new_event_kw(msg)
  kw["created_at"] = msg.timestamp or part.timestamp
  user_cnts: _UserCnt = None
  match part:
    case SystemPromptPart(content=text):
      kw["text"] = text
      kw["role"] = MsgRole.SYSTEM
    case ToolReturnPart(tool_name=tool_name):
      kw["role"] = MsgRole.TOOL_REPLY
      kw["json"] = _get_serialized_part_content(msg)
      kw["extra_metadata"]["tool_name"] = tool_name
    case RetryPromptPart(tool_name=tool_name, content=cnt):
      kw["role"] = MsgRole.RETRY
      kw["text" if isinstance(cnt, str) else "json"] = cnt
      kw["extra_metadata"]["tool_name"] = tool_name
    case UserPromptPart(content=cnts):
      user_cnts = cnts
    case _:
      kw["role"] = MsgRole.USER
  return kw, user_cnts


def _apply_user_contents(
  kw: dict[str, Any],
  user_cnts: Sequence[UserContent] | str,
) -> BinaryContent | None:
  _ensure_user_cnts_len(user_cnts)
  items: Sequence[UserContent] = (
    (user_cnts,) if isinstance(user_cnts, str) else user_cnts
  )
  bin_cnts: list[BinaryContent] = []
  for item in items:
    if isinstance(item, str):
      _set_raw_content(kw, item)
    elif isinstance(item, TextContent):
      metadata = item.metadata
      raw_data = (
        metadata[_RAW_DATA_KEY]
        if isinstance(metadata, Mapping) and _RAW_DATA_KEY in metadata
        else item.content
      )
      _set_raw_content(kw, raw_data)
    elif isinstance(item, BinaryContent):
      bin_cnts.append(item)
    elif isinstance(item, CachePoint):
      continue

  bin_cnt = bin_cnts[0] if bin_cnts else None
  if bin_cnt is not None:
    kw["binary_contents"] = bin_cnt.data
    kw["extra_metadata"]["mimetype"] = bin_cnt.media_type
  return bin_cnt


def _get_kw_pyai_req(msg: ModelRequest) -> dict[str, Any]:
  _ensure_req_parts_len(parts := msg.parts)
  kw, user_cnts = _handle_req_part_partial(msg, parts[0])
  if user_cnts is None:
    return kw
  agent_id = (msg.metadata or {}).get("agent_id")
  if agent_id is not None and not isinstance(agent_id, str):
    error_msg = "Agent ID in message metadata must be a string!"
    raise ValueError(error_msg)
  if agent_id is not None:
    kw["extra_metadata"]["agent_id"] = agent_id

  bin_cnt = _apply_user_contents(kw, user_cnts)
  if agent_id is not None:
    kw["role"] = MsgRole.AGENT_OTHER
  elif (
    bin_cnt is not None and kw["text"] is None and kw["json"] is None
  ):
    kw["role"] = MsgRole.FILE_OTHER
  else:
    kw["role"] = MsgRole.USER
  return kw


def _get_response_json_marker(
  msg: ModelResponse,
) -> tuple[int, JsonValue] | None:
  metadata = msg.metadata or {}
  if _RESPONSE_JSON_KEY not in metadata:
    return None
  marker = metadata[_RESPONSE_JSON_KEY]
  if not isinstance(marker, Mapping):
    error_msg = "Response JSON metadata marker must be a mapping!"
    raise TypeError(error_msg)
  part_index = marker.get("part_index")
  if type(part_index) is not int:
    error_msg = (
      "Response JSON metadata marker has an invalid part index!"
    )
    raise TypeError(error_msg)
  if part_index < 0:
    error_msg = (
      "Response JSON metadata marker has a negative part index!"
    )
    raise ValueError(error_msg)
  if "value" not in marker:
    error_msg = "Response JSON metadata marker has no value!"
    raise ValueError(error_msg)
  return part_index, _JSON_VALUE_ADAPTER.validate_python(
    marker["value"]
  )


def _apply_tool_call_projection(
  kw: dict[str, Any], part: ToolCallPart
) -> None:
  """Project searchable tool-call fields without changing replay data."""
  kw["role"] = MsgRole.TOOL_CALL
  if isinstance(part.args, str):
    kw["text"] = part.args
  else:
    kw["json"] = part.args
  kw["extra_metadata"]["tool_name"] = part.tool_name


def _get_kw_pyai_res(msg: ModelResponse) -> dict[str, Any]:
  kw = _new_event_kw(msg)
  kw["created_at"] = msg.timestamp

  supported = (TextPart, ThinkingPart, FilePart, ToolCallPart)
  unsupported = [
    part for part in msg.parts if not isinstance(part, supported)
  ]
  if unsupported:
    kw["role"] = MsgRole.AGENT_SELF
    return kw

  text_parts = [
    (index, part)
    for index, part in enumerate(msg.parts)
    if isinstance(part, TextPart)
  ]
  thinking_parts = [
    part for part in msg.parts if isinstance(part, ThinkingPart)
  ]
  file_parts = [
    part for part in msg.parts if isinstance(part, FilePart)
  ]
  tool_parts = [
    part for part in msg.parts if isinstance(part, ToolCallPart)
  ]
  json_marker = _get_response_json_marker(msg)
  if json_marker is not None:
    json_index, json_value = json_marker
    if json_index >= len(msg.parts) or not isinstance(
      msg.parts[json_index], TextPart
    ):
      error_msg = "Response JSON metadata points to a non-text part!"
      raise ValueError(error_msg)
    text_parts = [
      (index, part)
      for index, part in text_parts
      if index != json_index
    ]
    kw["json"] = json_value

  categories = sum(
    (
      bool(text_parts or json_marker is not None),
      bool(thinking_parts),
      bool(file_parts),
      bool(tool_parts),
    )
  )
  if categories != 1:
    error_msg = (
      "Response parts cannot map unambiguously onto one event!"
    )
    raise ValueError(error_msg)

  if text_parts or json_marker is not None:
    kw["role"] = MsgRole.AGENT_SELF
    if text_parts:
      kw["text"] = "".join(part.content for _, part in text_parts)
  elif thinking_parts:
    kw["role"] = MsgRole.AGENT_SELF_THINKING
    kw["text"] = "\n\n".join(part.content for part in thinking_parts)
  elif file_parts:
    p_file = ensure_singleton(file_parts)
    kw["role"] = MsgRole.FILE_SELF
    kw["binary_contents"] = p_file.content.data
    kw["extra_metadata"]["mimetype"] = p_file.content.media_type
  else:
    _apply_tool_call_projection(kw, ensure_singleton(tool_parts))
  return kw


def _get_kw_pyai_part(
  msg: ModelMessage,
  *,
  part_index: int,
) -> dict[str, Any]:
  """Normalize one top-level message part into one context event."""
  if isinstance(msg, ModelRequest):
    part = msg.parts[part_index]
    return _get_kw_pyai_req(replace(msg, parts=(part,)))

  part = msg.parts[part_index]

  json_marker = _get_response_json_marker(msg)
  metadata = dict(msg.metadata or {})
  if json_marker is not None:
    json_index, json_value = json_marker
    if json_index >= len(msg.parts) or not isinstance(
      msg.parts[json_index], TextPart
    ):
      error_msg = "Response JSON metadata points to a non-text part!"
      raise ValueError(error_msg)
    if json_index == part_index:
      metadata[_RESPONSE_JSON_KEY] = {
        "part_index": 0,
        "value": json_value,
      }
    else:
      metadata.pop(_RESPONSE_JSON_KEY, None)

  part_msg = replace(
    msg,
    parts=(part,),
    metadata=metadata or None,
  )
  return _get_kw_pyai_res(part_msg)


async def from_pyai_msg(
  msg: ModelMessage,
  *,
  context_id: IDType,
  parent_id: IDType,
  session: AsyncSession | None = None,
) -> list[_Msg]:
  """Split one Pydantic AI message into a serial group of context events.

  The returned events are ordered from the first message part to the last. A caller
  advancing a context pointer must use the final event.

  If a session is supplied, the objects are added and flushed but not committed.
  """
  if not msg.parts:
    error_msg = "Parts shouldn't be empty!"
    raise ValueError(error_msg)

  message_group = MessageGroup(
    context_id=context_id,
    pydantic_message=_get_pydantic_message(msg),
  )
  events: list[_Msg] = []
  previous: _Msg | None = None
  for part_index in range(len(msg.parts)):
    kw: dict[str, Any] = {
      "context_id": context_id,
      "message_group": message_group,
      "message_group_index": part_index,
    }
    if previous is None:
      kw["parent_id"] = parent_id
    else:
      kw["parent"] = previous
    kw.update(_get_kw_pyai_part(msg, part_index=part_index))
    kw["extra_metadata"] = MsgMetadata.model_validate(
      kw["extra_metadata"]
    )
    previous = ContextEvent.Message(**kw)
    events.append(previous)

  if session:
    session.add_all(events)
    await session.flush()
  return events
