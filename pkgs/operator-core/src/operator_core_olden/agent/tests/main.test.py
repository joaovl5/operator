from datetime import UTC, datetime
from functools import partial
from typing import TYPE_CHECKING

from operator_core_olden.agent.main import (
  _forward_streaming_events,
  _without_replayed_prefix,
)
from operator_core_olden.providers.transforms import (
  PydanticAIStreamTransform,
)
from operator_shared.providers.transforms import (
  OperatorRequestMessage,
  OperatorResponseMessage,
  OperatorSystemPromptPart,
  OperatorTextPart,
  OperatorToolReturnPart,
  OperatorUserPromptPart,
)

if TYPE_CHECKING:
  from collections.abc import AsyncIterator

  from pydantic_ai import AgentStreamEvent as PydanticAIStreamEvent

  from operator_core_olden.agent.streaming import (
    AgentStreamEvent as OperatorStreamEvent,
  )

PROMPT_AT = datetime(2026, 1, 1, tzinfo=UTC)
REPLAY_AT = datetime(2026, 1, 2, tzinfo=UTC)
RESPONSE_AT = datetime(2026, 1, 3, tzinfo=UTC)


async def _iter_events(
  *events: PydanticAIStreamEvent,
) -> AsyncIterator[PydanticAIStreamEvent]:
  for event in events:
    yield event


async def test_forward_streaming_events_accepts_pydantic_ai_api() -> (
  None
):
  """PydanticAI passes run context and stream events positionally."""
  forwarded_events: list[OperatorStreamEvent] = []

  async def sink(*, event: OperatorStreamEvent) -> None:
    forwarded_events.append(event)

  handler = partial(
    _forward_streaming_events,
    stream_transform=PydanticAIStreamTransform(),
    sink=sink,
  )

  await handler(object(), _iter_events())

  assert forwarded_events == []


def test_without_replayed_prefix_strips_first_prompt_replay() -> (
  None
):
  """Provider-owned prompt metadata does not make persisted prompts
  new again."""
  response = OperatorResponseMessage(
    parts=[OperatorTextPart(content="done")],
    timestamp=RESPONSE_AT,
  )

  result = _without_replayed_prefix(
    previous_messages=[
      OperatorRequestMessage(
        parts=[OperatorSystemPromptPart(content="system")],
        timestamp=PROMPT_AT,
        author_id="agent",
      ),
      OperatorRequestMessage(
        parts=[
          OperatorUserPromptPart(content="hello", timestamp=PROMPT_AT)
        ],
        timestamp=PROMPT_AT,
        author_id="agent",
      ),
    ],
    candidate_messages=[
      OperatorRequestMessage(
        parts=[
          OperatorSystemPromptPart(
            content="system", timestamp=REPLAY_AT
          ),
          OperatorUserPromptPart(
            content="hello", timestamp=REPLAY_AT
          ),
        ],
        timestamp=REPLAY_AT,
        run_id="current-run",
      ),
      response,
    ],
  )

  assert result == [response]


def test_without_replayed_prefix_keeps_non_replayed_requests() -> (
  None
):
  """Only duplicated prompt requests are stripped from new message
  candidates."""
  previous_messages = [
    OperatorRequestMessage(
      parts=[
        OperatorUserPromptPart(content="hello", timestamp=PROMPT_AT)
      ],
      timestamp=PROMPT_AT,
      author_id="agent",
    )
  ]
  different_prompt = OperatorRequestMessage(
    parts=[
      OperatorUserPromptPart(content="different", timestamp=REPLAY_AT)
    ],
    timestamp=REPLAY_AT,
  )
  tool_return = OperatorRequestMessage(
    parts=[
      OperatorToolReturnPart(
        tool_name="file_read",
        content="contents",
        tool_call_id="call-1",
        timestamp=REPLAY_AT,
      )
    ],
    timestamp=REPLAY_AT,
  )

  assert _without_replayed_prefix(
    previous_messages=previous_messages,
    candidate_messages=[different_prompt, tool_return],
  ) == [different_prompt, tool_return]
