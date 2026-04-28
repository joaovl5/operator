from typing import TYPE_CHECKING

from sqlalchemy import inspect, select

from operator_db.utils.db.base import Base
from operator_db.utils.db.testing import tmp_sqlite_db

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection


def get_table_names(sync_conn: Connection) -> set[str]:
    """Return the reflected table names for the temporary SQLite database."""
    return set(inspect(sync_conn).get_table_names())


async def test_tmp_sqlite_db_creates_operator_tables_and_sessions() -> None:
    """Temporary SQLite helper creates the schema and usable async sessions."""
    async with tmp_sqlite_db() as db:
        async with db.sessionmaker() as session:
            result = await session.execute(select(1))

        assert result.scalar_one() == 1

        async with db.engine.begin() as conn:
            table_names = await conn.run_sync(get_table_names)

        assert set(Base.metadata.tables) <= table_names
