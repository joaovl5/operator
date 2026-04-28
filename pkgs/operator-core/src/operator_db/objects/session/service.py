"""Session service API."""

from operator_db.objects.session.entity import SessionEnt
from operator_db.objects.session.schema import SessionRequestSchema, SessionResponseSchema
from operator_db.utils.services import BaseService, DbSession


class SessionService(BaseService):
    """Service for persisted collaboration sessions."""

    async def create_session(
        self,
        *,
        request: SessionRequestSchema,
        db_session: DbSession | None = None,
    ) -> SessionResponseSchema:
        """Create a collaboration session."""
        async with self.session(db_session) as session:
            session_ent = SessionEnt(
                title=request.title,
                description=request.description,
                extra_detail=request.extra_detail,
            )
            session.add(session_ent)
            await session.flush()
            await session.refresh(session_ent)
            return SessionResponseSchema.model_validate(session_ent)

    async def get_session(
        self,
        *,
        session_id: str,
        db_session: DbSession | None = None,
    ) -> SessionResponseSchema | None:
        """Return a session by database ID."""
        async with self.session(db_session, transaction=False) as session:
            session_ent = await session.get(SessionEnt, session_id)
            if session_ent is None:
                return None
            return SessionResponseSchema.model_validate(session_ent)

    async def update_session(
        self,
        *,
        session_id: str,
        request: SessionRequestSchema,
        db_session: DbSession | None = None,
    ) -> SessionResponseSchema:
        """Update session metadata fields."""
        async with self.session(db_session) as session:
            session_ent = await session.get(SessionEnt, session_id)
            if session_ent is None:
                message = f"session not found: {session_id}"
                raise LookupError(message)

            session_ent.title = request.title
            session_ent.description = request.description
            session_ent.extra_detail = request.extra_detail

            await session.flush()
            await session.refresh(session_ent)
            return SessionResponseSchema.model_validate(session_ent)


__all__ = ["SessionService"]
