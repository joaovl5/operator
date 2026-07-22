from typing import TYPE_CHECKING

from advanced_alchemy.alembic.commands import AlembicCommands

from operator_db.connection.alchemy import build_alchemy_config

if TYPE_CHECKING:
  from operator_shared.settings.main import OperatorSettings


def ensure_db_ready(cfg: OperatorSettings) -> None:
  """Upgrade the configured database to the latest migration."""
  AlembicCommands(build_alchemy_config(cfg)).upgrade()
