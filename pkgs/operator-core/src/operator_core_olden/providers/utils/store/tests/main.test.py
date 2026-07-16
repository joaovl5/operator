import json
import stat
from typing import TYPE_CHECKING

import pytest
from pydantic import BaseModel

from operator_core_olden.providers.utils.store import (
  JsonCredentialStore,
  JsonCredentialStoreCorruptionError,
)

if TYPE_CHECKING:
  from pathlib import Path


UPDATED_ACCESS_TOKEN = "updated-access-token"  # noqa: S105
PRIVATE_FILE_MODE = 0o600


class CredentialModel(BaseModel):
  access_token: str
  refresh_token: str
  expires_at_ms: int
  scope: str
  token_type: str


def make_credentials(
  *, access_token: str = "access-token"
) -> CredentialModel:
  """Build representative credentials for the generic JSON store tests."""
  return CredentialModel(
    access_token=access_token,
    refresh_token="refresh-token",  # noqa: S106
    expires_at_ms=123_456,
    scope="openid profile email offline_access",
    token_type="Bearer",  # noqa: S106
  )


def test_store_constructor_accepts_explicit_paths(
  tmp_path: Path,
) -> None:
  """Explicit store paths are preserved and derive matching lock files."""
  path = tmp_path / "custom" / "credentials.json"

  store = JsonCredentialStore(model_type=CredentialModel, path=path)

  assert store.path == path
  assert store.lock_path == path.with_name("credentials.json.lock")


def test_store_public_apis_save_load_update_and_delete(
  tmp_path: Path,
) -> None:
  """Store public APIs persist, update, and remove credentials."""
  store = JsonCredentialStore(
    model_type=CredentialModel, path=tmp_path / "credentials.json"
  )
  original = make_credentials()

  saved = store.save(original)
  loaded = store.load()
  updated = store.update(
    lambda current: (
      current.model_copy(
        update={"access_token": UPDATED_ACCESS_TOKEN}
      )
      if current
      else None
    )
  )
  store.delete()

  assert saved == original
  assert loaded == original
  assert updated
  assert updated.access_token == UPDATED_ACCESS_TOKEN
  assert store.load() is None
  assert not store.path.exists()
  assert not store.lock_path.exists()


def test_store_save_writes_private_credentials_file(
  tmp_path: Path,
) -> None:
  """Saving credentials persists them with private file permissions."""
  store = JsonCredentialStore(
    model_type=CredentialModel, path=tmp_path / "credentials.json"
  )

  _ = store.save(make_credentials())

  assert stat.S_IMODE(store.path.stat().st_mode) == PRIVATE_FILE_MODE


@pytest.mark.parametrize(
  "contents",
  [
    pytest.param("{not-json", id="invalid-json"),
    pytest.param(
      json.dumps({"access_token": "missing-refresh-token"}),
      id="missing-fields",
    ),
  ],
)
def test_store_public_apis_surface_corrupt_payloads(
  tmp_path: Path, contents: str
) -> None:
  """Corrupt on-disk payloads raise the dedicated public store error."""
  path = tmp_path / "credentials.json"
  _ = path.write_text(contents, encoding="utf-8")
  store = JsonCredentialStore(model_type=CredentialModel, path=path)

  with pytest.raises(JsonCredentialStoreCorruptionError):
    _ = store.load()


def test_store_save_overwrites_corrupt_payloads(
  tmp_path: Path,
) -> None:
  """Saving new credentials replaces unreadable on-disk payloads."""
  path = tmp_path / "credentials.json"
  _ = path.write_text("{bad-json", encoding="utf-8")
  store = JsonCredentialStore(model_type=CredentialModel, path=path)
  credentials = make_credentials()

  saved = store.save(credentials)

  assert saved == credentials
  assert store.load() == credentials


def test_store_delete_removes_corrupt_payloads(
  tmp_path: Path,
) -> None:
  """Deleting credentials removes unreadable payloads without surfacing corruption."""
  path = tmp_path / "credentials.json"
  _ = path.write_text("{bad-json", encoding="utf-8")
  store = JsonCredentialStore(model_type=CredentialModel, path=path)

  store.delete()

  assert store.load() is None
  assert not path.exists()


def test_store_update_surfaces_existing_corruption(
  tmp_path: Path,
) -> None:
  """Updates fail fast when the existing persisted state is corrupt."""
  path = tmp_path / "credentials.json"
  _ = path.write_text("{bad-json", encoding="utf-8")
  store = JsonCredentialStore(model_type=CredentialModel, path=path)

  with pytest.raises(JsonCredentialStoreCorruptionError):
    _ = store.update(lambda _current: make_credentials())


def test_store_save_recovers_from_stale_lock_file(
  tmp_path: Path,
) -> None:
  """Saving credentials recovers from stale lock files through public effects."""
  store = JsonCredentialStore(
    model_type=CredentialModel, path=tmp_path / "credentials.json"
  )
  store.lock_path.parent.mkdir(parents=True, exist_ok=True)
  _ = store.lock_path.write_text("0 stale-token", encoding="utf-8")
  credentials = make_credentials()

  saved = store.save(credentials)

  assert saved == credentials
  assert store.load() == credentials
  assert not store.lock_path.exists()
