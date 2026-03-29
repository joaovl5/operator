"""Helpers shared by reusable JSON credential stores."""

import asyncio
import json
import os
import secrets
import tempfile
import threading
from pathlib import Path
from typing import Final

from operator_shared.time import epoch_ms

STALE_LOCK_AGE_MS: Final[int] = 5 * 60 * 1000
LOCK_WRITE_GRACE_MS: Final[int] = 1_000
LOCK_RETRY_SLEEP_SECONDS: Final[float] = 0.05
FILE_MODE_PRIVATE: Final[int] = 0o600
_LOCK_PART_COUNT: Final[int] = 2
_ASYNC_LOCKS_BY_PATH: dict[str, asyncio.Lock] = {}
_ASYNC_LOCKS_BY_PATH_GUARD = threading.Lock()


def atomic_write_json(*, path: Path, payload: object) -> None:
    """Write JSON to disk using a temporary file and atomic replacement."""
    temp_path: Path | None = None
    try:
        file_descriptor, temp_name = tempfile.mkstemp(
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            text=True,
        )
        temp_path = Path(temp_name)
        os.fchmod(file_descriptor, FILE_MODE_PRIVATE)
        with os.fdopen(file_descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())

        _ = temp_path.replace(path)
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def build_lock_contents() -> str:
    """Build lock-file contents that capture acquisition time and token."""
    return f"{epoch_ms()} {secrets.token_hex(16)}"


def get_async_path_lock(*, path: Path) -> asyncio.Lock:
    """Return a shared async lock for one on-disk credential path."""
    path_key = str(path)
    with _ASYNC_LOCKS_BY_PATH_GUARD:
        lock = _ASYNC_LOCKS_BY_PATH.get(path_key)
        if lock is None:
            lock = asyncio.Lock()
            _ASYNC_LOCKS_BY_PATH[path_key] = lock
        return lock


def parse_lock_contents(contents: str) -> tuple[int | None, str | None]:
    """Parse lock-file contents into timestamp and token parts."""
    stripped = contents.strip()
    if not stripped:
        return None, None

    parts = stripped.split(" ", 1)
    if len(parts) != _LOCK_PART_COUNT:
        return None, None

    timestamp_text, token = parts
    if not token:
        return None, None

    try:
        timestamp = int(timestamp_text)
    except ValueError:
        return None, None

    return timestamp, token
