"""Database engine construction and migration readiness helpers."""

from pathlib import Path
from typing import Protocol

from alembic import command
from alembic.config import Config as AlembicConfig
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from alembic.script.revision import ResolutionError
from alembic.util.exc import CommandError
from sqlalchemy import create_engine, event, inspect
from sqlalchemy.engine import Connection, make_url
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from operator_db.connection.errors import OperatorDbMigrationError


class DatabaseConfigProtocol(Protocol):
    """Database settings required by connection helpers."""

    url: str


class _SqliteCursor(Protocol):
    def execute(self, statement: str, /) -> object: ...
    def close(self) -> None: ...


class _SqliteConnection(Protocol):
    def cursor(self) -> _SqliteCursor: ...


def ensure_db_ready(*, config: DatabaseConfigProtocol) -> None:
    """Ensure the configured database exists and is migrated to Alembic head."""
    db_url = get_db_url(config=config)
    db_path = _sqlite_db_path(db_url)
    db_file_existed = db_path   and db_path.is_file()

    if db_path  :
        db_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(_sync_db_url(db_url))
    try:
        with engine.begin() as connection:
            _ensure_connection_at_head(
                connection=connection,
                db_file_existed=db_file_existed,
                alembic_config=_alembic_config(db_url=db_url),
            )
    finally:
        engine.dispose()


def get_db_url(*, config: DatabaseConfigProtocol) -> str:
    """Return the configured database URL."""
    return config.url


def get_db_engine(*, config: DatabaseConfigProtocol) -> AsyncEngine:
    """Create an application async database engine after migration readiness checks."""
    ensure_db_ready(config=config)
    engine = create_async_engine(get_db_url(config=config))
    event.listen(engine.sync_engine, "connect", _enable_sqlite_foreign_keys)
    return engine


def _ensure_connection_at_head(
    *,
    connection: Connection,
    db_file_existed: bool,
    alembic_config: AlembicConfig,
) -> None:
    script = ScriptDirectory.from_config(alembic_config)
    target_heads = set(script.get_heads())
    current_heads = set(MigrationContext.configure(connection).get_current_heads())

    if current_heads == target_heads:
        return

    _raise_for_unknown_heads(current_heads=current_heads, script=script)

    if not current_heads and db_file_existed and _has_unmanaged_tables(connection=connection):
        message = "database has tables but no Alembic revision; refusing to migrate unmanaged schema"
        raise OperatorDbMigrationError(message)

    alembic_config.attributes["connection"] = connection
    command.upgrade(alembic_config, "head")


def _raise_for_unknown_heads(*, current_heads: set[str], script: ScriptDirectory) -> None:
    unknown_heads: list[str] = []
    for head in current_heads:
        try:
            _ = script.get_revision(head)
        except (CommandError, ResolutionError):
            unknown_heads.append(head)
    if unknown_heads:
        revisions = ", ".join(sorted(unknown_heads))
        message = f"database is at unknown Alembic revision(s): {revisions}"
        raise OperatorDbMigrationError(message)


def _has_unmanaged_tables(*, connection: Connection) -> bool:
    table_names = set(inspect(connection).get_table_names())
    return bool(table_names - {"alembic_version"})


def _alembic_config(*, db_url: str) -> AlembicConfig:
    package_root = _package_root()
    config = AlembicConfig(
        file_=package_root / "alembic.ini",
        toml_file=package_root / "pyproject.toml",
    )
    config.set_main_option("sqlalchemy.url", db_url)
    return config


def _package_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _sync_db_url(db_url: str) -> str:
    url = make_url(db_url)
    if url.drivername == "sqlite+aiosqlite":
        return url.set(drivername="sqlite").render_as_string(hide_password=False)
    return db_url


def _sqlite_db_path(db_url: str) -> Path | None:
    url = make_url(db_url)
    if not url.drivername.startswith("sqlite"):
        return None
    if url.database is None or url.database in {"", ":memory:"}:
        return None
    return Path(url.database)


def _enable_sqlite_foreign_keys(dbapi_connection: _SqliteConnection, _: object) -> None:
    cursor = dbapi_connection.cursor()
    _ = cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


__all__ = ["DatabaseConfigProtocol", "ensure_db_ready", "get_db_engine", "get_db_url"]
