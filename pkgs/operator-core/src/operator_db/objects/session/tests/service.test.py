import pytest

from operator_db.objects.session import SessionRequestSchema, SessionService
from operator_db.utils.db.testing import tmp_sqlite_db


async def test_session_service_persists_and_updates_sessions() -> None:
    """Session service creates, fetches, and updates persisted sessions."""
    async with tmp_sqlite_db() as db:
        service = SessionService()

        created = await service.create_session(
            request=SessionRequestSchema(
                title="Initial title",
                description="Initial description",
            ),
            db_session=db.sessionmaker,
        )

        fetched = await service.get_session(
            session_id=created.id,
            db_session=db.sessionmaker,
        )

        assert fetched == created

        updated = await service.update_session(
            session_id=created.id,
            request=SessionRequestSchema(
                title="Updated title",
                description="Updated description",
                extra_detail="Updated detail",
            ),
            db_session=db.sessionmaker,
        )

        assert updated.id == created.id
        assert updated.title == "Updated title"
        assert updated.description == "Updated description"
        assert updated.extra_detail == "Updated detail"

        refetched = await service.get_session(
            session_id=created.id,
            db_session=db.sessionmaker,
        )

        assert refetched == updated



async def test_session_service_reuses_caller_managed_transaction() -> None:
    """Session service composes with an existing transactional AsyncSession."""
    async with tmp_sqlite_db() as db:
        service = SessionService()

        async with db.sessionmaker() as session, session.begin():
                created = await service.create_session(
                    request=SessionRequestSchema(title="Shared title"),
                    db_session=session,
                )

                updated = await service.update_session(
                    session_id=created.id,
                    request=SessionRequestSchema(
                        title="Updated shared title",
                        description="Shared description",
                    ),
                    db_session=session,
                )

                fetched = await service.get_session(
                    session_id=created.id,
                    db_session=session,
                )

        assert updated.id == created.id
        assert fetched == updated

async def test_session_service_requires_bound_session_source() -> None:
    """Session service rejects calls without a bound session or sessionmaker."""
    service = SessionService()

    with pytest.raises(RuntimeError, match="db_session"):
        _ = await service.create_session(request=SessionRequestSchema())
