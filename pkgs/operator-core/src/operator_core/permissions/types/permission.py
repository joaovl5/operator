from typing import TYPE_CHECKING

from operator_shared.forms import BaseForm

from .communication import Communication, CommunicationState
from .temporal import TemporalScopeType  # noqa: TC001

if TYPE_CHECKING:
    from anyio import Path


class FilesystemScope(BaseForm):
    """A filesystem scope for permission checks."""

    path: Path
    glob: str = "*"


class _BasePermission(BaseForm): ...


class Permission:
    """Namespace for agent permission types."""

    class Filesystem:
        """Agent permission types dealing with the filesystem."""

        class BaseFilesystemPermission(_BasePermission):
            """Permission scoped to a directory and optional glob."""

            scope: FilesystemScope

        class Read(BaseFilesystemPermission):
            """Local file reading within a scope."""

        class Edit(BaseFilesystemPermission):
            """Local file creation, modification, or deletion."""

            can_write: bool = True
            can_modify: bool = True
            can_delete: bool = True

    class Subagent(_BasePermission):
        """Subagent invocation and communication permissions."""

        can_invoke: bool = True
        can_communicate: CommunicationState = Communication.Allow()


type PermissionType = Permission.Filesystem.Read | Permission.Filesystem.Edit | Permission.Subagent
"""Union for kinds of permissions agents may have."""


class PermissionItem(BaseForm):
    """Permission instance with additional metadata."""

    permission: PermissionType
    temporal_scope: TemporalScopeType


class PermissionGroup(BaseForm):
    """A group of permission items for a certain scope."""

    perms: list[PermissionItem]
