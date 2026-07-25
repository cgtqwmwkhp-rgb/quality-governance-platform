"""Regression coverage: Celery task bodies must not reuse connections across event loops.

Every task in ``src/infrastructure/tasks`` runs its async body through
``asyncio.run``, which closes the event loop it created. The shared async engine
is pooled for the FastAPI process, and a pooled asyncpg connection stays bound to
the loop that opened it — so in production the *first* index job in a worker
process succeeded and the second failed with
``RuntimeError: ... got Future ... attached to a different loop``, after which the
unusable connections were never released and Azure Postgres ran out of slots.

The fix is a worker-scoped :class:`~sqlalchemy.pool.NullPool` engine installed by
``configure_celery_worker_database`` from Celery's worker startup signals.
"""

from __future__ import annotations

import asyncio
import contextlib
import weakref
from types import SimpleNamespace
from typing import Any, Callable, Iterator

import pytest
from celery.signals import worker_init, worker_process_init, worker_ready
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import AsyncAdaptedQueuePool, NullPool

from src.domain.services.index_job_service import IndexJobService
from src.infrastructure import database
from src.infrastructure.tasks import document_index_tasks as tasks
from src.infrastructure.tasks import worker_db

_POSTGRES_URL = "postgresql+asyncpg://user:pass@db.postgres.database.azure.com:5432/qgp?ssl=true"


# =============================================================================
# 1. Engine configuration: pooled for the web app, NullPool for the worker
# =============================================================================


def test_web_engine_keeps_connection_pooling(monkeypatch: pytest.MonkeyPatch) -> None:
    """Disabling pooling in the worker must not disable it for FastAPI requests."""
    monkeypatch.setattr(database, "_is_testing", False)

    kwargs = database._build_async_engine_kwargs(_POSTGRES_URL, pooled=True)

    assert "poolclass" not in kwargs
    assert kwargs["pool_size"] == database._PG_POOL_SIZE
    assert kwargs["max_overflow"] == database._PG_MAX_OVERFLOW
    assert kwargs["pool_pre_ping"] is True


