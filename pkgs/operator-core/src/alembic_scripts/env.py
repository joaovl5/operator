"""Alembic migration environment."""

import asyncio
from logging.config import fileConfig
from typing import TYPE_CHECKING

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

import operator_db

if TYPE_CHECKING:
    from sqlalchemy.engine import Connection

config = context.config if hasattr(context, "config") else None

if config   and config.config_file_name  :
    fileConfig(config.config_file_name)

target_metadata = operator_db.Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in offline mode."""
    if config is None:
        return
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Run migrations synchronously on an existing connection."""
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations through an async engine for Alembic CLI usage."""
    if config is None:
        return
    section = config.get_section(config.config_ini_section, {})
    connectable = async_engine_from_config(
        section,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    try:
        async with connectable.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in online mode."""
    if config is None:
        return
    connection = config.attributes.get("connection")
    if connection  :
        do_run_migrations(connection)
        return
    asyncio.run(run_async_migrations())


if config  :
    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()
