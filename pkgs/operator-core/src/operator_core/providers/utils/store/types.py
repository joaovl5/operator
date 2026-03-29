"""Types for the reusable JSON credential store."""

from attrs import define

from operator_shared.time import epoch_ms

from .utils import parse_lock_contents


@define(frozen=True, init=False)
class LockSnapshot:
    contents: str
    modified_time_ns: int
    acquired_at_ms: int | None
    token: str | None

    def __init__(
        self,
        *,
        contents: str,
        modified_time_ns: int,
        acquired_at_ms: int | None,
        token: str | None,
    ) -> None:
        """Store a parsed lockfile snapshot with its source metadata."""
        object.__setattr__(self, "contents", contents)
        object.__setattr__(self, "modified_time_ns", modified_time_ns)
        object.__setattr__(self, "acquired_at_ms", acquired_at_ms)
        object.__setattr__(self, "token", token)

    @classmethod
    def from_contents(cls, *, contents: str, modified_time_ns: int) -> LockSnapshot:
        """Build a snapshot by parsing the persisted lockfile contents."""
        acquired_at_ms, token = parse_lock_contents(contents)
        return cls(
            contents=contents,
            modified_time_ns=modified_time_ns,
            acquired_at_ms=acquired_at_ms,
            token=token,
        )

    @property
    def has_valid_shape(self) -> bool:
        """Return whether the snapshot contains both parsed lockfile fields."""
        return self.acquired_at_ms is not None and self.token is not None

    @property
    def age_ms(self) -> int:
        """Return the snapshot age in milliseconds using parsed or file metadata."""
        if self.acquired_at_ms is not None:
            return max(0, epoch_ms() - self.acquired_at_ms)

        modified_time_ms = self.modified_time_ns // 1_000_000
        return max(0, epoch_ms() - modified_time_ms)
