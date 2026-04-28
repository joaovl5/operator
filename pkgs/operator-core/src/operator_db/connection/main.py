"""Database engine construction helpers."""

from pathlib import Path
from typing import Protocol

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

_LOCAL_DB_PATH = Path(".operator") / "operator.sqlite3"


class _SqliteCursor(Protocol):
    def execute(self, statement: str, /) -> object: ...
    def close(self) -> None: ...


class _SqliteConnection(Protocol):
    def cursor(self) -> _SqliteCursor: ...


def _enable_sqlite_foreign_keys(dbapi_connection: _SqliteConnection, _: object) -> None:
    cursor = dbapi_connection.cursor()
    _ = cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def get_db_url() -> str:
    """Return the local SQLite database URL."""
    return f"sqlite+aiosqlite:///{_LOCAL_DB_PATH.as_posix()}"


def get_db_engine() -> AsyncEngine:
    """Create the application async database engine."""
    _LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    engine = create_async_engine(get_db_url())
    event.listen(engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    return engine
