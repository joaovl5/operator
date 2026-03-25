"""Internal helpers for shared Operator settings loading."""

import tomllib
from pathlib import Path
from typing import TYPE_CHECKING

from .errors import OperatorSettingsLoadError

if TYPE_CHECKING:
    from .types import OperatorSettingsSource


def default_operator_settings_path() -> Path:
    """Return the canonical `operator.toml` path for the current workspace."""
    return Path("operator.toml")


def load_optional_toml(*, path: Path) -> OperatorSettingsSource:
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
