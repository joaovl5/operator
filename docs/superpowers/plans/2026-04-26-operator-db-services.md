# Operator DB Services Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the public `operator_db` service APIs behind integration-tested async SQLite behavior.

**Architecture:** Services remain thin, domain-shaped classes over SQLAlchemy `AsyncSession`. Public tests use only service methods and Pydantic schemas, backed by a reusable in-memory SQLite async context manager. Implementation keeps ordering/index allocation and local-ID resolution inside service methods instead of exposing raw ORM internals.

**Tech Stack:** Python 3.14, SQLAlchemy 2.x async ORM, `sqlite+aiosqlite`, pytest/pytest-asyncio, Pydantic v2.

---

## File Structure

- Modify: `pyproject.toml` and `uv.lock`
  - Add `aiosqlite` so `sqlite+aiosqlite://` works in tests and development.
- Create: `pkgs/operator-core/src/operator_db/utils/db/testing.py`
  - Async context manager for in-memory SQLite integration tests.
  - Yields an async engine and `async_sessionmaker[AsyncSession]`.
  - Creates `Base.metadata` on entry and disposes the engine on exit.
- Create: `pkgs/operator-core/src/operator_db/utils/db/tests/testing.test.py`
  - Public helper integration test proving the context manager yields usable DB/sessionmaker and disposes cleanly.
- Modify: `pkgs/operator-core/src/operator_db/objects/session/service.py`
  - Implement `SessionService` public methods.
- Create: `pkgs/operator-core/src/operator_db/objects/session/tests/service.test.py`
  - Minimal public service outcome tests.
- Modify: `pkgs/operator-core/src/operator_db/objects/agent/service.py`
  - Implement `SessionAgentService` public methods.
- Create: `pkgs/operator-core/src/operator_db/objects/agent/tests/service.test.py`
  - Minimal public service outcome tests.
- Modify: `pkgs/operator-core/src/operator_db/objects/history/service.py`
  - Implement `HistoryService` public methods.
- Create: `pkgs/operator-core/src/operator_db/objects/history/tests/service.test.py`
  - Minimal public service outcome tests.
- Modify: `pkgs/operator-core/src/operator_db/objects/mail/service.py`
  - Implement `MailService` public methods.
- Create: `pkgs/operator-core/src/operator_db/objects/mail/tests/service.test.py`
  - Minimal public service outcome tests.

## Global Test Rules

- Tests must exercise public service APIs only.
- Do not assert private helper calls, private query shapes, or internal delegation.
- Keep cases simple and non-duplicative.
- Use real SQLAlchemy async SQLite; no mocks for persistence.
- Prefer one happy-path/invariant test per service area instead of broad CRUD matrices.

## Task 1: Async SQLite Test Utility

**Files:**

- Create: `pkgs/operator-core/src/operator_db/utils/db/testing.py`
- Create: `pkgs/operator-core/src/operator_db/utils/db/tests/testing.test.py`
- Modify: `pyproject.toml`
- Modify: `uv.lock`

- [ ] **Step 1: Add async SQLite driver dependency**

Add `aiosqlite>=0.21.0` to the root project dependencies in `pyproject.toml`, then update `uv.lock` with `uv lock`.

- [ ] **Step 2: Write failing integration test for DB context helper**

Create `testing.test.py` with one async test:

```python
from sqlalchemy import inspect, select

from operator_db import Base
from operator_db.utils.db.testing import tmp_sqlite_db


async def test_tmp_sqlite_db_yields_usable_sessionmaker() -> None:
    async with tmp_sqlite_db() as db:
        async with db.sessionmaker() as session:
            result = await session.execute(select(1))
            assert result.scalar_one() == 1

        async with db.engine.connect() as conn:
            table_names = await conn.run_sync(
                lambda sync_conn: set(inspect(sync_conn).get_table_names()),
            )

        assert set(Base.metadata.tables) <= table_names
```

This checks only the public helper contract: usable engine/sessionmaker plus created operator_db tables.

- [ ] **Step 3: Run the focused test and verify failure**

Run:

```bash
uv run pytest pkgs/operator-core/src/operator_db/utils/db/tests/testing.test.py -q
```

Expected: fails because `operator_db.utils.db.testing` does not exist.

- [ ] **Step 4: Implement minimal helper**

Use an attrs model for the yielded object:

```python
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from attrs import define
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine

from operator_db import Base


@define(frozen=True, kw_only=True)
class TmpSqliteDb:
    """Temporary async SQLite DB handles."""

    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]


@asynccontextmanager
async def tmp_sqlite_db() -> AsyncIterator[TmpSqliteDb]:
    """Yield an in-memory async SQLite database with operator_db tables."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield TmpSqliteDb(engine=engine, sessionmaker=sessionmaker)
    finally:
        await engine.dispose()
```

