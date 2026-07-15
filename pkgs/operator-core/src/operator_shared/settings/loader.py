import tomllib
from pathlib import Path
from typing import Any

from operator_shared.settings.errors import OperatorSettingsLoadError
from operator_shared.settings.main import OperatorSettings


def _load_optional_toml(*, path: Path) -> dict[str, Any]:
  """Load a TOML document when present, otherwise return an empty mapping."""
  if not path.is_file():
    return {}

  try:
    with path.open("rb") as file:
      document = tomllib.load(file)
  except OSError as error:
    message = f"failed to read operator settings from {path}"
    raise OperatorSettingsLoadError(message) from error
  except tomllib.TOMLDecodeError as error:
    message = f"failed to parse operator settings from {path}"
    raise OperatorSettingsLoadError(message) from error

  return document


def get_default_config_path() -> Path:
  """Return the canonical `config.toml` path for the current workspace."""
  return Path("config.toml")


def load_operator_settings(
  *, path: Path | None = None
) -> OperatorSettings:
  """Load `config.toml` when present and validate it as `OperatorSettings`."""
  path = path or get_default_config_path()
  document = _load_optional_toml(path=path)

  return OperatorSettings.model_validate(document)
