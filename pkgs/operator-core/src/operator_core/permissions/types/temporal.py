from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from datetime import datetime


class _BaseTemporalScope(BaseModel): ...


class TemporalScope:
    """Namespace for temporal scope types."""

    class All(_BaseTemporalScope):
        """Scope for all of time."""

    class Interval(_BaseTemporalScope):
        """An interval of time."""

        starts_at: datetime | None = Field(
            None,
            description="If set, scope is validated from this starting point.",
        )
        ends_at: datetime | None = Field(
            None,
            description="If set, scope is validated up to this starting point.",
        )

    class Session(_BaseTemporalScope):
        """A placeholder scope dealing with session lifecycle."""


type TemporalScopeType = TemporalScope.All | TemporalScope.Interval | TemporalScope.Session
"""Union for kinds of temporal scopes for time or step-bound objects."""
