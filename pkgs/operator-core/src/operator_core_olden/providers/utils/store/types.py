"""Types for the reusable JSON credential store."""

from attrs import define

from operator_shared.time import epoch_ms

from .utils import parse_lock_contents


@define(frozen=True)
class LockSnapshot:
    """Parsed lockfile snapshot w/ metadata."""

    contents: str
    modified_time_ns: int
    acquired_at_ms: int | None
    token: str | None

    @classmethod
    def from_contents(cls, *, contents: str, modified_time_ns: int) -> LockSnapshot:
        """Parse a snapshot from lockfile contents."""
        acquired_at_ms, token = parse_lock_contents(contents)
        return cls(
            contents=contents,
            modified_time_ns=modified_time_ns,
            acquired_at_ms=acquired_at_ms,
            token=token,
        )

    @property
    def has_valid_shape(self) -> bool:
        """Return whether the snapshot is valid."""
        return self.acquired_at_ms and self.token

    @property
    def age_ms(self) -> int:
        """Return snapshot age in miliseconds."""
        if self.acquired_at_ms:
            return max(0, epoch_ms() - self.acquired_at_ms)

        modified_time_ms = self.modified_time_ns // 1_000_000
        return max(0, epoch_ms() - modified_time_ms)
