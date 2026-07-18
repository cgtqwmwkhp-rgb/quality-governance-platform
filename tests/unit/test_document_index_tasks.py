"""Unit coverage for library document index Celery tasks."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from src.infrastructure.tasks import document_index_tasks as tasks


def test_mark_job_failed_persists_failed_status() -> None:
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
        _run(tasks._mark_job_failed(17, "boom"))

    session.execute.assert_awaited()
    session.commit.assert_awaited()


def test_process_document_index_job_returns_job_payload() -> None:
    expected = {
        "job_id": 17,
        "status": "completed",
        "chunks_processed": 3,
        "chunks_succeeded": 3,
        "chunks_failed": 0,
    }

    with patch.object(tasks.asyncio, "run", return_value=expected):
        result = tasks.process_document_index_job.run(17, 1, 2)

    assert result == expected
