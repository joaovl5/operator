from typing import TYPE_CHECKING

import pytest
from sqlalchemy import inspect, select
from sqlalchemy.exc import IntegrityError

from operator_db.objects.agent.entity import SessionAgentEnt
from operator_db.objects.history.entity import HistoryEnt
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



async def test_tmp_sqlite_db_enforces_foreign_keys() -> None:
    """Temporary SQLite helper enforces foreign keys on committed rows."""
    async with tmp_sqlite_db() as db, db.sessionmaker() as session:
        history = HistoryEnt()
        session.add(history)
        await session.flush()

        session.add(
            SessionAgentEnt(
                session_id="missing-session",
                history_id=history.id,
                local_id="agent-1",
            )
        )

        with pytest.raises(IntegrityError):
            await session.commit()
