"""Stable message DTOs for provider transforms."""

from datetime import datetime
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field

JsonScalar = str | int | float | bool | None
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]
type OperatorFinishReason = Literal["stop", "length", "content_filter", "tool_call", "error"]

_TRANSFORM_SCHEMA_NAME = "operator_message_v1"


class TransformDTO(BaseModel):
    """Base class for stable transform DTOs."""

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="forbid",
        ser_json_bytes="base64",
        val_json_bytes="base64",
    )


class OperatorUsage(TransformDTO):
    """Stable model usage metadata."""

    input_tokens: int = 0
    cache_write_tokens: int = 0
    cache_read_tokens: int = 0
    output_tokens: int = 0
    input_audio_tokens: int = 0
    cache_audio_read_tokens: int = 0
    output_audio_tokens: int = 0
    details: dict[str, int] = Field(default_factory=dict)


class OperatorSystemPromptPart(TransformDTO):
    """System prompt request part."""

    part_kind: Literal["system_prompt"] = "system_prompt"
    content: str
    timestamp: datetime | None = None
    dynamic_ref: str | None = None


class OperatorUserPromptPart(TransformDTO):
    """User prompt request part."""

    part_kind: Literal["user_prompt"] = "user_prompt"
    content: str
    timestamp: datetime | None = None


class OperatorToolReturnPart(TransformDTO):
    """Tool return request part."""

    part_kind: Literal["tool_return"] = "tool_return"
    tool_name: str
    content: JsonValue
    tool_call_id: str
    metadata: JsonValue = None
    timestamp: datetime | None = None
    outcome: Literal["success", "failed", "denied"] = "success"
    provider_name: str | None = None
    provider_details: JsonObject | None = None
    builtin: bool = False


class OperatorRetryPromptPart(TransformDTO):
    """Retry request part."""

    part_kind: Literal["retry_prompt"] = "retry_prompt"
    content: str | list[JsonObject]
    tool_name: str | None = None
    tool_call_id: str
    timestamp: datetime | None = None


class OperatorTextPart(TransformDTO):
    """Agent text response part."""

    part_kind: Literal["text"] = "text"
    content: str
    id: str | None = None
    provider_name: str | None = None
    provider_details: JsonObject | None = None


class OperatorThinkingPart(TransformDTO):
    """Agent thinking response part."""

    part_kind: Literal["thinking"] = "thinking"
    content: str
    id: str | None = None
    signature: str | None = None
    provider_name: str | None = None
    provider_details: JsonObject | None = None


class OperatorToolCallPart(TransformDTO):
    """Tool call response part."""

    part_kind: Literal["tool_call"] = "tool_call"
    tool_name: str
    args: str | JsonObject | None = None
    tool_call_id: str
    id: str | None = None
    provider_name: str | None = None
    provider_details: JsonObject | None = None
    builtin: bool = False


class OperatorFilePart(TransformDTO):
    """Binary file response part."""

    part_kind: Literal["file"] = "file"
    data: bytes
    media_type: str
    identifier: str | None = None
    vendor_metadata: JsonObject | None = None
    id: str | None = None
    provider_name: str | None = None
    provider_details: JsonObject | None = None


type OperatorRequestPart = (
    OperatorSystemPromptPart
    | OperatorUserPromptPart
    | OperatorToolReturnPart
    | OperatorRetryPromptPart
)
type OperatorResponsePart = (
    OperatorTextPart
    | OperatorThinkingPart
    | OperatorToolCallPart
    | OperatorToolReturnPart
    | OperatorFilePart
)


class OperatorRequestMessage(TransformDTO):
    """Stable request-side provider message."""

    schema_name: Literal["operator_message_v1"] = _TRANSFORM_SCHEMA_NAME
    kind: Literal["request"] = "request"
    parts: list[OperatorRequestPart]
    timestamp: datetime | None = None
    instructions: str | None = None
    run_id: str | None = None
    metadata: JsonObject | None = None
    author_id: str | None = None


class OperatorResponseMessage(TransformDTO):
    """Stable response-side provider message."""

    schema_name: Literal["operator_message_v1"] = _TRANSFORM_SCHEMA_NAME
    kind: Literal["response"] = "response"
    parts: list[OperatorResponsePart]
    timestamp: datetime | None = None
    usage: OperatorUsage = Field(default_factory=OperatorUsage)
    model_name: str | None = None
    provider_name: str | None = None
    provider_url: str | None = None
    provider_details: JsonObject | None = None
    provider_response_id: str | None = None
    finish_reason: OperatorFinishReason | None = None
    run_id: str | None = None
    metadata: JsonObject | None = None
    author_id: str | None = None


type OperatorMessage = OperatorRequestMessage | OperatorResponseMessage

__all__ = [
    "JsonObject",
    "JsonScalar",
    "JsonValue",
    "OperatorFilePart",
    "OperatorFinishReason",
    "OperatorMessage",
    "OperatorRequestMessage",
    "OperatorRequestPart",
    "OperatorResponseMessage",
    "OperatorResponsePart",
    "OperatorRetryPromptPart",
    "OperatorSystemPromptPart",
    "OperatorTextPart",
    "OperatorThinkingPart",
    "OperatorToolCallPart",
    "OperatorToolReturnPart",
    "OperatorUsage",
    "OperatorUserPromptPart",
    "TransformDTO",
]
