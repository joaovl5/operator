from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator


class BaseService:
    async def session(
        self,
        session: AsyncSession | None,
        *,
        transaction: bool = True,
    ) -> AsyncGenerator[AsyncSession]:
        """Yields an AsyncSession, either from the passed argument or generated lazily."""
        if not session:
            session = AsyncSession()
        if transaction:
            async with session.begin():
                yield session
        else:
            yield session
