"""Utilities for the OpenAI client package."""

import asyncio
import threading
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

_REFRESH_LOCKS_BY_STORE_PATH: dict[str, asyncio.Lock] = {}
_REFRESH_LOCKS_BY_STORE_PATH_GUARD = threading.Lock()


def get_refresh_lock(*, store_path: Path) -> asyncio.Lock:
    """Return the shared refresh lock for a credential store path."""
    store_key = str(store_path)
    with _REFRESH_LOCKS_BY_STORE_PATH_GUARD:
        lock = _REFRESH_LOCKS_BY_STORE_PATH.get(store_key)
        if lock is None:
            lock = asyncio.Lock()
            _REFRESH_LOCKS_BY_STORE_PATH[store_key] = lock
        return lock
