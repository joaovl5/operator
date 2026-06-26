from collections.abc import AsyncIterator  # noqa: TC003
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

type DbSession = AsyncSession | async_sessionmaker[AsyncSession]


class BaseService:
    @asynccontextmanager
    async def session(
        self,
        db_session: DbSession | None,
        *,
        transaction: bool = True,
    ) -> AsyncIterator[AsyncSession]:
        """Yield a bound async session from a session or sessionmaker."""
        if db_session is None:
            message = (
                "db_session is required; pass an AsyncSession or async_sessionmaker[AsyncSession]"
            )
            raise RuntimeError(message)

        if isinstance(db_session, AsyncSession):
            if transaction and not db_session.in_transaction():
                async with db_session.begin():
                    yield db_session
            else:
                yield db_session
            return

        async with db_session() as session:
            if transaction:
                async with session.begin():
                    yield session
            else:
                yield session
