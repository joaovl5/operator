"""History service API."""

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from operator_db.objects.agent.entity import SessionAgentEnt
from operator_db.objects.history.entity import (
    HistoryEnt,
    HistoryEpochEnt,
    HistoryEpochMessageEnt,
    )
from operator_db.objects.history.schema import (
    HistoryEpochRequestSchema,
    HistoryEpochResponseSchema,
    HistoryMessageRequestSchema,
    HistoryMessageResponseSchema,
    HistoryResponseSchema,
    )
from operator_db.utils.services import BaseService, DbSession

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


class HistoryService(BaseService):
    """Service for ordered agent histories."""

    async def get_history(
        self,
        *,
        history_id: str,
        db_session: DbSession | None = None,
    ) -> HistoryResponseSchema | None:
        """Return a history by database ID."""
        async with self.session(db_session, transaction=False) as session:
            history_ent = await session.get(HistoryEnt, history_id)
            if history_ent is None:
                return None
            return self._history_response(history_ent)

    async def get_history_for_agent(
        self,
        *,
        session_id: str,
        agent_local_id: str,
        db_session: DbSession | None = None,
    ) -> HistoryResponseSchema | None:
        """Return the history for a session-local agent."""
        async with self.session(db_session, transaction=False) as session:
            result = await session.execute(
                select(HistoryEnt)
                .join(SessionAgentEnt, SessionAgentEnt.history_id == HistoryEnt.id)
                .where(
                    SessionAgentEnt.session_id == session_id,
                    SessionAgentEnt.local_id == agent_local_id,
                )
            )
            history_ent = result.scalar_one_or_none()
            if history_ent is None:
                return None
            return self._history_response(history_ent)

    async def create_next_epoch(
        self,
        *,
        history_id: str,
        request: HistoryEpochRequestSchema | None = None,
        db_session: DbSession | None = None,
    ) -> HistoryEpochResponseSchema:
        """Create the next epoch for a history."""
        async with self.session(db_session) as session:
            next_epoch_iteration = await self._next_epoch_iteration(
                session=session,
                history_id=history_id,
            )
            epoch_ent = HistoryEpochEnt(
                history_id=history_id,
                epoch_iteration=next_epoch_iteration,
                title=request.title if request is not None else None,
                description=request.description if request is not None else None,
                extra_detail=request.extra_detail if request is not None else None,
            )
            session.add(epoch_ent)
            await session.flush()
            await session.refresh(epoch_ent)
            return self._epoch_response(epoch_ent)

    async def append_message(
        self,
        *,
        history_id: str,
        request: HistoryMessageRequestSchema,
        compacted_message_ids: Sequence[str] = (),
        db_session: DbSession | None = None,
    ) -> HistoryMessageResponseSchema:
        """Append a message to the current history epoch."""
        async with self.session(db_session) as session:
            epoch_result = await session.execute(
                select(HistoryEpochEnt)
                .where(HistoryEpochEnt.history_id == history_id)
                .order_by(HistoryEpochEnt.epoch_iteration.desc())
                .limit(1)
            )
            epoch_ent = epoch_result.scalar_one_or_none()

            if epoch_ent is None:
                epoch_ent = HistoryEpochEnt(history_id=history_id, epoch_iteration=0)
                session.add(epoch_ent)
                await session.flush()
                await session.refresh(epoch_ent)

            message_index_result = await session.execute(
                select(func.max(HistoryEpochMessageEnt.message_index)).where(
                    HistoryEpochMessageEnt.epoch_id == epoch_ent.id,
                )
            )
            current_message_index = message_index_result.scalar()
            next_message_index = 0 if current_message_index is None else current_message_index + 1

            message_ent = HistoryEpochMessageEnt(
                epoch_id=epoch_ent.id,
                message_index=next_message_index,
                role=request.role,
                author_id=request.author_id,
                text_contents=request.text_contents,
                binary_contents=request.binary_contents,
                json_contents=request.json_contents,
                extra_metadata=request.extra_metadata,
            )
            session.add(message_ent)
            await session.flush()

            if compacted_message_ids:
                compacted_result = await session.execute(
                    select(HistoryEpochMessageEnt).where(
                        HistoryEpochMessageEnt.id.in_(compacted_message_ids),
                    )
                )
                for compacted_message in compacted_result.scalars().all():
                    compacted_message.compacted_by_id = message_ent.id

            await session.refresh(message_ent)
            return self._message_response(message_ent)

    async def list_messages(
        self,
        *,
        history_id: str,
        epoch_iteration: int | None = None,
        db_session: DbSession | None = None,
    ) -> list[HistoryMessageResponseSchema]:
        """List ordered messages for a history."""
        async with self.session(db_session, transaction=False) as session:
            statement = (
                select(HistoryEpochMessageEnt)
                .join(HistoryEpochEnt, HistoryEpochMessageEnt.epoch_id == HistoryEpochEnt.id)
                .where(HistoryEpochEnt.history_id == history_id)
                .order_by(
                    HistoryEpochEnt.epoch_iteration,
                    HistoryEpochMessageEnt.message_index,
                )
            )
            if epoch_iteration is not None:
                statement = statement.where(
                    HistoryEpochEnt.epoch_iteration == epoch_iteration,
                )

            result = await session.execute(statement)
            return [
                self._message_response(message_ent)
                for message_ent in result.scalars().all()
            ]

    @staticmethod
    def _history_response(history_ent: HistoryEnt) -> HistoryResponseSchema:
        return HistoryResponseSchema.model_validate(history_ent)

    @staticmethod
    def _epoch_response(epoch_ent: HistoryEpochEnt) -> HistoryEpochResponseSchema:
        return HistoryEpochResponseSchema.model_validate(epoch_ent)

    @staticmethod
    def _message_response(
        message_ent: HistoryEpochMessageEnt,
    ) -> HistoryMessageResponseSchema:
        return HistoryMessageResponseSchema.model_validate(message_ent)

    @staticmethod
    async def _next_epoch_iteration(
        *,
        session: AsyncSession,
        history_id: str,
    ) -> int:
        result = await session.execute(
            select(func.max(HistoryEpochEnt.epoch_iteration)).where(
                HistoryEpochEnt.history_id == history_id,
            )
        )
        current_epoch_iteration = result.scalar()
        if current_epoch_iteration is None:
            return 0
        return current_epoch_iteration + 1


__all__ = ["HistoryService"]
