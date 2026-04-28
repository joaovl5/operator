"""Session service API."""

from typing import TYPE_CHECKING

from operator_db.utils.services import BaseService

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from operator_db.objects.session.schema import SessionRequestSchema, SessionResponseSchema


class SessionService(BaseService):
    """Service for persisted collaboration sessions."""

    async def create_session(
        self,
        *,
        request: SessionRequestSchema,
        db_session: AsyncSession | None = None,
    ) -> SessionResponseSchema:
        """Create a collaboration session."""
        _ = (..., request, db_session)
        raise NotImplementedError

    async def get_session(
        self,
        *,
        session_id: str,
        db_session: AsyncSession | None = None,
    ) -> SessionResponseSchema | None:
        """Return a session by database ID."""
        _ = (..., session_id, db_session)
        raise NotImplementedError

    async def update_session(
        self,
        *,
        session_id: str,
        request: SessionRequestSchema,
        db_session: AsyncSession | None = None,
    ) -> SessionResponseSchema:
        """Update session metadata fields."""
        _ = (..., session_id, request, db_session)
        raise NotImplementedError


__all__ = ["SessionService"]
