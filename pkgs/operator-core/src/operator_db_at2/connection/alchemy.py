from pathlib import Path
from typing import TYPE_CHECKING

from advanced_alchemy.config import AlembicAsyncConfig, SQLAlchemyAsyncConfig

from operator_db_at2.objects import (
    Base,
)

if TYPE_CHECKING:
    from operator_shared.settings.main import OperatorSettings

_ALEMBIC_DIR = Path(__file__).parent.parent / "alembic"


def build_alchemy_config(cfg: OperatorSettings) -> SQLAlchemyAsyncConfig:
    """Build Alchemy CLI config from settings."""
    return SQLAlchemyAsyncConfig(
        connection_string=cfg.database.connection_string,
        metadata=Base.metadata,
        alembic_config=AlembicAsyncConfig(
            script_location=str(_ALEMBIC_DIR.resolve()),
            toml_file="pyproject.toml",
        ),
    )
