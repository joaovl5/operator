"""History schema adapters for stable provider transform DTOs."""

from typing import TYPE_CHECKING

from operator_db.constants import HistoryMessageRole
from operator_db.objects.history.schema import (
  HistoryMessageRequestSchema,
  HistoryMessageResponseSchema,
  HistoryMessageSchema,
  JsonPayload,
)
from pydantic import TypeAdapter, ValidationError

from operator_core_olden.providers.transforms.errors import (
  ProviderTransformError,
)
from operator_shared.providers.transforms import (
  JsonObject,
  JsonValue,
  OperatorFilePart,
  OperatorMessage,
  OperatorRequestMessage,
  OperatorResponseMessage,
  OperatorRetryPromptPart,
  OperatorSystemPromptPart,
  OperatorTextPart,
  OperatorThinkingPart,
  OperatorToolCallPart,
  OperatorToolReturnPart,
  OperatorUserPromptPart,
)

if TYPE_CHECKING:
  from collections.abc import Sequence
  from datetime import datetime

_OPERATOR_MESSAGE_ADAPTER: TypeAdapter[OperatorMessage] = TypeAdapter(
  OperatorMessage
)
_JSON_OBJECT_ADAPTER: TypeAdapter[JsonObject] = TypeAdapter(
  JsonObject
)
_JSON_OBJECT_LIST_ADAPTER: TypeAdapter[list[JsonObject]] = (
  TypeAdapter(list[JsonObject])
)
_JSON_PAYLOAD_ADAPTER: TypeAdapter[JsonPayload] = TypeAdapter(
  JsonPayload
)
_JSON_VALUE_ADAPTER: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
_SCHEMA_NAME = "operator_message_v1"


class HistoryMessageTransform:
  """Translate between history schemas and stable Operator message DTOs."""

  def to_operator_message(
    self, *, message: HistoryMessageSchema
  ) -> OperatorMessage:
    """Convert one persisted history message to a stable Operator message."""
    if operator_message := _stable_payload_to_operator_message(
      message.json_contents
    ):
      return _with_author_id(operator_message, message.author_id)
    return _legacy_history_message_to_operator_message(message)

  def to_operator_messages(
    self,
    *,
    messages: Sequence[HistoryMessageSchema],
  ) -> list[OperatorMessage]:
    """Convert persisted history messages to stable Operator messages."""
    return [
      self.to_operator_message(message=message)
      for message in messages
    ]

  def to_history_request(
    self,
    *,
    message: OperatorMessage,
    author_id: str | None = None,
  ) -> HistoryMessageRequestSchema:
    """Convert one stable Operator message to a history append request."""
    return HistoryMessageRequestSchema(
      role=_role_from_operator_message(message),
      author_id=author_id or message.author_id,
      text_contents=_text_contents_from_operator_message(message),
      binary_contents=_binary_contents_from_operator_message(message),
      json_contents=_operator_message_to_json_payload(message),
      extra_metadata={"operator_message_schema": _SCHEMA_NAME},
    )

  def to_history_requests(
    self,
    *,
    messages: Sequence[OperatorMessage],
    author_id: str | None = None,
  ) -> list[HistoryMessageRequestSchema]:
    """Convert stable Operator messages to history append requests."""
    return [
      self.to_history_request(message=message, author_id=author_id)
      for message in messages
    ]


def _stable_payload_to_operator_message(
  payload: JsonPayload,
) -> OperatorMessage | None:
  if not isinstance(payload, dict):
    return None
  if payload.get("schema_name") != _SCHEMA_NAME:
    return None
  try:
    return _OPERATOR_MESSAGE_ADAPTER.validate_python(payload)
  except ValidationError as error:
    raise ProviderTransformError from error


def _with_author_id(
  message: OperatorMessage, author_id: str | None
) -> OperatorMessage:
  if author_id is None:
    return message
  match message:
    case OperatorRequestMessage():
      return message.model_copy(update={"author_id": author_id})
    case OperatorResponseMessage():
      return message.model_copy(update={"author_id": author_id})


def _operator_message_to_json_payload(
  message: OperatorMessage,
) -> JsonPayload:
  payload: object = _OPERATOR_MESSAGE_ADAPTER.dump_python(
    message, mode="json"
  )
  return _json_payload(payload)


def _legacy_history_message_to_operator_message(
  message: HistoryMessageSchema,
) -> OperatorMessage:
  timestamp = _history_message_timestamp(message)
  match message.role:
    case HistoryMessageRole.SYSTEM:
      result = OperatorRequestMessage(
        parts=[
          OperatorSystemPromptPart(
            content=_require_text(message), timestamp=timestamp
          )
        ],
        timestamp=timestamp,
        author_id=message.author_id,
      )
    case HistoryMessageRole.USER | HistoryMessageRole.AGENT_OTHER:
      result = OperatorRequestMessage(
        parts=[
          OperatorUserPromptPart(
            content=_require_text(message), timestamp=timestamp
          )
        ],
        timestamp=timestamp,
        author_id=message.author_id,
      )
    case HistoryMessageRole.AGENT_SELF:
      result = OperatorResponseMessage(
        parts=[OperatorTextPart(content=_require_text(message))],
        timestamp=timestamp,
        author_id=message.author_id,
      )
    case HistoryMessageRole.AGENT_SELF_THINKING:
      result = OperatorResponseMessage(
        parts=[OperatorThinkingPart(content=_require_text(message))],
        timestamp=timestamp,
        author_id=message.author_id,
      )
    case HistoryMessageRole.TOOL_CALL:
      result = _legacy_tool_call_message(
        message=message, timestamp=timestamp
      )
    case HistoryMessageRole.TOOL_REPLY:
      result = _legacy_tool_return_message(
        message=message, timestamp=timestamp
      )
    case HistoryMessageRole.TOOL_RETRY:
      result = _legacy_retry_message(
        message=message, timestamp=timestamp
      )
    case _:
      raise ProviderTransformError
  return result


