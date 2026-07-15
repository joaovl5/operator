"""OpenAI OAuth credential storage."""

import os
from pathlib import Path
from typing import override

from operator_core_olden.providers.openai.errors import (
  OpenAIOAuthStoreCorruptionError,
)
from operator_core_olden.providers.utils.store import (
  JsonCredentialStore,
)

from .types import OpenAIOAuthCredentials


def default_openai_oauth_credentials_path() -> Path:
  """Return the default on-disk location for OpenAI OAuth credentials."""
  xdg_data_home = os.environ.get("XDG_DATA_HOME")
  base_dir = (
    Path(xdg_data_home)
    if xdg_data_home
    else Path.home() / ".local" / "share"
  )
  return base_dir / "operator" / "auth" / "openai.json"


class OpenAIOAuthStore(JsonCredentialStore[OpenAIOAuthCredentials]):
  """Store OpenAI OAuth credentials using the reusable JSON store."""

  def __init__(
    self,
    *,
    path: Path | None = None,
    base_dir: Path | None = None,
  ) -> None:
    """Initialize the OpenAI OAuth store from an explicit or derived path."""
    super().__init__(
      model_type=OpenAIOAuthCredentials,
      path=_resolve_store_path(path=path, base_dir=base_dir),
    )

  @override
  def _build_corruption_error(
    self, *, message: str
  ) -> OpenAIOAuthStoreCorruptionError:
    return OpenAIOAuthStoreCorruptionError(message)


def _resolve_store_path(
  *, path: Path | None, base_dir: Path | None
) -> Path:
  if path and base_dir:
    message = "path and base_dir are mutually exclusive"
    raise ValueError(message)

  if path:
    return path
  if base_dir:
    return base_dir / "auth" / "openai.json"
  return default_openai_oauth_credentials_path()


__all__ = [
  "OpenAIOAuthStore",
  "default_openai_oauth_credentials_path",
]
