"""Unit coverage for bulk Pinecone reprocess helpers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models.document import DocumentStatus, IndexJobStatus
from src.domain.services.index_job_service import IndexJobService, vector_index_configured


@pytest.mark.asyncio
async def test_create_bulk_reprocess_job_requires_explicit_scope() -> None:
    service = IndexJobService(AsyncMock())
    with pytest.raises(ValueError, match="confirm_full_tenant"):
        await service.create_bulk_reprocess_job(
            tenant_id=1,
            created_by_id=7,
        )


@pytest.mark.asyncio
async def test_create_bulk_reprocess_job_with_document_ids() -> None:
    db = AsyncMock()
    service = IndexJobService(db)
    service.resolve_bulk_reprocess_document_ids = AsyncMock(return_value=[10, 11])
    service.create_job = AsyncMock(
        return_value=SimpleNamespace(id=42, job_type="bulk", document_ids=[10, 11], status=IndexJobStatus.PENDING)
    )

    job = await service.create_bulk_reprocess_job(
        tenant_id=1,
        created_by_id=7,
        document_ids=[10, 11],
    )

    service.resolve_bulk_reprocess_document_ids.assert_awaited_once_with(
        tenant_id=1,
        document_ids=[10, 11],
    )
    service.create_job.assert_awaited_once_with(
        document_ids=[10, 11],
        job_type="bulk",
        tenant_id=1,
        created_by_id=7,
    )
    assert job.id == 42


@pytest.mark.asyncio
async def test_create_bulk_reprocess_job_full_tenant() -> None:
    db = AsyncMock()
    service = IndexJobService(db)
    service.resolve_bulk_reprocess_document_ids = AsyncMock(return_value=[1, 2, 3])
    service.create_job = AsyncMock(return_value=SimpleNamespace(id=5, document_ids=[1, 2, 3]))

    await service.create_bulk_reprocess_job(
        tenant_id=9,
        created_by_id=3,
        confirm_full_tenant=True,
        limit=250,
    )

    service.resolve_bulk_reprocess_document_ids.assert_awaited_once_with(
        tenant_id=9,
        limit=250,
    )


@pytest.mark.asyncio
async def test_resolve_resume_document_ids_merges_failures_and_remaining() -> None:
    job = SimpleNamespace(
        id=8,
        document_ids=[1, 2, 3, 4],
        documents_processed=2,
        error_log=[{"message": "Document 2: no searchable text extracted"}],
    )
    service = IndexJobService(AsyncMock())
    service.get_job = AsyncMock(return_value=job)

    resume_ids = await service.resolve_resume_document_ids(8, tenant_id=1)

    assert resume_ids == [2, 3, 4]


@pytest.mark.asyncio
async def test_resolve_bulk_reprocess_document_ids_scopes_to_tenant() -> None:
    db = AsyncMock()
    execute_result = MagicMock()
    execute_result.scalars.return_value = [7, 8]
    db.execute = AsyncMock(return_value=execute_result)

    service = IndexJobService(db)
    ids = await service.resolve_bulk_reprocess_document_ids(
        tenant_id=3,
        document_ids=[7, 8],
    )

    assert ids == [7, 8]
    db.execute.assert_awaited()


def test_vector_index_configured_honest_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOYAGE_API_KEY", "")
    monkeypatch.setenv("PINECONE_API_KEY", "")
    monkeypatch.setattr(
        "src.domain.services.index_job_service.settings",
        SimpleNamespace(voyage_api_key="", pinecone_api_key=""),
    )

    configured, warning = vector_index_configured()

    assert configured is False
    assert warning is not None
    assert "VOYAGE_API_KEY" in warning
    assert "PINECONE_API_KEY" in warning


def test_vector_index_configured_true_when_keys_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("VOYAGE_API_KEY", "voyage-test")
    monkeypatch.setenv("PINECONE_API_KEY", "pinecone-test")
    monkeypatch.setattr(
        "src.domain.services.index_job_service.settings",
        SimpleNamespace(voyage_api_key="voyage-test", pinecone_api_key="pinecone-test"),
    )

    configured, warning = vector_index_configured()

    assert configured is True
    assert warning is None


@pytest.mark.asyncio
async def test_process_job_updates_document_progress_counters(monkeypatch: pytest.MonkeyPatch) -> None:
    document = SimpleNamespace(
        id=1,
        tenant_id=1,
        file_name="policy.pdf",
        file_path="documents/policy.pdf",
        document_type=SimpleNamespace(value="policy"),
        status=DocumentStatus.APPROVED,
        has_tables=False,
        indexing_error=None,
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
    vector_ids_result = MagicMock()
    vector_ids_result.scalars.return_value = []
    db.execute = AsyncMock(return_value=vector_ids_result)

    service = IndexJobService(db)
    service.get_job = AsyncMock(return_value=job)
    service._append_error = AsyncMock()
    service.intelligence_service.process = AsyncMock(
        return_value=SimpleNamespace(text="Sample policy text for indexing.", hard_ocr_failure=False, note=None)
    )
    monkeypatch.setattr(
        "src.domain.services.index_job_service.storage_service",
        lambda: SimpleNamespace(download=AsyncMock(return_value=b"pdf-bytes")),
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
        lambda: SimpleNamespace(upsert_chunks=AsyncMock(return_value=True)),
    )

    result = await service.process_job(5, tenant_id=1)

    assert result.documents_processed == 1
    assert result.documents_succeeded == 1
    assert result.documents_failed == 0
    assert result.status == IndexJobStatus.COMPLETED
