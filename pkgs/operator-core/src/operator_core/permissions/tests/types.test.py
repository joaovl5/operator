from pydantic import BaseModel

from operator_core.permissions import Permission, PermissionItem, PermissionSet, TemporalScope


def test_temporal_scope_session_is_accepted_as_a_safe_placeholder() -> None:
    """The unfinished session scope remains valid in permission payloads."""
    permission_item = PermissionItem(
        permission=Permission.Subagent(),
        temporal_scope=TemporalScope.Session(),
    )

    assert isinstance(permission_item.temporal_scope, TemporalScope.Session)


def test_permission_set_remains_available_as_a_placeholder_schema() -> None:
    """PermissionSet stays on the public surface as a placeholder schema."""
    assert issubclass(PermissionSet, BaseModel)
