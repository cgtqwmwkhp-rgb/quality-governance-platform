from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from src.domain.models.compliance_evidence import EvidenceLinkMethod
from src.domain.models.external_audit_import import ExternalAuditImportStatus
from src.services.external_audit_import_service import PROCESSING_TTL_SECONDS, ExternalAuditImportService


@pytest.mark.asyncio
async def test_link_evidence_for_finding_revives_soft_deleted_rows() -> None:
    deleted_link = SimpleNamespace(
        deleted_at=datetime.now(timezone.utc),
        linked_by=EvidenceLinkMethod.MANUAL,
        confidence=None,
        title="Old title",
        notes=None,
    )
    db = SimpleNamespace(
        execute=AsyncMock(return_value=SimpleNamespace(scalar_one_or_none=lambda: deleted_link)),
        add=Mock(),
        flush=AsyncMock(),
    )
    service = ExternalAuditImportService(db)

    await service._link_evidence_for_finding(
        finding_id=321,
        clause_ids=["iso-9001-8.1"],
        tenant_id=1,
        user_id=1,
        note="Recovered evidence",
        confidence=0.88,
    )

    assert deleted_link.deleted_at is None
    assert deleted_link.linked_by == EvidenceLinkMethod.AUTO
    assert deleted_link.confidence == 0.88
    assert deleted_link.notes == "Recovered evidence"


def test_classify_processing_failure_reason_codes() -> None:
    assert ExternalAuditImportService._classify_processing_failure(RuntimeError("OCR timeout"))[0] == "OCR_FAILED"
    assert (
        ExternalAuditImportService._classify_processing_failure(RuntimeError("mistral chat failed"))[0]
        == "AI_ANALYSIS_FAILED"
    )
    assert (
        ExternalAuditImportService._classify_processing_failure(ConnectionError("celery broker down"))[0]
        == "QUEUE_DISPATCH_FAILED"
    )
    assert (
        ExternalAuditImportService._classify_processing_failure(RuntimeError("unexpected boom"))[0]
        == "IMPORT_PROCESSING_FAILED"
    )


def test_is_hard_ai_failure_only_when_configured_provider_fails() -> None:
    completed = SimpleNamespace(provider_status="completed")
    failed = SimpleNamespace(provider_status="failed")
    not_configured = SimpleNamespace(provider_status="not_configured")
    skipped = SimpleNamespace(provider_status="skipped")

    assert ExternalAuditImportService._is_hard_ai_failure(failed, failed) is True
    assert ExternalAuditImportService._is_hard_ai_failure(failed, not_configured) is True
    assert ExternalAuditImportService._is_hard_ai_failure(failed, completed) is False
    assert ExternalAuditImportService._is_hard_ai_failure(not_configured, skipped) is False
    assert ExternalAuditImportService._is_hard_ai_failure(not_configured, not_configured) is False


@pytest.mark.asyncio
async def test_recover_stale_queued_job_sets_stale_queue_timeout() -> None:
    job = SimpleNamespace(
        id=42,
        status=ExternalAuditImportStatus.QUEUED,
        updated_at=datetime.now(timezone.utc) - timedelta(seconds=PROCESSING_TTL_SECONDS + 5),
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        error_code=None,
        error_detail=None,
    )
    db = SimpleNamespace(flush=AsyncMock())
    service = ExternalAuditImportService(db)

    await service._recover_stale_processing(job)

    assert job.status == ExternalAuditImportStatus.FAILED
    assert job.error_code == "STALE_QUEUE_TIMEOUT"
    assert "queued" in (job.error_detail or "").lower()
    db.flush.assert_awaited()


@pytest.mark.asyncio
async def test_recover_stale_processing_job_sets_processing_timeout() -> None:
    job = SimpleNamespace(
        id=43,
        status=ExternalAuditImportStatus.PROCESSING,
        updated_at=datetime.now(timezone.utc) - timedelta(seconds=PROCESSING_TTL_SECONDS + 5),
        created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        error_code=None,
        error_detail=None,
    )
    db = SimpleNamespace(flush=AsyncMock())
    service = ExternalAuditImportService(db)

    await service._recover_stale_processing(job)

    assert job.status == ExternalAuditImportStatus.FAILED
    assert job.error_code == "PROCESSING_TIMEOUT"


@pytest.mark.asyncio
async def test_mark_queue_dispatch_failed_from_queued() -> None:
    job = SimpleNamespace(
        id=7,
        status=ExternalAuditImportStatus.QUEUED,
        tenant_id=1,
        updated_at=datetime.now(timezone.utc),
        created_at=datetime.now(timezone.utc),
        error_code=None,
        error_detail=None,
        updated_by_id=None,
    )
    db = SimpleNamespace(flush=AsyncMock(), refresh=AsyncMock())
    service = ExternalAuditImportService(db)
    service.get_job = AsyncMock(return_value=job)  # type: ignore[method-assign]

    result = await service.mark_queue_dispatch_failed(
        job_id=7,
        tenant_id=1,
        user_id=9,
        detail="Unable to dispatch (ValueError).",
    )

    assert result.status == ExternalAuditImportStatus.FAILED
    assert result.error_code == "QUEUE_DISPATCH_FAILED"
    assert "ValueError" in (result.error_detail or "")
    assert result.updated_by_id == 9
