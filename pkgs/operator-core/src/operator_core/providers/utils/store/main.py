"""Reusable JSON-backed credential store APIs."""

import os
import time
from typing import TYPE_CHECKING, Self

from pydantic import BaseModel, TypeAdapter, ValidationError

from .errors import JsonCredentialStoreCorruptionError, JsonCredentialStoreTransactionError
from .types import LockSnapshot
from .utils import (
    FILE_MODE_PRIVATE,
    LOCK_RETRY_SLEEP_SECONDS,
    LOCK_WRITE_GRACE_MS,
    STALE_LOCK_AGE_MS,
    atomic_write_json,
    build_lock_contents,
)

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path


class JsonCredentialStore[CredentialT: BaseModel]:
    """Persist one pydantic credential model in a lock-coordinated JSON file."""

    def __init__(self, *, model_type: type[CredentialT], path: Path) -> None:
        """Initialize the store for one credential model type and path."""
        self._model_type: type[CredentialT] = model_type
        self.path: Path = path
        self.lock_path: Path = path.with_name(f"{path.name}.lock")

    def load(self) -> CredentialT | None:
        """Load stored credentials when present."""
        if not self.path.exists():
            return None

        try:
            raw_text = self.path.read_text(encoding="utf-8")
        except OSError as error:
            message = f"failed to read credentials from {self.path}"
            raise self._build_corruption_error(message=message) from error

        try:
            payload_object = TypeAdapter(object).validate_json(raw_text)
        except ValidationError as error:
            message = f"credentials at {self.path} are malformed"
            raise self._build_corruption_error(message=message) from error

        try:
            return self._model_type.model_validate(payload_object)
        except ValidationError as error:
            message = f"credentials at {self.path} are missing required fields"
            raise self._build_corruption_error(message=message) from error

    def save(self, credentials: CredentialT) -> CredentialT:
        """Persist credentials and return the saved value."""
        with JsonCredentialStoreTransaction(store=self) as transaction:
            transaction.save(credentials)
        return credentials

    def delete(self) -> None:
        """Delete any stored credentials."""
        with JsonCredentialStoreTransaction(store=self) as transaction:
            transaction.delete()

    def update(
        self,
        updater: Callable[[CredentialT | None], CredentialT | None],
    ) -> CredentialT | None:
        """Read, update, and persist credentials while holding the store lock."""
        with JsonCredentialStoreTransaction(store=self) as transaction:
            current = transaction.load()
            updated = updater(current)
            if updated is None:
                transaction.delete()
            else:
                transaction.save(updated)
            return updated

    def _build_corruption_error(self, *, message: str) -> JsonCredentialStoreCorruptionError:
        return JsonCredentialStoreCorruptionError(message)


class JsonCredentialStoreTransaction[CredentialT: BaseModel]:
    """Lock-held store transaction for compound credential updates."""

    def __init__(self, *, store: JsonCredentialStore[CredentialT]) -> None:
        """Initialize a lock-backed transaction for the given store."""
        self._store: JsonCredentialStore[CredentialT] = store
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

    def load(self) -> CredentialT | None:
        """Load credentials while the transaction lock is held."""
        self._ensure_lock_held()
        return self._store.load()

    def save(self, credentials: CredentialT) -> None:
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
            message = "JsonCredentialStoreTransaction lock is not held"
            raise JsonCredentialStoreTransactionError(message)

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
