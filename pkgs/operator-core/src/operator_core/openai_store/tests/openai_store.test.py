import json
import stat
from typing import TYPE_CHECKING

import pytest

from operator_core.openai_oauth import OpenAIOAuthCredentials
from operator_core.openai_store import OpenAIOAuthStore, OpenAIOAuthStoreCorruptionError

if TYPE_CHECKING:
    from pathlib import Path


UPDATED_ACCESS_TOKEN = "updated-access-token"  # noqa: S105
PRIVATE_FILE_MODE = 0o600


def make_credentials(*, access_token: str = "access-token") -> OpenAIOAuthCredentials:  # noqa: S107
    """Build a representative OAuth credential payload for store tests."""
    return OpenAIOAuthCredentials(
        access_token=access_token,
        refresh_token="refresh-token",  # noqa: S106
        id_token="id-token",  # noqa: S106
        expires_at_ms=123_456,
        account_id="acct_123",
        scope="openid profile email offline_access",
        token_type="Bearer",  # noqa: S106
    )


def test_store_constructor_derives_default_and_base_dir_paths(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Store construction derives the expected credential and lock paths."""
    monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg"))

    default_store = OpenAIOAuthStore()
    base_dir_store = OpenAIOAuthStore(base_dir=tmp_path / "base")

    assert default_store.path == tmp_path / "xdg" / "operator" / "auth" / "openai.json"
    assert default_store.lock_path == tmp_path / "xdg" / "operator" / "auth" / "openai.json.lock"
    assert base_dir_store.path == tmp_path / "base" / "auth" / "openai.json"
    assert base_dir_store.lock_path == tmp_path / "base" / "auth" / "openai.json.lock"


def test_store_constructor_accepts_explicit_paths(tmp_path: Path) -> None:
    """Explicit store paths are preserved and derive matching lock files."""
    path = tmp_path / "custom" / "openai.json"

    store = OpenAIOAuthStore(path=path)

    assert store.path == path
    assert store.lock_path == path.with_name("openai.json.lock")


def test_store_public_apis_save_load_update_and_delete(tmp_path: Path) -> None:
    """Store public APIs persist, update, and remove credentials."""
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    original = make_credentials()

    saved = store.save(original)
    loaded = store.load()
    updated = store.update(
        lambda current: (
            current.model_copy(update={"access_token": UPDATED_ACCESS_TOKEN})
            if current is not None
            else None
        )
    )
    store.delete()

    assert saved == original
    assert loaded == original
    assert updated is not None
    assert updated.access_token == UPDATED_ACCESS_TOKEN
    assert store.load() is None
    assert not store.path.exists()
    assert not store.lock_path.exists()


def test_store_save_writes_private_credentials_file(tmp_path: Path) -> None:
    """Saving credentials persists them with private file permissions."""
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")

    _ = store.save(make_credentials())

    assert stat.S_IMODE(store.path.stat().st_mode) == PRIVATE_FILE_MODE


@pytest.mark.parametrize(
    "contents",
    [
        pytest.param("{not-json", id="invalid-json"),
        pytest.param(json.dumps({"access_token": "missing-refresh-token"}), id="missing-fields"),
    ],
)
def test_store_public_apis_surface_corrupt_payloads(tmp_path: Path, contents: str) -> None:
    """Corrupt on-disk payloads raise the dedicated public store error."""
    path = tmp_path / "openai.json"
    _ = path.write_text(contents, encoding="utf-8")
    store = OpenAIOAuthStore(path=path)

    with pytest.raises(OpenAIOAuthStoreCorruptionError):
        _ = store.load()


def test_store_save_overwrites_corrupt_payloads(tmp_path: Path) -> None:
    """Saving new credentials replaces unreadable on-disk payloads."""
    path = tmp_path / "openai.json"
    _ = path.write_text("{bad-json", encoding="utf-8")
    store = OpenAIOAuthStore(path=path)
    credentials = make_credentials()

    saved = store.save(credentials)

    assert saved == credentials
    assert store.load() == credentials


def test_store_delete_removes_corrupt_payloads(tmp_path: Path) -> None:
    """Deleting credentials removes unreadable payloads without surfacing corruption."""
    path = tmp_path / "openai.json"
    _ = path.write_text("{bad-json", encoding="utf-8")
    store = OpenAIOAuthStore(path=path)

    store.delete()

    assert store.load() is None
    assert not path.exists()


def test_store_update_surfaces_existing_corruption(tmp_path: Path) -> None:
    """Updates fail fast when the existing persisted state is corrupt."""
    path = tmp_path / "openai.json"
    _ = path.write_text("{bad-json", encoding="utf-8")
    store = OpenAIOAuthStore(path=path)

    with pytest.raises(OpenAIOAuthStoreCorruptionError):
        _ = store.update(lambda _current: make_credentials())


def test_store_save_recovers_from_stale_lock_file(tmp_path: Path) -> None:
    """Saving credentials recovers from stale lock files through public effects."""
    store = OpenAIOAuthStore(path=tmp_path / "openai.json")
    store.lock_path.parent.mkdir(parents=True, exist_ok=True)
    _ = store.lock_path.write_text("0 stale-token", encoding="utf-8")
    credentials = make_credentials()

    saved = store.save(credentials)

    assert saved == credentials
    assert store.load() == credentials
    assert not store.lock_path.exists()
