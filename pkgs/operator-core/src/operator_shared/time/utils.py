"""Shared time utilities."""

import time


def epoch_ms() -> int:
    """Return the current Unix epoch timestamp in milliseconds."""
    return int(time.time() * 1000)
