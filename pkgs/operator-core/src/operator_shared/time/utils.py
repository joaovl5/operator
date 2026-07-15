"""Shared time utilities."""

import time
from datetime import UTC, datetime


def epoch_ms() -> int:
  """Return the current Unix epoch timestamp in milliseconds."""
  return int(time.time() * 1000)


def mk_time() -> datetime:
  """Create `datetime` from current time on UTC."""
  return datetime.now(tz=UTC)