def test_worker_engine_disables_connection_pooling(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(database, "_is_testing", False)

    kwargs = database._build_async_engine_kwargs(_POSTGRES_URL, pooled=False)

    assert kwargs["poolclass"] is NullPool
    # Queue-pool sizing is rejected outright by NullPool, and the statement
    # timeout must survive — background jobs need it as much as requests do.
    assert not {"pool_size", "max_overflow", "pool_timeout", "pool_pre_ping"} & set(kwargs)
    assert kwargs["connect_args"] == {"server_settings": {"statement_timeout": "30000"}}


def test_worker_engine_kwargs_build_a_real_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    """create_async_engine must accept the worker kwargs (no pool arg conflicts)."""
    monkeypatch.setattr(database, "_is_testing", False)

    engine = create_async_engine(
        _POSTGRES_URL,
        **database._build_async_engine_kwargs(_POSTGRES_URL, pooled=False),
    )

    assert isinstance(engine.pool, NullPool)


# =============================================================================
# 2. Worker bootstrap wiring
# =============================================================================


def _connected_receivers(signal: Any) -> list[Any]:
    resolved = []
    for _key, receiver in signal.receivers:
        candidate = receiver() if isinstance(receiver, weakref.ReferenceType) else receiver
        if candidate is not None:
            resolved.append(candidate)
    return resolved


def test_worker_startup_signals_configure_the_database() -> None:
    """Without this wiring the fix never runs in production."""
    assert worker_db._configure_worker_main_process in _connected_receivers(worker_init)
    assert worker_db._configure_worker_child_process in _connected_receivers(worker_process_init)


def test_pool_is_reported_on_worker_ready_not_on_init() -> None:
    """``worker_init`` fires before Celery configures logging, so its records vanish.

    Celery sends ``worker_init`` (celery/worker/worker.py) before ``on_init_blueprint``
    calls ``setup_logging``, and prefork children return early from the idempotent
    rebind — so the rebind's own log line reached the container log from neither
    process. Reporting on ``worker_ready`` is what makes the fix verifiable in prod.
    """
    assert worker_db._log_engine_pool in _connected_receivers(worker_ready)


def test_worker_ready_reports_the_null_pool(monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    engine = create_async_engine(_POSTGRES_URL, poolclass=NullPool)
    monkeypatch.setattr(database, "engine", engine)

    try:
        with caplog.at_level("INFO", logger=worker_db.__name__):
            worker_db._log_engine_pool()
    finally:
        engine.sync_engine.dispose(close=False)

    record = next(r for r in caplog.records if r.name == worker_db.__name__)
    assert record.levelname == "INFO"
    assert "NullPool" in record.getMessage()


def test_worker_ready_warns_when_the_engine_is_still_pooled(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A pooled worker engine is the precondition for the cross-loop failure — warn loudly."""
    engine = create_async_engine(_POSTGRES_URL)
    assert isinstance(engine.pool, AsyncAdaptedQueuePool)
    monkeypatch.setattr(database, "engine", engine)

    try:
        with caplog.at_level("INFO", logger=worker_db.__name__):
            worker_db._log_engine_pool()
    finally:
        engine.sync_engine.dispose(close=False)

    record = next(r for r in caplog.records if r.name == worker_db.__name__)
    assert record.levelname == "WARNING"
    assert "AsyncAdaptedQueuePool" in record.getMessage()
    assert "expected NullPool" in record.getMessage()


def test_configure_celery_worker_database_rebinds_the_shared_session_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Task modules bind ``async_session_maker`` at import; the rebind must reach them."""
    original_engine = database.engine
    original_bind = database.async_session_maker.kw["bind"]
    monkeypatch.setattr(database, "_worker_database_configured", False)
    # Build a production-shaped asyncpg engine (no connection is opened) so the
    # pool class assertion cannot be satisfied by the test-mode NullPool default.
    monkeypatch.setattr(database, "_is_testing", False)
    monkeypatch.setattr(database, "settings", SimpleNamespace(database_url=_POSTGRES_URL, database_echo=False))

    try:
        database.configure_celery_worker_database()

        assert isinstance(database.engine.pool, NullPool)
        assert database.async_session_maker.kw["bind"] is database.engine
        # Same factory object the task modules imported — no re-import needed.
        assert tasks.async_session_maker is database.async_session_maker
    finally:
        worker_engine = database.engine
        database.engine = original_engine
        database.async_session_maker.configure(bind=original_bind)
        if worker_engine is not original_engine:
            worker_engine.sync_engine.dispose(close=False)


def test_configure_celery_worker_database_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    """Prefork children re-enter this on ``worker_process_init``; it must not churn engines."""
    original_engine = database.engine
    original_bind = database.async_session_maker.kw["bind"]
    monkeypatch.setattr(database, "_worker_database_configured", False)

    try:
        database.configure_celery_worker_database()
        first = database.engine
        database.configure_celery_worker_database()

        assert database.engine is first
    finally:
        worker_engine = database.engine
        database.engine = original_engine
        database.async_session_maker.configure(bind=original_bind)
        if worker_engine is not original_engine:
            worker_engine.sync_engine.dispose(close=False)


# =============================================================================
# 3. The production defect: running a task body twice in one process
# =============================================================================


class _Checkout:
    """One connection checkout, recorded from inside a task's async body."""

    def __init__(self, loop: asyncio.AbstractEventLoop, dbapi_connection: object) -> None:
        self.loop = loop
        # Held by strong reference: comparing ``id()`` of a released connection
        # would be flaky because CPython recycles addresses.
        self.dbapi_connection = dbapi_connection


@pytest.fixture
def bind_task_session_maker(tmp_path: Any) -> Iterator[Callable[..., AsyncEngine]]:
    """Point the shared ``async_session_maker`` at a throwaway on-disk engine."""
    original_bind = database.async_session_maker.kw["bind"]
    created: list[AsyncEngine] = []

    def _bind(**engine_kwargs: Any) -> AsyncEngine:
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path}/tasks.db", **engine_kwargs)
        created.append(engine)
        database.async_session_maker.configure(bind=engine)
        return engine

    try:
        yield _bind
    finally:
        database.async_session_maker.configure(bind=original_bind)
        for engine in created:
            with contextlib.suppress(Exception):
                asyncio.run(engine.dispose())


@pytest.fixture
def recorded_checkouts(monkeypatch: pytest.MonkeyPatch) -> list[_Checkout]:
    """Replace the indexing work with a real round trip on the task's own session."""
    checkouts: list[_Checkout] = []

    async def _record_and_return_job(
        self: IndexJobService,
        job_id: int,
        *,
        tenant_id: int | None = None,
        content_cache: dict[int, bytes] | None = None,
        current_user: Any = None,
    ) -> Any:
        await self.db.execute(text("SELECT 1"))
        connection = await self.db.connection()
        raw = await connection.get_raw_connection()
        checkouts.append(_Checkout(asyncio.get_running_loop(), raw.dbapi_connection))
        return SimpleNamespace(
            id=job_id,
            status="completed",
            chunks_processed=1,
            chunks_succeeded=1,
            chunks_failed=0,
        )

    monkeypatch.setattr(IndexJobService, "process_job", _record_and_return_job)
    return checkouts


def test_second_index_job_in_the_same_worker_process_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    bind_task_session_maker: Callable[..., AsyncEngine],
    recorded_checkouts: list[_Checkout],
) -> None:
    """The reported defect: job 5 passed, jobs 6 and 7 died on the reused connection.

    The pool class comes from the production worker configuration rather than
    being hard-coded here, so re-enabling pooling for the worker fails this test.
    """
    monkeypatch.setattr(database, "_is_testing", False)
    worker_kwargs = database._build_async_engine_kwargs(_POSTGRES_URL, pooled=False)
    engine = bind_task_session_maker(poolclass=worker_kwargs["poolclass"])

    first = tasks.process_document_index_job.run(5, 1, None)
    second = tasks.process_document_index_job.run(6, 1, None)

    assert first["job_id"] == 5
    assert second["job_id"] == 6
    assert second["status"] == "completed"

    assert len(recorded_checkouts) == 2
    # Each ``asyncio.run`` really did build its own loop — otherwise this test
    # would pass for the wrong reason.
    assert recorded_checkouts[0].loop is not recorded_checkouts[1].loop
    # …and the second job did not inherit a connection bound to the first,
    # now-closed, loop. This is the invariant that broke in production.
    assert recorded_checkouts[0].dbapi_connection is not recorded_checkouts[1].dbapi_connection
    assert isinstance(engine.pool, NullPool)


def test_pooled_engine_would_reuse_a_connection_across_event_loops(
    bind_task_session_maker: Callable[..., AsyncEngine],
    recorded_checkouts: list[_Checkout],
) -> None:
    """Control: proves the assertion above has teeth rather than passing vacuously.

    ``AsyncAdaptedQueuePool`` is what ``create_async_engine`` gives the asyncpg
    web engine. Handing the same connection to a second, unrelated event loop is
    exactly what asyncpg rejects; SQLite tolerates it, so assert the reuse itself.
    """
    bind_task_session_maker(poolclass=AsyncAdaptedQueuePool)

    tasks.process_document_index_job.run(5, 1, None)
    tasks.process_document_index_job.run(6, 1, None)

    assert len(recorded_checkouts) == 2
    assert recorded_checkouts[0].loop is not recorded_checkouts[1].loop
    assert recorded_checkouts[0].dbapi_connection is recorded_checkouts[1].dbapi_connection