If in-memory connection isolation causes table visibility issues, use `StaticPool` and `connect_args={"check_same_thread": False}` with the same URL.

- [ ] **Step 5: Run focused test and commit**

Run:

```bash
uv run pytest pkgs/operator-core/src/operator_db/utils/db/tests/testing.test.py -q
uv run ruff check pkgs/operator-core/src/operator_db/utils/db/testing.py pkgs/operator-core/src/operator_db/utils/db/tests/testing.test.py
uv run basedpyright pkgs/operator-core/src/operator_db/utils/db/testing.py pkgs/operator-core/src/operator_db/utils/db/tests/testing.test.py
```

Commit:

```bash
git add pyproject.toml uv.lock pkgs/operator-core/src/operator_db/utils/db/testing.py pkgs/operator-core/src/operator_db/utils/db/tests/testing.test.py
git commit -m "test: add operator db sqlite integration helper"
```

## Task 2: Session and Agent Services

**Files:**

- Modify: `pkgs/operator-core/src/operator_db/objects/session/service.py`
- Modify: `pkgs/operator-core/src/operator_db/objects/agent/service.py`
- Create: `pkgs/operator-core/src/operator_db/objects/session/tests/service.test.py`
- Create: `pkgs/operator-core/src/operator_db/objects/agent/tests/service.test.py`
- Modify: `pkgs/operator-core/src/operator_db/utils/services/base.py`
- Modify: `pkgs/operator-core/src/operator_db/utils/services/__init__.py`
- Modify signature imports only: `pkgs/operator-core/src/operator_db/objects/history/service.py`
- Modify signature imports only: `pkgs/operator-core/src/operator_db/objects/mail/service.py`

- [ ] **Step 1: Write failing SessionService public tests**

Test only outcomes:

```python
async def test_session_service_creates_gets_and_updates_session() -> None:
    async with tmp_sqlite_db() as db:
        service = SessionService()
        created = await service.create_session(
            request=SessionRequestSchema(title="Initial"),
            db_session=db.sessionmaker,
        )
        assert created.id
        assert created.title == "Initial"

        loaded = await service.get_session(session_id=created.id, db_session=db.sessionmaker)
        assert loaded == created

        updated = await service.update_session(
            session_id=created.id,
            request=SessionRequestSchema(title="Updated"),
            db_session=db.sessionmaker,
        )
        assert updated.title == "Updated"
```

Use the final fixture shape from Task 1. The final shared service boundary is: every public service method keeps the `db_session` keyword, but its type should be updated consistently to accept `AsyncSession | async_sessionmaker[AsyncSession] | None` via a shared alias exported from `operator_db.utils.services`.

- [ ] **Step 2: Write failing SessionAgentService public tests**

Test one clear flow:

```python
async def test_agent_service_creates_history_and_resolves_local_ids() -> None:
    async with tmp_sqlite_db() as db:
        sessions = SessionService()
        agents = SessionAgentService()
        session = await sessions.create_session(request=SessionRequestSchema(), db_session=db.sessionmaker)

        created = await agents.create_agent(
            request=AgentRequestSchema(session_id=session.id, local_id="worker"),
            db_session=db.sessionmaker,
        )
        assert created.history_id

        by_local = await agents.get_agent_by_local_id(
            session_id=session.id,
            local_id="worker",
            db_session=db.sessionmaker,
        )
        assert by_local == created

        listed = await agents.list_agents(session_id=session.id, db_session=db.sessionmaker)
        assert [agent.local_id for agent in listed] == ["worker"]
```

- [ ] **Step 3: Run focused tests and verify failure**

Run:

```bash
uv run pytest \
  pkgs/operator-core/src/operator_db/objects/session/tests/service.test.py \
  pkgs/operator-core/src/operator_db/objects/agent/tests/service.test.py \
  -q
```

Expected: fails with `NotImplementedError` or signature mismatch.

- [ ] **Step 4: Implement minimal service behavior**

Implementation guidance:

- Define a concrete shared session-boundary alias in `operator_db.utils.services.base`, e.g. `type DbSession = AsyncSession | async_sessionmaker[AsyncSession]`. Re-export it from `operator_db.utils.services`.
- Update all service method signatures from `db_session: AsyncSession | None` to `db_session: DbSession | None`.
- Convert `BaseService.session(...)` into an `@asynccontextmanager` that accepts either an existing `AsyncSession` or an `async_sessionmaker[AsyncSession]`.
- Do not leave unbound `AsyncSession()` as any real code path. If `db_session is None`, raise a clear `RuntimeError` until application-level sessionmaker wiring exists.
- Apply this `DbSession` signature update to all service classes in the same task, including `HistoryService` and `MailService`, before writing later tests that pass `db.sessionmaker`.
- `SessionService.create_session`: create `SessionEnt`, add, flush/refresh, return `SessionResponseSchema.model_validate(ent)`.
- `get_session`: use `AsyncSession.get(SessionEnt, session_id)`.
- `update_session`: mutate metadata fields, flush/refresh.
- `SessionAgentService.create_agent`: create `HistoryEnt` and `SessionAgentEnt` together; callers do not provide `history_id`.
- `get_agent_by_local_id`: select by `(session_id, local_id)`.
- `list_agents`: select by `session_id`, stable order by `local_id`.

