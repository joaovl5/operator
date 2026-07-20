from enum import StrEnum
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, JsonValue

from operator_db.objects.base import IDType

if TYPE_CHECKING:
  from sqlalchemy.ext.asyncio import AsyncSession

  from operator_db.objects.context_event import CtxEvent


class StopAgentMethod(StrEnum):
  KILL = "kill"
  """Don't wait for anything and just abort any agent-related
  tasks."""

  WAIT_LOOP = "wait-loop"
  """Stop after agent's loop is done."""

  WAIT_TURN = "wait-turn"
  """Stop after agent's loop turn is done."""


class IncomingMessage(BaseModel):
  """Message object for communication to/from agent/user."""

  text_data: str | None = None
  json_data: JsonValue | None = None
  bytes_data: bytes | None = None


class EventPointer(BaseModel):
  """Stores position on the context tree."""

  event_id: IDType
  context_id: IDType

  @classmethod
  async def from_event(
    cls, *, event: CtxEvent, session: AsyncSession
  ) -> Self:
    """Returns a pointer to `event`."""
    await session.refresh(event, attribute_names=("id", "context_id"))
    return cls(
      event_id=event.id,
      context_id=event.context_id,
    )
