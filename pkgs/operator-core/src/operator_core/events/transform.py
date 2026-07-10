from pydantic_ai import ModelMessage
from sqlalchemy.ext.asyncio import AsyncSession

from operator_db.objects import ContextEvent
from operator_db.objects.context import CtxEvent

# used privately as shorthand
type _Ev = ContextEvent


async def event_to_msg(
    event: CtxEvent,
    session: AsyncSession,
) -> ModelMessage | None:
    """Turn event into Pydantic AI `ModelMessage` type."""
    match event:
        case _Ev.Message():
            pass
        case _:
            return None
