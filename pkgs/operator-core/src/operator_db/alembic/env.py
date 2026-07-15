import asyncio
from functools import cache
from typing import TYPE_CHECKING, Any, Literal

from advanced_alchemy.alembic.commands import AlembicCommandConfig
from alembic import context
from alembic.autogenerate import rewriter

from operator_db.connection.main import get_async_engine
from operator_db.objects import Base
from operator_db.objects.utils import PydanticJSON
from operator_shared.settings.loader import load_operator_settings

if TYPE_CHECKING:
  from sqlalchemy.engine import Connection

  from operator_shared.settings.main import OperatorSettings

config = context.config
if not isinstance(config, AlembicCommandConfig):
  error_msg = (
    "Operator migrations require Advanced Alchemy configuration!"
  )
  raise TypeError(error_msg)
writer = rewriter.Rewriter()


def _render_item(
  type_: str,
  obj: object,
  *_args: Any,
  **_kwargs: Any,
) -> str | Literal[False]:
  if type_ != "type":
    return False
  match obj:
    case PydanticJSON():
      # we need this to avoid having to detect internal model_type, which is
      # useless for alembic - so we just use the internal type of JsonB
      return "sa.JsonB"
    case _:
      return False


@cache
def _get_op_settings() -> OperatorSettings:
  return load_operator_settings()


def _get_configure_kwargs() -> dict[str, Any]:
  return {
    "target_metadata": Base.metadata,
    "compare_type": config.compare_type,
    "version_table": config.version_table_name,
    "version_table_pk": config.version_table_pk,
    "user_module_prefix": config.user_module_prefix,
    "render_as_batch": config.render_as_batch,
    "process_revision_directives": writer,
    "render_item": _render_item,
  }


def run_migrations_offline() -> None:
  """Run migrations in 'offline' mode."""
  url = _get_op_settings().database.connection_string
  context.configure(
    url=url,
    literal_binds=True,
    dialect_opts={"paramstyle": "named"},
    **_get_configure_kwargs(),
  )

  with context.begin_transaction():
    context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
  """Run migrations synchronously on an existing connection."""
  context.configure(
    connection=connection,
    **_get_configure_kwargs(),
  )

  with context.begin_transaction():
    context.run_migrations()


async def run_async_migrations() -> None:
  """Run migrations through an async engine for Alembic CLI usage."""
  connectable = get_async_engine(_get_op_settings())

  try:
    async with connectable.connect() as connection:
      sqlite = connection.dialect.name == "sqlite"
      if sqlite:
        await connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        await connection.commit()
      try:
        await connection.run_sync(do_run_migrations)
        if sqlite:
          check = await connection.exec_driver_sql(
            "PRAGMA foreign_key_check"
          )
          if check.first():
            error_msg = (
              "SQLite foreign-key violations remain after migration!"
            )
            raise RuntimeError(error_msg)
      finally:
        if sqlite:
          if connection.in_transaction():
            await connection.rollback()
          await connection.exec_driver_sql("PRAGMA foreign_keys=ON")
          await connection.commit()
  finally:
    await connectable.dispose()


def run_migrations_online() -> None:
  """Run migrations in 'online' mode."""
  asyncio.run(run_async_migrations())


if context.is_offline_mode():
  run_migrations_offline()
else:
  run_migrations_online()
