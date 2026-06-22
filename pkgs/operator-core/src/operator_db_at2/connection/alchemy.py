from typing import TYPE_CHECKING

from advanced_alchemy.config import SQLAlchemyAsyncConfig

if TYPE_CHECKING:
    from operator_shared.settings.main import OperatorSettings


def build_alchemy_config(cfg: OperatorSettings) -> SQLAlchemyAsyncConfig:
    """Build Alchemy CLI config from settings."""
    return SQLAlchemyAsyncConfig(
        connection_string=cfg.database.connection_string,
    )
