"""History service API."""

from typing import TYPE_CHECKING

from operator_db.utils.services import BaseService, DbSession

if TYPE_CHECKING:
    from collections.abc import Sequence

    from operator_db.objects.history.schema import (
        HistoryEpochRequestSchema,
        HistoryEpochResponseSchema,
        HistoryMessageRequestSchema,
        HistoryMessageResponseSchema,
        HistoryResponseSchema,
    )


class HistoryService(BaseService):
    """Service for ordered agent histories."""

    async def get_history(
        self,
        *,
        history_id: str,
        db_session: DbSession | None = None,
    ) -> HistoryResponseSchema | None:
        """Return a history by database ID."""
        _ = (..., history_id, db_session)
        raise NotImplementedError

    async def get_history_for_agent(
        self,
        *,
        session_id: str,
        agent_local_id: str,
        db_session: DbSession | None = None,
    ) -> HistoryResponseSchema | None:
        """Return the history for a session-local agent."""
        _ = (..., session_id, agent_local_id, db_session)
        raise NotImplementedError

    async def create_next_epoch(
        self,
        *,
        history_id: str,
        request: HistoryEpochRequestSchema | None = None,
        db_session: DbSession | None = None,
    ) -> HistoryEpochResponseSchema:
        """Create the next epoch for a history."""
        _ = (..., history_id, request, db_session)
        raise NotImplementedError

    async def append_message(
        self,
        *,
        history_id: str,
        request: HistoryMessageRequestSchema,
        compacted_message_ids: Sequence[str] = (),
        db_session: DbSession | None = None,
    ) -> HistoryMessageResponseSchema:
        """Append a message to the current history epoch."""
        _ = (..., history_id, request, compacted_message_ids, db_session)
        raise NotImplementedError

    async def list_messages(
        self,
        *,
        history_id: str,
        epoch_iteration: int | None = None,
        db_session: DbSession | None = None,
    ) -> list[HistoryMessageResponseSchema]:
        """List ordered messages for a history."""
        _ = (..., history_id, epoch_iteration, db_session)
        raise NotImplementedError


__all__ = ["HistoryService"]
