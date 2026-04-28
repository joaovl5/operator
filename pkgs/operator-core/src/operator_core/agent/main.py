from asyncio import Lock
from typing import TYPE_CHECKING

from attrs import Factory, define, field
from pydantic import ValidationError
from pydantic_ai import (
    Agent,
    ModelMessage,
    ModelMessagesTypeAdapter,
    ModelRequest,
    ModelRequestPart,
    ModelResponse,
    ModelResponsePart,
    SystemPromptPart,
    TextPart,
    ThinkingPart,
    UserPromptPart,
)

from operator_core.agent.errors import OpAgentMessageError
from operator_db.constants import HistoryMessageRole

if TYPE_CHECKING:
    from collections.abc import Sequence

    from pydantic_ai.models import Model

    from operator_core.permissions import PermissionGroup
    from operator_db.objects.history.schema import HistoryMessageResponseSchema


_REQUEST_PART_KINDS = frozenset(
    {
        "system-prompt",
        "user-prompt",
        "tool-return",
        "retry-prompt",
    }
)
_RESPONSE_PART_KINDS = frozenset(
    {
        "text",
        "thinking",
        "tool-call",
        "builtin-tool-call",
        "builtin-tool-return",
        "file",
    }
)


def _mk_model_req(
    msg: HistoryMessageResponseSchema,
    parts: ModelRequestPart | list[ModelRequestPart],
) -> ModelRequest:
    parts_list: list[ModelRequestPart]
    match parts:
        case list(x):
            parts_list = x
        case _:
            parts_list = [parts]

    return ModelRequest(
        parts_list,
        timestamp=msg.updated_at,
    )


def _mk_model_res(
    msg: HistoryMessageResponseSchema,
    parts: ModelResponsePart | list[ModelResponsePart],
) -> ModelResponse:
    parts_list: list[ModelResponsePart]
    match parts:
        case list(x):
            parts_list = x
        case _:
            parts_list = [parts]

    return ModelResponse(
        parts_list,
        timestamp=msg.updated_at,
    )


def _parse_pydantic_msg(payload: dict[str, object]) -> ModelMessage:
    try:
        messages = ModelMessagesTypeAdapter.validate_python([payload])
    except ValidationError as error:
        raise OpAgentMessageError from error

    if len(messages) != 1:
        raise OpAgentMessageError

    return messages[0]


def _json_contents_to_pydantic_msg(msg: HistoryMessageResponseSchema) -> ModelMessage | None:
    contents = msg.json_contents
    if not isinstance(contents, dict):
        return None

    if "kind" in contents or "parts" in contents:
        return _parse_pydantic_msg(contents)

    part_kind = contents.get("part_kind")
    if part_kind in _REQUEST_PART_KINDS:
        part_payload = (
            contents if "timestamp" in contents else {**contents, "timestamp": msg.updated_at}
        )
        return _parse_pydantic_msg(
            {
                "kind": "request",
                "parts": [part_payload],
                "timestamp": msg.updated_at,
            }
        )
    if part_kind in _RESPONSE_PART_KINDS:
        return _parse_pydantic_msg(
            {
                "kind": "response",
                "parts": [contents],
                "timestamp": msg.updated_at,
            }
        )
    if part_kind is not None:
        raise OpAgentMessageError

    return None


def _require_text_contents(msg: HistoryMessageResponseSchema) -> str:
    if msg.text_contents is None:
        raise OpAgentMessageError
    return msg.text_contents


def _history_msg_to_pydantic_msg(msg: HistoryMessageResponseSchema) -> ModelMessage:
    if pydantic_msg := _json_contents_to_pydantic_msg(msg):
        return pydantic_msg

    text_contents = _require_text_contents(msg)
    match msg.role:
        case HistoryMessageRole.SYSTEM:
            return _mk_model_req(
                msg,
                SystemPromptPart(text_contents, timestamp=msg.updated_at),
            )
        case HistoryMessageRole.USER | HistoryMessageRole.AGENT_OTHER:
            return _mk_model_req(
                msg,
                UserPromptPart(text_contents, timestamp=msg.updated_at),
            )
        case HistoryMessageRole.AGENT_SELF:
            return _mk_model_res(msg, TextPart(text_contents))
        case HistoryMessageRole.AGENT_SELF_THINKING:
            return _mk_model_res(msg, ThinkingPart(text_contents))
        case _:
            raise OpAgentMessageError


@define(kw_only=True)
class OpAgent:
    """Simple agent for testing."""

    id: str
    model: Model
    system_prompt: str
    permissions: PermissionGroup
    lock: Lock = Factory(Lock)
    agent: Agent = field(init=False)

    def __attrs_post_init__(self) -> None:
        """Initialize internal pydantic-ai agent."""
        self.agent = Agent(
            model=self.model,
        )

    async def run(
        self,
        *,
        messages: Sequence[HistoryMessageResponseSchema] = (),
    ) -> None:
        """Run a turn with agent."""
        message_history = [_history_msg_to_pydantic_msg(msg) for msg in messages]
        _ = await self.agent.run(message_history=message_history)
