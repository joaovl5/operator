"""Testing helpers for operator_db integration tests."""

from collections.abc import AsyncIterator  # noqa: TC003
from contextlib import asynccontextmanager

from attrs import define
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import operator_db


@define(frozen=True, kw_only=True)
class TmpSqliteDb:
    """Temporary async SQLite DB handles."""

    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]


@asynccontextmanager
async def tmp_sqlite_db() -> AsyncIterator[TmpSqliteDb]:
    """Yield an in-memory async SQLite database with operator_db tables."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(operator_db.Base.metadata.create_all)

        yield TmpSqliteDb(engine=engine, sessionmaker=sessionmaker)
    finally:
        await engine.dispose()


__all__ = ["TmpSqliteDb", "tmp_sqlite_db"]
