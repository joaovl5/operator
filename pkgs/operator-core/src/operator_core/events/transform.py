from typing import TYPE_CHECKING

from operator_db.objects import ContextEvent
from operator_db.objects.context_event import (
  CtxEvent,
  events_to_pyai_msg,
)

if TYPE_CHECKING:
  from collections.abc import Sequence

  from pydantic_ai import ModelMessage

# used privately as shorthand
_Ev = ContextEvent


async def events_to_msgs(
  events: Sequence[CtxEvent],
) -> list[ModelMessage]:
  """Turn events into Pydantic AI `ModelMessage` type.

  IMPORTANT: This assumes `events` were already loaded and populated via ORM,
  typically can be done via `walk_up_to`.
  """
  out: list[ModelMessage] = []

  i: int = 0
  while i < len(events):
    event: CtxEvent = events[i]
    match event:
      case _Ev.Message():
        group, i = _gather_msg_group(events, i)
        pyai_msg = await events_to_pyai_msg(
          group, session=None, refresh=False
        )
        out.append(pyai_msg)
        continue
      case _:
        pass
    i += 1

  return out


def _gather_msg_group(
  events: Sequence[CtxEvent], i: int
) -> tuple[list[_Ev.Message], int]:
  """Collect all messages within the same group and advance `i`.

  Returns a tuple of the collected messages, as well as the next unread index.
  This expects `i` is within the position of the first message already.
  """
  group: list[_Ev.Message] = []

  while i < len(events):
    msg = events[i]
    if not isinstance(msg, _Ev.Message):
      break
    if group and group[-1].message_group_id != msg.message_group_id:
      break
    if (msg.message_group_id is None) != (msg.message_group is None):
      error_msg = (
        "`message_group` and its ID must be both existing or absent!"
      )
      raise ValueError(error_msg)
    group.append(msg)
    i += 1
    if msg.message_group_id is None:
      break

  return group, i
