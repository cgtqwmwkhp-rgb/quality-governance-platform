"""Slice 2 — File-to-Library creates an IndexJob when COMPLIANCE_FILING_INDEX_ENABLED.

DoD: flag on → one IndexJob for a newly filed document; governance status stays
DRAFT after successful index and after hard OCR failure (indexing_error only).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.config import settings
from src.domain.models.compliance_schedule import ComplianceFilingStatus, ComplianceRecord, ComplianceRecordOutcome
from src.domain.models.document import DocumentStatus, IndexJobStatus
from src.domain.services import compliance_schedule_filing_service as filing
from src.domain.services.index_job_service import IndexJobService, maybe_create_filing_index_job

FILING_MODULE = "src.domain.services.compliance_schedule_filing_service"


def _result(scalar=None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar
    return result


@pytest.fixture
def db():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock(return_value=None)
    session.execute = AsyncMock()
    return session


@pytest.fixture
def user():
    return SimpleNamespace(id=7, tenant_id=1, is_superuser=False, has_permission=lambda _p: True)


def _record(**overrides) -> ComplianceRecord:
    values = dict(
        id=55,
        tenant_id=1,
        external_id="ext-55",
        reference_number="CRC-2026-0001",
        requirement_id=10,
        due_date=date(2026, 4, 1),
        outcome=ComplianceRecordOutcome.COMPLETED,
        completed_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
        filing_status=ComplianceFilingStatus.NOT_FILED,
        library_document_id=None,
        filing_error=None,
    )
    values.update(overrides)
    return ComplianceRecord(**values)


@pytest.mark.asyncio
async def test_maybe_create_filing_index_job_respects_flag_off(db, monkeypatch):
    monkeypatch.setattr(settings, "compliance_filing_index_enabled", False)
    document = SimpleNamespace(id=99, tenant_id=1)
    job = await maybe_create_filing_index_job(db, document=document, created_by_id=7)
    assert job is None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_maybe_create_filing_index_job_creates_pending_job(db, monkeypatch):
    monkeypatch.setattr(settings, "compliance_filing_index_enabled", True)
    document = SimpleNamespace(id=99, tenant_id=1)

    created = SimpleNamespace(id=501, document_ids=[99], status=IndexJobStatus.PENDING)

    async def _fake_create_job(self, **kwargs):
        assert kwargs["document_ids"] == [99]
        assert kwargs["job_type"] == "single"
        assert kwargs["tenant_id"] == 1
        assert kwargs["created_by_id"] == 7
        return created

    with patch.object(IndexJobService, "create_job", _fake_create_job):
        job = await maybe_create_filing_index_job(db, document=document, created_by_id=7)

    assert job is created
    assert job.id == 501


@pytest.mark.asyncio
async def test_file_mode_creates_exactly_one_index_job_when_flag_on(db, user, monkeypatch):
    monkeypatch.setattr(settings, "compliance_filing_index_enabled", True)
    record = _record()
    document = SimpleNamespace(id=321, tenant_id=1, pel_doc_ref="PEL-FIR-01-0001", category_id=4)
    index_job = SimpleNamespace(id=77, document_ids=[321], status=IndexJobStatus.PENDING)

    db.execute = AsyncMock(side_effect=[_result(record)])
    audit = AsyncMock()

    with (
        patch(
            f"{FILING_MODULE}._create_library_document",
            new=AsyncMock(return_value=(document, False, None)),
        ),
        patch(
            f"{FILING_MODULE}.maybe_create_filing_index_job",
            new=AsyncMock(return_value=index_job),
        ) as create_job,
        patch(f"{FILING_MODULE}.record_audit_event", new=audit),
    ):
        result = await filing.file_record_to_library(
            db,
            record_id=55,
            tenant_id=1,
            user=user,
            evidence_asset_id=99,
            category_id=4,
        )

    create_job.assert_awaited_once()
    assert result.index_job is index_job
    assert result.linked_existing is False
    assert result.record.filing_status == ComplianceFilingStatus.FILED
    assert audit.await_args.kwargs["payload"]["index_job_id"] == 77


@pytest.mark.asyncio
async def test_file_mode_skips_index_job_when_flag_off(db, user, monkeypatch):
    monkeypatch.setattr(settings, "compliance_filing_index_enabled", False)
    record = _record()
    document = SimpleNamespace(id=321, tenant_id=1, pel_doc_ref="PEL-FIR-01-0001", category_id=4)

    db.execute = AsyncMock(side_effect=[_result(record)])

    with (
        patch(
            f"{FILING_MODULE}._create_library_document",
            new=AsyncMock(return_value=(document, False, None)),
        ),
        patch(f"{FILING_MODULE}.record_audit_event", new=AsyncMock()),
    ):
        result = await filing.file_record_to_library(
            db,
            record_id=55,
            tenant_id=1,
            user=user,
            evidence_asset_id=99,
            category_id=4,
        )

    assert result.index_job is None
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_link_mode_never_creates_index_job_even_when_flag_on(db, user, monkeypatch):
    monkeypatch.setattr(settings, "compliance_filing_index_enabled", True)
    record = _record()
    document = SimpleNamespace(id=321, tenant_id=1, category_id=8, access_level="all_staff", pel_doc_ref=None)
    db.execute = AsyncMock(side_effect=[_result(record), _result(document)])

    with (
        patch(
            f"{FILING_MODULE}.maybe_create_filing_index_job",
            new=AsyncMock(return_value=SimpleNamespace(id=1)),
        ) as create_job,
        patch(f"{FILING_MODULE}.record_audit_event", new=AsyncMock()),
    ):
        result = await filing.file_record_to_library(
            db,
            record_id=55,
            tenant_id=1,
            user=user,
            library_document_id=321,
        )

    create_job.assert_not_awaited()
    assert result.index_job is None
    assert result.linked_existing is True


def _make_category_process_fixture(monkeypatch: pytest.MonkeyPatch, *, hard_ocr: bool, upsert: bool = True):
    document = SimpleNamespace(
        id=1,
        tenant_id=1,
        file_name="fra.pdf",
        file_path="documents/fra.pdf",
        document_type=SimpleNamespace(value="record"),
        status=DocumentStatus.DRAFT,
        category_id=42,
        has_tables=False,
        indexing_error=None,
        indexed_at=None,
        chunk_count=None,
        ai_summary=None,
        ai_tags=None,
        ai_keywords=None,
        ai_topics=None,
        ai_entities=None,
        ai_confidence=None,
        ai_processed_at=None,
        has_images=None,
        word_count=None,
    )
    job = SimpleNamespace(
        id=5,
        document_ids=[1],
        tenant_id=1,
        status=IndexJobStatus.PENDING,
        started_at=None,
        completed_at=None,
        error_log=None,
        previous_vector_ids=None,
        documents_processed=0,
        documents_succeeded=0,
        documents_failed=0,
        chunks_processed=0,
        chunks_succeeded=0,
        chunks_failed=0,
        chunk_count=0,
    )
    db = AsyncMock()
    db.get = AsyncMock(return_value=document)
    db.flush = AsyncMock()
    previous_chunks_result = MagicMock()
    previous_chunks_result.all.return_value = []
    db.execute = AsyncMock(return_value=previous_chunks_result)

    service = IndexJobService(db)
    service.get_job = AsyncMock(return_value=job)
    service._append_error = AsyncMock()
    if hard_ocr:
        service.intelligence_service.process = AsyncMock(
            return_value=SimpleNamespace(text="", hard_ocr_failure=True, note="unreadable scan")
        )
    else:
        service.intelligence_service.process = AsyncMock(
            return_value=SimpleNamespace(text="Sample FRA text for indexing.", hard_ocr_failure=False, note=None)
        )
    monkeypatch.setattr(
        "src.domain.services.index_job_service.storage_service",
        lambda: SimpleNamespace(download=AsyncMock(return_value=b"%PDF-1.4")),
    )
    monkeypatch.setattr(
        "src.domain.services.index_job_service.DocumentAIService",
        lambda: SimpleNamespace(
            analyze_document=AsyncMock(
                return_value=SimpleNamespace(
                    summary="s",
                    tags=[],
                    keywords=[],
                    topics=[],
                    entities={},
                    confidence=0.9,
                    has_tables=False,
                    has_images=False,
                )
            ),
            generate_chunks=AsyncMock(
                return_value=[
                    SimpleNamespace(content="chunk", index=0, token_count=1, heading=None, char_start=0, char_end=5)
                ]
            ),
        ),
    )
    monkeypatch.setattr(
        "src.domain.services.index_job_service.EmbeddingService",
        lambda: SimpleNamespace(generate_embeddings=AsyncMock(return_value=[[0.1, 0.2]])),
    )
    monkeypatch.setattr(
        "src.domain.services.index_job_service.VectorSearchService",
        lambda: SimpleNamespace(upsert_chunks=AsyncMock(return_value=upsert)),
    )
    return service, document, job


@pytest.mark.asyncio
async def test_filed_document_stays_draft_after_successful_index(monkeypatch: pytest.MonkeyPatch):
    service, document, _job = _make_category_process_fixture(monkeypatch, hard_ocr=False, upsert=True)

    await service.process_job(5, tenant_id=1)

    assert document.status == DocumentStatus.DRAFT
    assert document.indexed_at is not None
    assert document.indexing_error is None


@pytest.mark.asyncio
async def test_hard_ocr_failure_keeps_filed_document_draft_with_indexing_error(
    monkeypatch: pytest.MonkeyPatch,
):
    service, document, _job = _make_category_process_fixture(monkeypatch, hard_ocr=True)

    await service.process_job(5, tenant_id=1)

    assert document.status == DocumentStatus.DRAFT
    assert document.indexing_error == "unreadable scan"
    assert document.indexed_at is None


@pytest.mark.asyncio
async def test_hard_ocr_failure_still_fails_non_category_documents(monkeypatch: pytest.MonkeyPatch):
    """Legacy / non-filed library uploads keep FAILED on hard OCR — do not weaken."""
    service, document, _job = _make_category_process_fixture(monkeypatch, hard_ocr=True)
    document.category_id = None

    await service.process_job(5, tenant_id=1)

    assert document.status == DocumentStatus.FAILED
    assert document.indexing_error == "unreadable scan"