def _legacy_tool_call_message(
  *,
  message: HistoryMessageSchema,
  timestamp: datetime | None,
) -> OperatorResponseMessage:
  payload = _require_json_object(message)
  return OperatorResponseMessage(
    parts=[
      OperatorToolCallPart(
        tool_name=_require_string(payload.get("tool_name")),
        args=_optional_tool_args(payload.get("args")),
        tool_call_id=_require_string(payload.get("tool_call_id")),
      )
    ],
    timestamp=timestamp,
    author_id=message.author_id,
  )


def _legacy_tool_return_message(
  *,
  message: HistoryMessageSchema,
  timestamp: datetime | None,
) -> OperatorRequestMessage:
  payload = _require_json_object(message)
  return OperatorRequestMessage(
    parts=[
      OperatorToolReturnPart(
        tool_name=_require_string(payload.get("tool_name")),
        content=_json_value(payload.get("content")),
        tool_call_id=_require_string(payload.get("tool_call_id")),
        timestamp=timestamp,
      )
    ],
    timestamp=timestamp,
    author_id=message.author_id,
  )


def _legacy_retry_message(
  *,
  message: HistoryMessageSchema,
  timestamp: datetime | None,
) -> OperatorRequestMessage:
  payload = _require_json_object(message)
  return OperatorRequestMessage(
    parts=[
      OperatorRetryPromptPart(
        content=_retry_content(payload.get("content")),
        tool_name=_optional_string(payload.get("tool_name")),
        tool_call_id=_require_string(payload.get("tool_call_id")),
        timestamp=timestamp,
      )
    ],
    timestamp=timestamp,
    author_id=message.author_id,
  )


def _history_message_timestamp(
  message: HistoryMessageSchema,
) -> datetime | None:
  if isinstance(message, HistoryMessageResponseSchema):
    return message.updated_at
  return None


def _require_text(message: HistoryMessageSchema) -> str:
  if message.text_contents is None:
    raise ProviderTransformError
  return message.text_contents


def _require_json_object(message: HistoryMessageSchema) -> JsonObject:
  return _json_object(message.json_contents)


def _role_from_operator_message(
  message: OperatorMessage,
) -> HistoryMessageRole:
  first_part = _first_part(message)
  match first_part:
    case OperatorSystemPromptPart():
      role = HistoryMessageRole.SYSTEM
    case OperatorUserPromptPart():
      role = HistoryMessageRole.USER
    case OperatorTextPart():
      role = HistoryMessageRole.AGENT_SELF
    case OperatorThinkingPart():
      role = HistoryMessageRole.AGENT_SELF_THINKING
    case OperatorToolCallPart():
      role = HistoryMessageRole.TOOL_CALL
    case OperatorToolReturnPart():
      role = HistoryMessageRole.TOOL_REPLY
    case OperatorRetryPromptPart():
      role = HistoryMessageRole.TOOL_RETRY
    case OperatorFilePart():
      role = HistoryMessageRole.FILE_SELF
  return role


def _first_part(
  message: OperatorMessage,
) -> (
  OperatorSystemPromptPart
  | OperatorUserPromptPart
  | OperatorToolReturnPart
  | OperatorRetryPromptPart
  | OperatorTextPart
  | OperatorThinkingPart
  | OperatorToolCallPart
  | OperatorFilePart
):
  if not message.parts:
    raise ProviderTransformError
  return message.parts[0]


def _text_contents_from_operator_message(
  message: OperatorMessage,
) -> str | None:
  if len(message.parts) != 1:
    return None
  part = message.parts[0]
  match part:
    case (
      OperatorSystemPromptPart()
      | OperatorUserPromptPart()
      | OperatorTextPart()
      | OperatorThinkingPart()
    ):
      return part.content
    case _:
      return None


def _binary_contents_from_operator_message(
  message: OperatorMessage,
) -> bytes | None:
  if len(message.parts) != 1:
    return None
  part = message.parts[0]
  match part:
    case OperatorFilePart():
      return part.data
    case _:
      return None


def _optional_tool_args(value: object) -> str | JsonObject | None:
  if value is None or isinstance(value, str):
    return value
  return _json_object(value)


def _retry_content(value: object) -> str | list[JsonObject]:
  if isinstance(value, str):
    return value
  if isinstance(value, list):
    try:
      return _JSON_OBJECT_LIST_ADAPTER.validate_python(value)
    except ValidationError as error:
      raise ProviderTransformError from error
  raise ProviderTransformError


def _optional_string(value: object) -> str | None:
  if value is None or isinstance(value, str):
    return value
  raise ProviderTransformError


def _require_string(value: object) -> str:
  if not isinstance(value, str):
    raise ProviderTransformError
  return value


def _json_payload(value: object) -> JsonPayload:
  try:
    return _JSON_PAYLOAD_ADAPTER.validate_python(value)
  except ValidationError as error:
    raise ProviderTransformError from error


def _json_object(value: object) -> JsonObject:
  try:
    return _JSON_OBJECT_ADAPTER.validate_python(value)
  except ValidationError as error:
    raise ProviderTransformError from error


def _json_value(value: object) -> JsonValue:
  try:
    return _JSON_VALUE_ADAPTER.validate_python(value)
  except ValidationError as error:
    raise ProviderTransformError from error


__all__ = ["HistoryMessageTransform"]
