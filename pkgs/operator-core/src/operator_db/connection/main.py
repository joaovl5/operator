"""Database engine construction and migration readiness helpers."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from operator_shared.settings.main import OperatorSettings


def get_async_engine(cfg: OperatorSettings) -> AsyncEngine:
    """Create an async engine from config."""
    return create_async_engine(
        url=cfg.database.connection_string,
    )


def get_sessionmaker(
    eng: AsyncEngine,
    *,
    expire_on_commit: bool = True,
) -> async_sessionmaker[AsyncSession]:
    """Create a session-maker."""
    return async_sessionmaker(
        eng,
        expire_on_commit=expire_on_commit,
    )


@asynccontextmanager
async def with_session(
    s: async_sessionmaker[AsyncSession],
    *,
    transaction: bool = True,
) -> AsyncGenerator[AsyncSession]:
    """Yields a session within possibly-transactional context.

    Args:
        s: Async session-maker.
        transaction: If set, will handle transaction operations.

    """
    async with s() as session:
        if transaction:
            await session.begin()
        try:
            yield session
        except Exception:
            if transaction:
                await session.rollback()
            raise
        finally:
            if transaction:
                await session.close()