- [ ] **Step 5: Run focused tests/lint/type and commit**

Run:

```bash
uv run pytest \
  pkgs/operator-core/src/operator_db/objects/session/tests/service.test.py \
  pkgs/operator-core/src/operator_db/objects/agent/tests/service.test.py \
  -q
uv run ruff check \
  pkgs/operator-core/src/operator_db/objects/session \
  pkgs/operator-core/src/operator_db/objects/agent \
  pkgs/operator-core/src/operator_db/utils/services \
  pkgs/operator-core/src/operator_db/objects/history/service.py \
  pkgs/operator-core/src/operator_db/objects/mail/service.py
uv run basedpyright \
  pkgs/operator-core/src/operator_db/objects/session \
  pkgs/operator-core/src/operator_db/objects/agent \
  pkgs/operator-core/src/operator_db/utils/services \
  pkgs/operator-core/src/operator_db/objects/history/service.py \
  pkgs/operator-core/src/operator_db/objects/mail/service.py
```

Commit:

```bash
git add \
  pkgs/operator-core/src/operator_db/objects/session \
  pkgs/operator-core/src/operator_db/objects/agent \
  pkgs/operator-core/src/operator_db/objects/history/service.py \
  pkgs/operator-core/src/operator_db/objects/mail/service.py \
  pkgs/operator-core/src/operator_db/utils/services
git commit -m "feat: implement session and agent services"
```

## Task 3: History Service

**Files:**

- Modify: `pkgs/operator-core/src/operator_db/objects/history/service.py`
- Create: `pkgs/operator-core/src/operator_db/objects/history/tests/service.test.py`

- [ ] **Step 1: Write failing public history service tests**

Use existing `SessionService` and `SessionAgentService` to create a session/agent/history.

Test one flow:

```python
async def test_history_service_appends_ordered_messages_and_compaction_links() -> None:
    async with tmp_sqlite_db() as db:
        session = await SessionService().create_session(request=SessionRequestSchema(), db_session=db.sessionmaker)
        agent = await SessionAgentService().create_agent(
            request=AgentRequestSchema(session_id=session.id, local_id="worker"),
            db_session=db.sessionmaker,
        )

        history = HistoryService()
        first = await history.append_message(
            history_id=agent.history_id,
            request=HistoryMessageRequestSchema(role=HistoryMessageRole.USER, text_contents="one"),
            db_session=db.sessionmaker,
        )
        second = await history.append_message(
            history_id=agent.history_id,
            request=HistoryMessageRequestSchema(role=HistoryMessageRole.AGENT_SELF, text_contents="two"),
            compacted_message_ids=[first.id],
            db_session=db.sessionmaker,
        )

        messages = await history.list_messages(history_id=agent.history_id, db_session=db.sessionmaker)
        assert [message.message_index for message in messages] == [0, 1]
        assert [message.id for message in messages] == [first.id, second.id]
```

Add one small assertion by querying public service response only if response includes `compacted_by_id`; otherwise keep compaction verification for implementation-level later.

- [ ] **Step 2: Run focused test and verify failure**

Run:

```bash
uv run pytest pkgs/operator-core/src/operator_db/objects/history/tests/service.test.py -q
```

Expected: fails with `NotImplementedError`.

- [ ] **Step 3: Implement minimal history behavior**

Implementation guidance:

- `get_history`: `session.get(HistoryEnt, history_id)`.
- `get_history_for_agent`: resolve `SessionAgentEnt` by `(session_id, local_id)` then return its history.
- `create_next_epoch`: find max `epoch_iteration` for history and insert next; first epoch is `0`.
- `append_message`: ensure a current epoch exists, allocate next `message_index` in that epoch, insert message, then update each compacted old message's `compacted_by_id` to the new message ID.
- `list_messages`: if `epoch_iteration` is given, list that epoch; otherwise list all history messages ordered by epoch and message index.

- [ ] **Step 4: Run focused tests/lint/type and commit**

Run:

```bash
uv run pytest pkgs/operator-core/src/operator_db/objects/history/tests/service.test.py -q
uv run ruff check pkgs/operator-core/src/operator_db/objects/history
uv run basedpyright pkgs/operator-core/src/operator_db/objects/history
```

Commit:

```bash
git add pkgs/operator-core/src/operator_db/objects/history
git commit -m "feat: implement history service"
```

## Task 4: Mail Service

**Files:**

