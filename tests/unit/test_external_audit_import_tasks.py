"""Unit coverage for external audit import Celery task failure/recovery codes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.infrastructure.tasks import external_audit_import_tasks as tasks


def _bound_params(stmt) -> dict:
    compiled = stmt.compile()
    return {str(k): v for k, v in compiled.params.items()}


def test_recover_stale_import_jobs_uses_distinct_reason_codes() -> None:
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.execute = AsyncMock(side_effect=[SimpleNamespace(rowcount=2), SimpleNamespace(rowcount=1)])
    session.commit = AsyncMock()

    def _run(coro):
        loop = __import__("asyncio").new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with patch.object(tasks, "async_session_maker", return_value=session):
        with patch.object(tasks.asyncio, "run", side_effect=_run):
            result = tasks.recover_stale_import_jobs()

    assert result == {"recovered": 3, "queued_recovered": 2, "processing_recovered": 1}
    assert session.execute.await_count == 2

    first_params = _bound_params(session.execute.await_args_list[0].args[0])
    second_params = _bound_params(session.execute.await_args_list[1].args[0])
    assert "STALE_QUEUE_TIMEOUT" in first_params.values()
    assert "STALE_JOB_TIMEOUT" in second_params.values()


def test_mark_job_failed_persists_reason_code() -> None:
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.execute = AsyncMock()
    session.commit = AsyncMock()

    def _run(coro):
        loop = __import__("asyncio").new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

    with patch.object(tasks, "async_session_maker", return_value=session):
        _run(tasks._mark_job_failed(55, "MAX_RETRIES_EXCEEDED", "Processing failed after all retry attempts"))

    session.execute.assert_awaited()
    session.commit.assert_awaited()
    params = _bound_params(session.execute.await_args.args[0])
    assert "MAX_RETRIES_EXCEEDED" in params.values()
