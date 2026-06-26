"""PydanticAI provider message transform."""

from datetime import UTC, datetime
from typing import override

from pydantic import TypeAdapter, ValidationError
from pydantic_ai import (
    BinaryContent,
    BuiltinToolCallPart,
    BuiltinToolReturnPart,
    FilePart,
    ModelMessage,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    ModelResponsePart,
    RetryPromptPart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.usage import RequestUsage
from pydantic_core import ErrorDetails, PydanticSerializationError

from operator_core_olden.providers.transforms.errors import (
    ProviderTransformError,
    UnsupportedProviderMessageError,
)
from operator_core_olden.providers.transforms.main import ProviderMessageTransform
from operator_shared.providers.transforms import (
    JsonObject,
    JsonValue,
    OperatorFilePart,
    OperatorMessage,
    OperatorRequestMessage,
    OperatorRequestPart,
    OperatorResponseMessage,
    OperatorResponsePart,
    OperatorRetryPromptPart,
    OperatorSystemPromptPart,
    OperatorTextPart,
    OperatorThinkingPart,
    OperatorToolCallPart,
    OperatorToolReturnPart,
    OperatorUsage,
    OperatorUserPromptPart,
)

_ERROR_DETAILS_ADAPTER: TypeAdapter[list[ErrorDetails]] = TypeAdapter(list[ErrorDetails])
_JSON_OBJECT_ADAPTER: TypeAdapter[JsonObject] = TypeAdapter(JsonObject)
_JSON_SAFE_ADAPTER: TypeAdapter[object] = TypeAdapter(object)
_JSON_VALUE_ADAPTER: TypeAdapter[JsonValue] = TypeAdapter(JsonValue)
_TOOL_RETURN_PART_ADAPTER: TypeAdapter[ToolReturnPart | BuiltinToolReturnPart] = TypeAdapter(
    ToolReturnPart | BuiltinToolReturnPart
)


class PydanticAIMessageTransform(ProviderMessageTransform[ModelMessage]):
    """Translate between stable Operator DTOs and PydanticAI messages."""

    @override
    def to_provider_message(self, *, message: OperatorMessage) -> ModelMessage:
        """Convert one stable Operator message to a PydanticAI message."""
        match message:
            case OperatorRequestMessage():
                return ModelRequest(
                    parts=[_request_part_to_provider(part) for part in message.parts],
                    timestamp=message.timestamp,
                    instructions=message.instructions,
                    run_id=message.run_id,
                    metadata=message.metadata,
                )
            case OperatorResponseMessage():
                return ModelResponse(
                    parts=[_response_part_to_provider(part) for part in message.parts],
                    usage=_usage_to_provider(message.usage),
                    model_name=message.model_name,
                    timestamp=message.timestamp or _now(),
                    provider_name=message.provider_name,
                    provider_url=message.provider_url,
                    provider_details=message.provider_details,
                    provider_response_id=message.provider_response_id,
                    finish_reason=message.finish_reason,
                    run_id=message.run_id,
                    metadata=message.metadata,
                )

    @override
    def from_provider_message(self, *, message: ModelMessage) -> OperatorMessage:
        """Convert one PydanticAI message to a stable Operator message."""
        match message:
            case ModelRequest():
                return OperatorRequestMessage(
                    parts=[_request_part_from_provider(part) for part in message.parts],
                    timestamp=message.timestamp,
                    instructions=message.instructions,
                    run_id=message.run_id,
                    metadata=_optional_json_object(message.metadata),
                )
            case ModelResponse():
                return OperatorResponseMessage(
                    parts=[_response_part_from_provider(part) for part in message.parts],
                    timestamp=message.timestamp,
                    usage=_usage_from_provider(message.usage),
                    model_name=message.model_name,
                    provider_name=message.provider_name,
                    provider_url=message.provider_url,
                    provider_details=_optional_json_object(message.provider_details),
                    provider_response_id=message.provider_response_id,
                    finish_reason=message.finish_reason,
                    run_id=message.run_id,
                    metadata=_optional_json_object(message.metadata),
                )


def _request_part_to_provider(part: OperatorRequestPart) -> ModelRequestPart:
    match part:
        case OperatorSystemPromptPart():
            return SystemPromptPart(
                content=part.content,
                timestamp=part.timestamp or _now(),
                dynamic_ref=part.dynamic_ref,
            )
        case OperatorUserPromptPart():
            return UserPromptPart(content=part.content, timestamp=part.timestamp or _now())
        case OperatorToolReturnPart():
            if part.builtin:
                raise UnsupportedProviderMessageError
            return ToolReturnPart(
                tool_name=part.tool_name,
                content=part.content,
                tool_call_id=part.tool_call_id,
                metadata=part.metadata,
                timestamp=part.timestamp or _now(),
                outcome=part.outcome,
            )
        case OperatorRetryPromptPart():
            return RetryPromptPart(
                content=_retry_content_to_provider(part.content),
                tool_name=part.tool_name,
                tool_call_id=part.tool_call_id,
                timestamp=part.timestamp or _now(),
            )


def _response_part_to_provider(part: OperatorResponsePart) -> ModelResponsePart:
    match part:
        case OperatorTextPart():
            return TextPart(
                content=part.content,
                id=part.id,
                provider_name=part.provider_name,
                provider_details=part.provider_details,
            )
        case OperatorThinkingPart():
            return ThinkingPart(
                content=part.content,
                id=part.id,
                signature=part.signature,
                provider_name=part.provider_name,
                provider_details=part.provider_details,
            )
        case OperatorToolCallPart() if part.builtin:
            return BuiltinToolCallPart(
                tool_name=part.tool_name,
                args=part.args,
                tool_call_id=part.tool_call_id,
                id=part.id,
                provider_name=part.provider_name,
                provider_details=part.provider_details,
            )
        case OperatorToolCallPart():
            return ToolCallPart(
                tool_name=part.tool_name,
                args=part.args,
                tool_call_id=part.tool_call_id,
                id=part.id,
                provider_name=part.provider_name,
                provider_details=part.provider_details,
            )
        case OperatorToolReturnPart():
            return BuiltinToolReturnPart(
                tool_name=part.tool_name,
                content=part.content,
                tool_call_id=part.tool_call_id,
                metadata=part.metadata,
                timestamp=part.timestamp or _now(),
                outcome=part.outcome,
                provider_name=part.provider_name,
                provider_details=part.provider_details,
            )
        case OperatorFilePart():
            return FilePart(
                content=BinaryContent(
                    data=part.data,
                    media_type=part.media_type,
                    identifier=part.identifier,
                    vendor_metadata=part.vendor_metadata,
                ),
                id=part.id,
                provider_name=part.provider_name,
                provider_details=part.provider_details,
            )


def _request_part_from_provider(part: ModelRequestPart) -> OperatorRequestPart:
    match part:
        case SystemPromptPart():
            return OperatorSystemPromptPart(
                content=part.content,
                timestamp=part.timestamp,
                dynamic_ref=part.dynamic_ref,
            )
        case UserPromptPart():
            if not isinstance(part.content, str):
                raise UnsupportedProviderMessageError
            return OperatorUserPromptPart(content=part.content, timestamp=part.timestamp)
        case ToolReturnPart():
            return OperatorToolReturnPart(
                tool_name=part.tool_name,
                content=_json_value(part.content),
                tool_call_id=part.tool_call_id,
                metadata=_tool_return_metadata(part),
                timestamp=part.timestamp,
                outcome=part.outcome,
            )
        case RetryPromptPart():
            return OperatorRetryPromptPart(
                content=_retry_content_from_provider(part.content),
                tool_name=part.tool_name,
                tool_call_id=part.tool_call_id,
                timestamp=part.timestamp,
            )


def _response_part_from_provider(part: ModelResponsePart) -> OperatorResponsePart:
    match part:
        case TextPart():
            return OperatorTextPart(
                content=part.content,
                id=part.id,
                provider_name=part.provider_name,
                provider_details=_optional_json_object(part.provider_details),
            )
        case ThinkingPart():
            return OperatorThinkingPart(
                content=part.content,
                id=part.id,
                signature=part.signature,
                provider_name=part.provider_name,
                provider_details=_optional_json_object(part.provider_details),
            )
        case BuiltinToolCallPart():
            return OperatorToolCallPart(
                tool_name=part.tool_name,
                args=_optional_tool_args(part.args),
                tool_call_id=part.tool_call_id,
                id=part.id,
                provider_name=part.provider_name,
                provider_details=_optional_json_object(part.provider_details),
                builtin=True,
            )
        case ToolCallPart():
            return OperatorToolCallPart(
                tool_name=part.tool_name,
                args=_optional_tool_args(part.args),
                tool_call_id=part.tool_call_id,
                id=part.id,
                provider_name=part.provider_name,
                provider_details=_optional_json_object(part.provider_details),
            )
        case BuiltinToolReturnPart():
            return OperatorToolReturnPart(
                tool_name=part.tool_name,
                content=_json_value(part.content),
                tool_call_id=part.tool_call_id,
                metadata=_tool_return_metadata(part),
                timestamp=part.timestamp,
                outcome=part.outcome,
                provider_name=part.provider_name,
                provider_details=_optional_json_object(part.provider_details),
                builtin=True,
            )
        case FilePart():
            return OperatorFilePart(
                data=part.content.data,
                media_type=part.content.media_type,
                identifier=part.content.identifier,
                vendor_metadata=_optional_json_object(part.content.vendor_metadata),
                id=part.id,
                provider_name=part.provider_name,
                provider_details=_optional_json_object(part.provider_details),
            )


def _usage_to_provider(usage: OperatorUsage) -> RequestUsage:
    return RequestUsage(
        input_tokens=usage.input_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        output_tokens=usage.output_tokens,
        input_audio_tokens=usage.input_audio_tokens,
        cache_audio_read_tokens=usage.cache_audio_read_tokens,
        output_audio_tokens=usage.output_audio_tokens,
        details=usage.details,
    )


def _usage_from_provider(usage: RequestUsage) -> OperatorUsage:
    return OperatorUsage(
        input_tokens=usage.input_tokens,
        cache_write_tokens=usage.cache_write_tokens,
        cache_read_tokens=usage.cache_read_tokens,
        output_tokens=usage.output_tokens,
        input_audio_tokens=usage.input_audio_tokens,
        cache_audio_read_tokens=usage.cache_audio_read_tokens,
        output_audio_tokens=usage.output_audio_tokens,
        details=usage.details,
    )


def _retry_content_to_provider(value: str | list[JsonObject]) -> str | list[ErrorDetails]:
    if isinstance(value, str):
        return value
    try:
        return _ERROR_DETAILS_ADAPTER.validate_python(value)
    except ValidationError as error:
        raise ProviderTransformError from error


def _retry_content_from_provider(value: str | list[ErrorDetails]) -> str | list[JsonObject]:
    if isinstance(value, str):
        return value
    return [_json_object(item) for item in value]


def _optional_tool_args(value: object) -> str | JsonObject | None:
    if value is None or isinstance(value, str):
        return value
    return _json_object(value)


def _optional_json_object(value: object) -> JsonObject | None:
    if value is None:
        return None
    return _json_object(value)


def _json_object(value: object) -> JsonObject:
    try:
        return _JSON_OBJECT_ADAPTER.validate_json(_JSON_SAFE_ADAPTER.dump_json(value))
    except (PydanticSerializationError, ValidationError) as error:
        raise UnsupportedProviderMessageError from error


def _json_value(value: object) -> JsonValue:
    try:
        return _JSON_VALUE_ADAPTER.validate_json(_JSON_SAFE_ADAPTER.dump_json(value))
    except (PydanticSerializationError, ValidationError) as error:
        raise UnsupportedProviderMessageError from error


def _tool_return_metadata(part: ToolReturnPart | BuiltinToolReturnPart) -> JsonValue:
    try:
        payload = _JSON_OBJECT_ADAPTER.validate_json(_TOOL_RETURN_PART_ADAPTER.dump_json(part))
    except (PydanticSerializationError, ValidationError) as error:
        raise UnsupportedProviderMessageError from error
    return payload.get("metadata")


def _now() -> datetime:
    return datetime.now(tz=UTC)


__all__ = ["PydanticAIMessageTransform"]
