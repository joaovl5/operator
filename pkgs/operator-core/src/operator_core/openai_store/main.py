"""Public OpenAI OAuth credential store APIs."""

import json
import os
import time
from typing import TYPE_CHECKING, Self, TypeVar

from pydantic import ValidationError

from operator_core.openai_oauth import OpenAIOAuthCredentials

from .errors import OpenAIOAuthStoreCorruptionError
from .types import LockSnapshot
from .utils import (
    FILE_MODE_PRIVATE,
    LOCK_RETRY_SLEEP_SECONDS,
    LOCK_WRITE_GRACE_MS,
    STALE_LOCK_AGE_MS,
    atomic_write_json,
    build_lock_contents,
    default_store_path,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

_UpdateResult = TypeVar("_UpdateResult", bound=OpenAIOAuthCredentials | None)


class OpenAIOAuthStore:
    """Store OpenAI OAuth credentials with lock-file coordination."""

    def __init__(
        self,
        *,
        path: Path | None = None,
        base_dir: Path | None = None,
    ) -> None:
        """Initialize the store from an explicit path or derived base directory."""
        resolved_path, lock_path = _resolve_store_paths(path=path, base_dir=base_dir)
        self.path: Path = resolved_path
        self.lock_path: Path = lock_path

    def load(self) -> OpenAIOAuthCredentials | None:
        """Load stored OpenAI OAuth credentials when present."""
        if not self.path.exists():
            return None

        try:
            raw_text = self.path.read_text(encoding="utf-8")
        except OSError as error:
            message = f"failed to read OpenAI OAuth credentials from {self.path}"
            raise OpenAIOAuthStoreCorruptionError(message) from error

        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as error:
            message = f"OpenAI OAuth credentials at {self.path} are malformed"
            raise OpenAIOAuthStoreCorruptionError(message) from error

        try:
            return OpenAIOAuthCredentials.model_validate(payload)
        except ValidationError as error:
            message = f"OpenAI OAuth credentials at {self.path} are missing required fields"
            raise OpenAIOAuthStoreCorruptionError(message) from error

    def save(self, credentials: OpenAIOAuthCredentials) -> OpenAIOAuthCredentials:
        """Persist OpenAI OAuth credentials and return the saved value."""
        with OpenAIOAuthStoreTransaction(store=self) as transaction:
            transaction.save(credentials)
        return credentials

    def delete(self) -> None:
        """Delete any stored OpenAI OAuth credentials."""
        with OpenAIOAuthStoreTransaction(store=self) as transaction:
            transaction.delete()

    def update(
        self,
        updater: Callable[[OpenAIOAuthCredentials | None], _UpdateResult],
    ) -> _UpdateResult:
        """Read, update, and persist credentials while holding the store lock."""
        with OpenAIOAuthStoreTransaction(store=self) as transaction:
            current = transaction.load()
            updated = updater(current)
            if updated is None:
                transaction.delete()
            else:
                transaction.save(updated)
            return updated


class OpenAIOAuthStoreTransaction:
    """Lock-held store transaction for compound credential updates."""

    def __init__(self, store: OpenAIOAuthStore) -> None:
        """Initialize a lock-backed transaction for the given store."""
        self._store: OpenAIOAuthStore = store
        self._lock_acquired: bool = False
        self._lock_contents: str | None = None

    def __enter__(self) -> Self:
        """Acquire the lock and return the active transaction."""
        self._acquire_lock()
        self._lock_acquired = True
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        """Release the lock when leaving the transaction scope."""
        del exc_type, exc, tb
        self._release_lock()

    def load(self) -> OpenAIOAuthCredentials | None:
        """Load credentials while the transaction lock is held."""
        self._ensure_lock_held()
        return self._store.load()

    def save(self, credentials: OpenAIOAuthCredentials) -> None:
        """Persist credentials while the transaction lock is held."""
        self._ensure_lock_held()
        self._store.path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(path=self._store.path, payload=credentials.model_dump(mode="json"))

    def delete(self) -> None:
        """Delete credentials while the transaction lock is held."""
        self._ensure_lock_held()
        try:
            self._store.path.unlink()
        except FileNotFoundError:
            return

    def _ensure_lock_held(self) -> None:
        if not self._lock_acquired:
            message = "OpenAIOAuthStoreTransaction lock is not held"
            raise RuntimeError(message)

    def _acquire_lock(self) -> None:
        self._store.lock_path.parent.mkdir(parents=True, exist_ok=True)

        while True:
            lock_contents = build_lock_contents()
            try:
                file_descriptor = os.open(
                    self._store.lock_path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    FILE_MODE_PRIVATE,
                )
            except FileExistsError:
                if self._clear_stale_lock_if_needed():
                    continue
                time.sleep(LOCK_RETRY_SLEEP_SECONDS)
                continue

            try:
                _ = os.write(file_descriptor, lock_contents.encode("utf-8"))
                os.fchmod(file_descriptor, FILE_MODE_PRIVATE)
            finally:
                os.close(file_descriptor)

            self._lock_contents = lock_contents
            return

    def _clear_stale_lock_if_needed(self) -> bool:
        lock_snapshot = self._read_lock_snapshot()
        if lock_snapshot is None:
            return True

        if not lock_snapshot.has_valid_shape:
            if lock_snapshot.age_ms < LOCK_WRITE_GRACE_MS:
                return False
            return self._remove_lock_file_if_matches(lock_snapshot.contents)

        if lock_snapshot.age_ms >= STALE_LOCK_AGE_MS:
            return self._remove_lock_file_if_matches(lock_snapshot.contents)

        return False

    def _read_lock_snapshot(self) -> LockSnapshot | None:
        try:
            stats = self._store.lock_path.stat()
            contents = self._store.lock_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError:
            try:
                stats = self._store.lock_path.stat()
            except FileNotFoundError:
                return None
            contents = ""

        return LockSnapshot.from_contents(contents=contents, modified_time_ns=stats.st_mtime_ns)

    def _remove_lock_file_if_matches(self, expected_contents: str) -> bool:
        current_contents = self._read_lock_contents()
        if current_contents is None:
            return True
        if current_contents != expected_contents:
            return False

        try:
            self._store.lock_path.unlink()
        except FileNotFoundError:
            return True
        except OSError:
            return False
        return True

    def _read_lock_contents(self) -> str | None:
        try:
            return self._store.lock_path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError:
            return ""

    def _release_lock(self) -> None:
        if not self._lock_acquired:
            return

        self._lock_acquired = False
        if self._lock_contents is None:
            return

        _ = self._remove_lock_file_if_matches(self._lock_contents)
        self._lock_contents = None


def _resolve_store_paths(*, path: Path | None, base_dir: Path | None) -> tuple[Path, Path]:
    if path is not None and base_dir is not None:
        message = "path and base_dir are mutually exclusive"
        raise ValueError(message)

    if path is not None:
        resolved_path = path
    elif base_dir is not None:
        resolved_path = base_dir / "auth" / "openai.json"
    else:
        resolved_path = default_store_path()

    return resolved_path, resolved_path.with_name(f"{resolved_path.name}.lock")
