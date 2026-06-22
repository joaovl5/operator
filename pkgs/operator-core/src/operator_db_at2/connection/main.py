"""Database engine construction and migration readiness helpers."""

from typing import TYPE_CHECKING

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

if TYPE_CHECKING:
    from operator_shared.settings.main import OperatorSettings


def get_async_engine(cfg: OperatorSettings) -> AsyncEngine:
    """Create an async engine from config."""
    return create_async_engine(
        url=cfg.database.connection_string,
    )
