"""Unit coverage for external audit import Celery task failure/recovery codes."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from src.api.routes import external_audit_imports
from src.domain.models.external_audit_import import ExternalAuditImportStatus
from src.infrastructure.tasks import external_audit_import_tasks as tasks


def _bound_params(stmt) -> dict:
    compiled = stmt.compile()
    return {str(k): v for k, v in compiled.params.items()}


def test_recover_stale_import_jobs_uses_distinct_reason_codes() -> None:
    session = AsyncMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    session.execute = AsyncMock(
        side_effect=[SimpleNamespace(rowcount=2), SimpleNamespace(rowcount=1), SimpleNamespace(rowcount=3)]
    )
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

    assert result == {"recovered": 6, "queued_recovered": 2, "processing_recovered": 1, "promoting_recovered": 3}
    assert session.execute.await_count == 3

    first_params = _bound_params(session.execute.await_args_list[0].args[0])
    second_params = _bound_params(session.execute.await_args_list[1].args[0])
    third_params = _bound_params(session.execute.await_args_list[2].args[0])
    assert "STALE_QUEUE_TIMEOUT" in first_params.values()
    assert "STALE_JOB_TIMEOUT" in second_params.values()
    assert "STALE_PROMOTION_LEASE" in third_params.values()


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


@pytest.mark.asyncio
async def test_promote_endpoint_queues_celery_work_and_returns_promoting(monkeypatch: pytest.MonkeyPatch) -> None:
    job = SimpleNamespace(
        id=55,
        reference_number="IMP-00055",
        audit_run_id=7,
        source_document_asset_id=8,
        status=ExternalAuditImportStatus.PROMOTING,
        has_tabular_data=False,
        created_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    service = SimpleNamespace(enqueue_promote=AsyncMock(return_value=job))
    delay = patch.object(external_audit_imports.promote_external_audit_import_job, "delay")
    monkeypatch.setattr(external_audit_imports, "ExternalAuditImportService", lambda _db: service)

    with delay as task_delay:
        response = await external_audit_imports.promote_import_job(
            job_id=job.id,
            db=SimpleNamespace(),
            current_user=SimpleNamespace(id=3, tenant_id=4),
        )

    assert response.status == ExternalAuditImportStatus.PROMOTING
    service.enqueue_promote.assert_awaited_once_with(job_id=55, tenant_id=4, user_id=3)
    task_delay.assert_called_once_with(55, 4, 3)
