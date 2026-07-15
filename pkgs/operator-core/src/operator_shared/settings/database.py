from operator_shared.settings.types import SettingsBase

DEFAULT_DATABASE_URL = (
  "sqlite+aiosqlite:///.operator/operator.sqlite3"
)


class DatabaseSettings(SettingsBase):
  """Database connection settings."""

  connection_string: str = DEFAULT_DATABASE_URL