- Modify: `pkgs/operator-core/src/operator_db/objects/mail/service.py`
- Create: `pkgs/operator-core/src/operator_db/objects/mail/tests/service.test.py`

- [ ] **Step 1: Write failing public mail service tests**

Use existing services to create one session with sender and receivers.

Test one flow:

```python
async def test_mail_service_queues_claims_and_renders_mail() -> None:
    async with tmp_sqlite_db() as db:
        session = await SessionService().create_session(request=SessionRequestSchema(), db_session=db.sessionmaker)
        agents = SessionAgentService()
        await agents.create_agent(request=AgentRequestSchema(session_id=session.id, local_id="sender"), db_session=db.sessionmaker)
        await agents.create_agent(request=AgentRequestSchema(session_id=session.id, local_id="receiver"), db_session=db.sessionmaker)

        service = MailService()
        queued = await service.queue_message(
            request=MailRequestSchema(
                session_id=session.id,
                sender_local_ids=["sender"],
                receiver_local_ids=["receiver"],
                body="hello",
            ),
            db_session=db.sessionmaker,
        )
        assert queued.body == "hello"
        assert len(queued.deliveries) == 1

        claimed = await service.claim_inbox(
            session_id=session.id,
            receiver_local_id="receiver",
            db_session=db.sessionmaker,
        )
        assert [message.id for message in claimed] == [queued.id]

        claimed_again = await service.claim_inbox(
            session_id=session.id,
            receiver_local_id="receiver",
            db_session=db.sessionmaker,
        )
        assert claimed_again == []

        rendered = await service.render_mailbox(
            session_id=session.id,
            receiver_local_id="receiver",
            db_session=db.sessionmaker,
        )
        assert [message.id for message in rendered] == [queued.id]
```

- [ ] **Step 2: Run focused test and verify failure**

Run:

```bash
uv run pytest pkgs/operator-core/src/operator_db/objects/mail/tests/service.test.py -q
```

Expected: fails with `NotImplementedError`.

- [ ] **Step 3: Implement minimal mail behavior**

Implementation guidance:

- Resolve all `sender_local_ids` and `receiver_local_ids` within `request.session_id`.
- Reject empty sender or receiver lists with a clear error for now (`ValueError` is acceptable until module errors exist).
- Deduplicate local IDs before writing mapping rows.
- Insert one `MailMessageEnt` and one `MailboxMapping` for each sender/receiver pair.
- `claim_inbox`: select queued deliveries for receiver, ordered by message creation time; mark those delivery rows read; return corresponding `MailResponseSchema` objects.
- `render_mailbox`: select all messages visible to receiver, regardless of state; apply `reverse_order`.
- `mark_delivery_read`: resolve sender/receiver local IDs and update one mapping row.

- [ ] **Step 4: Run focused tests/lint/type and commit**

Run:

```bash
uv run pytest pkgs/operator-core/src/operator_db/objects/mail/tests/service.test.py -q
uv run ruff check pkgs/operator-core/src/operator_db/objects/mail
uv run basedpyright pkgs/operator-core/src/operator_db/objects/mail
```

Commit:

```bash
git add pkgs/operator-core/src/operator_db/objects/mail
git commit -m "feat: implement mail service"
```

## Task 5: Final Verification and Review

**Files:**

- Potentially modify any service/test files based on verification or review.

- [ ] **Step 1: Run focused operator_db integration tests**

Run:

```bash
uv run pytest pkgs/operator-core/src/operator_db -q
```

- [ ] **Step 2: Run narrow static checks**

Run:

```bash
uv run ruff check pkgs/operator-core/src/operator_db
uv run basedpyright pkgs/operator-core/src/operator_db
```

- [ ] **Step 3: Run authoritative verification**

Run:

```bash
just check
```

If `just check` mutates formatting or generated files, inspect the diff and commit necessary changes only if they belong to this work.

- [ ] **Step 4: Code review loop**

Dispatch a reviewer with:

- Requirements from this plan.
- Diff range from the implementation branch base to HEAD.
- Verification evidence.

Fix Critical/Important findings and repeat review until no blocking findings remain.

- [ ] **Step 5: Final commit if needed**

If review/verification produced changes:

```bash
git add <changed files>
git commit -m "fix: address operator db service review"
```

## Task 6: Local Merge

**Files:** none expected.

- [ ] **Step 1: Merge branch locally into `main`**

After final review passes, switch to the main worktree and merge the implementation branch locally.

- [ ] **Step 2: Verify merged result**

Run at least:

```bash
uv run pytest pkgs/operator-core/src/operator_db -q
uv run ruff check pkgs/operator-core/src/operator_db
uv run basedpyright pkgs/operator-core/src/operator_db
```

If practical, run `just check` again on merged `main`.

- [ ] **Step 3: Cleanup**

Remove the implementation worktree after merge verification passes.
