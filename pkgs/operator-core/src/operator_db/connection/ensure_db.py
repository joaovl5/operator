from operator_db.alembic.env import run_async_migrations


async def ensure_db_ready() -> None:
  """Ensure database is ready with all migrations."""
  await run_async_migrations()
