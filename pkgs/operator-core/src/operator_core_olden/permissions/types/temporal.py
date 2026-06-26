from datetime import datetime

from pydantic import Field

from operator_core_olden.permissions.types.permission import PermissionItem, PermissionType
from operator_shared.forms import BaseForm


class _BaseTemporalScope(BaseForm):
    def wrap_permission(self, perm: PermissionType) -> PermissionItem:
        """Wrap temporal scope in a permission, yielding a `PermissionItem`."""
        return PermissionItem(
            permission=perm,
            temporal_scope=self,
        )


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
