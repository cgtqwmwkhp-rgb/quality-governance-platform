"""Unit coverage for index job writer/worker."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.domain.models.document import IndexJobStatus
from src.domain.services.index_job_service import IndexJobService


@pytest.mark.asyncio
async def test_create_job_persists_pending_row() -> None:
    db = AsyncMock()
    db.add = lambda obj: setattr(obj, "id", 12) or db.added.append(obj) if hasattr(db, "added") else None
    db.added = []
    db.flush = AsyncMock(side_effect=lambda: setattr(db.added[0], "id", 12) if db.added else None)

    service = IndexJobService(db)
    job = await service.create_job(
        document_ids=[1, 2],
        job_type="bulk",
        tenant_id=3,
        created_by_id=7,
    )

    assert job.job_type == "bulk"
    assert job.document_ids == [1, 2]
    assert job.status == IndexJobStatus.PENDING
    assert job.id == 12


@pytest.mark.asyncio
async def test_process_job_marks_failed_when_document_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    job = SimpleNamespace(
        id=5,
        document_ids=[99],
        tenant_id=1,
        status=IndexJobStatus.PENDING,
        started_at=None,
        completed_at=None,
        error_log=None,
        previous_vector_ids=None,
        chunks_processed=0,
        chunks_succeeded=0,
        chunks_failed=0,
        chunk_count=0,
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=None)
    db.flush = AsyncMock()
    db.execute = AsyncMock()

    service = IndexJobService(db)
    service.get_job = AsyncMock(return_value=job)
    service._append_error = AsyncMock()
    monkeypatch.setattr(
        "src.domain.services.index_job_service.storage_service",
        lambda: SimpleNamespace(download=AsyncMock(return_value=b"content")),
    )

    result = await service.process_job(5, tenant_id=1)

    assert result.status == IndexJobStatus.FAILED
    service._append_error.assert_awaited()
