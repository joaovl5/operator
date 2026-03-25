from typing import TYPE_CHECKING

from operator_shared.time.utils import epoch_ms

if TYPE_CHECKING:
    import pytest


EXPECTED_EPOCH_MS = 123_456


def test_epoch_ms_returns_unix_timestamp_in_milliseconds(monkeypatch: pytest.MonkeyPatch) -> None:
    """epoch_ms returns whole Unix milliseconds."""
    monkeypatch.setattr("operator_shared.time.utils.time.time", lambda: 123.456)

    assert epoch_ms() == EXPECTED_EPOCH_MS


def test_epoch_ms_truncates_fractional_milliseconds(monkeypatch: pytest.MonkeyPatch) -> None:
    """epoch_ms truncates sub-millisecond fractions."""
    monkeypatch.setattr("operator_shared.time.utils.time.time", lambda: 123.4567)

    assert epoch_ms() == EXPECTED_EPOCH_MS
