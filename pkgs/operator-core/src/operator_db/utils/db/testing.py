"""Testing helpers for operator_db integration tests."""

from collections.abc import AsyncIterator  # noqa: TC003
from contextlib import asynccontextmanager
from typing import Protocol

from attrs import define
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import StaticPool

import operator_db


class _SqliteCursor(Protocol):
    def execute(self, statement: str, /) -> object: ...
    def close(self) -> None: ...


class _SqliteConnection(Protocol):
    def cursor(self) -> _SqliteCursor: ...


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

    def enable_sqlite_foreign_keys(
        dbapi_connection: _SqliteConnection,
        _: object,
    ) -> None:
        cursor = dbapi_connection.cursor()
        _ = cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    event.listen(engine.sync_engine, "connect", enable_sqlite_foreign_keys)

    try:
        async with engine.begin() as conn:
            await conn.run_sync(operator_db.Base.metadata.create_all)

        yield TmpSqliteDb(engine=engine, sessionmaker=sessionmaker)
    finally:
        await engine.dispose()


__all__ = ["TmpSqliteDb", "tmp_sqlite_db"]
