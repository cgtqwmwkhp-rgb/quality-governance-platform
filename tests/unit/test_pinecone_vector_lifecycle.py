"""Pinecone vector lifecycle coverage: recorded IDs, stale cleanup, disposal cleanup.

Vector IDs are deterministic (``doc_{id}_chunk_{index}``) and deletes are issued
by ID because serverless indexes reject delete-by-metadata-filter.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models.document import DocumentChunk, DocumentStatus, IndexJobStatus
from src.domain.services import document_library_disposal_service as disposal_service
from src.domain.services.document_ai_service import document_chunk_vector_id
from src.domain.services.governed_knowledge_service import GovernedKnowledgeService
from src.domain.services.index_job_service import IndexJobService


def _chunk(index: int) -> SimpleNamespace:
    return SimpleNamespace(
        content=f"chunk-{index}",
        index=index,
        token_count=1,
        heading=None,
        char_start=index * 10,
        char_end=index * 10 + 5,
    )


def _make_index_job_fixture(
    monkeypatch: pytest.MonkeyPatch,
    *,
    upsert_result: bool,
    chunk_count: int = 1,
    previous_chunk_rows: list[tuple[int, str | None]] | None = None,
):
    """Wire IndexJobService.process_job against fakes, exposing the vector service."""
    document = SimpleNamespace(
        id=1,
        tenant_id=1,
        file_name="policy.pdf",
        file_path="documents/policy.pdf",
        document_type=SimpleNamespace(value="policy"),
        status=DocumentStatus.APPROVED,
        has_tables=False,
        indexing_error=None,
        indexed_at=None,
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
    chunk_rows_result = MagicMock()
    chunk_rows_result.all.return_value = previous_chunk_rows or []
    db.execute = AsyncMock(return_value=chunk_rows_result)

    chunks = [_chunk(index) for index in range(chunk_count)]
    vector_service = SimpleNamespace(
        upsert_chunks=AsyncMock(return_value=upsert_result),
        delete_vectors_by_id=AsyncMock(return_value=True),
    )

    service = IndexJobService(db)
    service.get_job = AsyncMock(return_value=job)
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
            generate_chunks=AsyncMock(return_value=chunks),
        ),
    )
    monkeypatch.setattr(
        "src.domain.services.index_job_service.EmbeddingService",
        lambda: SimpleNamespace(generate_embeddings=AsyncMock(return_value=[[0.1, 0.2]] * chunk_count)),
    )
    monkeypatch.setattr(
        "src.domain.services.index_job_service.VectorSearchService",
        lambda: vector_service,
    )
    return service, db, job, vector_service


def _added_chunks(db: AsyncMock) -> list[DocumentChunk]:
    return [call.args[0] for call in db.add.call_args_list if isinstance(call.args[0], DocumentChunk)]


# =============================================================================
# 1. vector_id honesty
# =============================================================================


@pytest.mark.asyncio
async def test_vector_id_recorded_after_successful_upsert(monkeypatch: pytest.MonkeyPatch) -> None:
    service, db, _job, _vector_service = _make_index_job_fixture(monkeypatch, upsert_result=True, chunk_count=2)

    await service.process_job(5, tenant_id=1)

    chunk_rows = _added_chunks(db)
    assert [row.vector_id for row in chunk_rows] == ["doc_1_chunk_0", "doc_1_chunk_1"]


@pytest.mark.asyncio
async def test_vector_id_not_recorded_when_vector_index_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    service, db, _job, vector_service = _make_index_job_fixture(monkeypatch, upsert_result=False, chunk_count=2)

    await service.process_job(5, tenant_id=1)

    chunk_rows = _added_chunks(db)
    assert [row.vector_id for row in chunk_rows] == [None, None]
    vector_service.delete_vectors_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_vector_id_only_recorded_for_chunks_that_received_an_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Voyage can return fewer embeddings than chunks; only upserted rows may claim an ID."""
    service, db, _job, _vector_service = _make_index_job_fixture(monkeypatch, upsert_result=True, chunk_count=3)
    monkeypatch.setattr(
        "src.domain.services.index_job_service.EmbeddingService",
        lambda: SimpleNamespace(generate_embeddings=AsyncMock(return_value=[[0.1, 0.2], [0.3, 0.4]])),
    )

    await service.process_job(5, tenant_id=1)

    chunk_rows = _added_chunks(db)
    assert [row.vector_id for row in chunk_rows] == ["doc_1_chunk_0", "doc_1_chunk_1", None]


# =============================================================================
# 2. Re-index must not orphan high-index vectors
# =============================================================================


@pytest.mark.asyncio
async def test_reindex_with_fewer_chunks_deletes_orphaned_high_index_vectors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _db, job, vector_service = _make_index_job_fixture(
        monkeypatch,
        upsert_result=True,
        chunk_count=1,
        previous_chunk_rows=[(0, "doc_1_chunk_0"), (1, "doc_1_chunk_1"), (2, "doc_1_chunk_2")],
    )

    await service.process_job(5, tenant_id=1)

    vector_service.delete_vectors_by_id.assert_awaited_once_with(["doc_1_chunk_1", "doc_1_chunk_2"])
    assert job.previous_vector_ids == ["doc_1_chunk_0", "doc_1_chunk_1", "doc_1_chunk_2"]


@pytest.mark.asyncio
async def test_reindex_derives_previous_ids_for_legacy_rows_without_vector_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rows indexed before vector_id was recorded still get their vectors cleaned up."""
    service, _db, _job, vector_service = _make_index_job_fixture(
        monkeypatch,
        upsert_result=True,
        chunk_count=1,
        previous_chunk_rows=[(0, None), (1, None)],
    )

    await service.process_job(5, tenant_id=1)

    vector_service.delete_vectors_by_id.assert_awaited_once_with(["doc_1_chunk_1"])


@pytest.mark.asyncio
async def test_reindex_with_more_chunks_deletes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    service, _db, _job, vector_service = _make_index_job_fixture(
        monkeypatch,
        upsert_result=True,
        chunk_count=3,
        previous_chunk_rows=[(0, "doc_1_chunk_0")],
    )

    await service.process_job(5, tenant_id=1)

    vector_service.delete_vectors_by_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_reindex_failing_stale_delete_records_error_without_marking_document_for_resume(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service, _db, job, vector_service = _make_index_job_fixture(
        monkeypatch,
        upsert_result=True,
        chunk_count=1,
        previous_chunk_rows=[(0, "doc_1_chunk_0"), (1, "doc_1_chunk_1")],
    )
    vector_service.delete_vectors_by_id = AsyncMock(return_value=False)

    result = await service.process_job(5, tenant_id=1)

    assert result.status == IndexJobStatus.COMPLETED
    assert result.documents_failed == 0
    messages = [entry["message"] for entry in job.error_log or []]
    assert messages and "Stale vector cleanup incomplete for document 1" in messages[0]
    # "Document N:" is the resume marker; indexing itself succeeded, so it must not match.
    service.get_job = AsyncMock(return_value=job)
    with pytest.raises(ValueError, match="no remaining documents to resume"):
        await service.resolve_resume_document_ids(5, tenant_id=1)


# =============================================================================
# 3. Disposal must delete vectors
# =============================================================================


class _DisposalDb:
    """Fake session recording ordering of chunk reads, deletes, flush and commit."""

    def __init__(self, documents: list[SimpleNamespace], chunk_rows: list[tuple[int, int, str | None]]) -> None:
        self._documents = documents
        self._chunk_rows = chunk_rows
        self.events: list[str] = []
        self.deleted: list[SimpleNamespace] = []

    async def execute(self, statement: object) -> MagicMock:
        result = MagicMock()
        if "document_chunks" in str(statement):
            self.events.append("chunks")
            result.all.return_value = self._chunk_rows
            return result
        result.scalars.return_value.all.return_value = self._documents
        return result

    async def delete(self, obj: SimpleNamespace) -> None:
        self.events.append(f"delete:{obj.id}")
        self.deleted.append(obj)

    async def flush(self) -> None:
        self.events.append("flush")

    async def commit(self) -> None:
        self.events.append("commit")

    async def rollback(self) -> None:
        self.events.append("rollback")


def _disposal_document(document_id: int = 11) -> SimpleNamespace:
    return SimpleNamespace(
        id=document_id,
        file_path=f"documents/{document_id}.pdf",
        retention_until=datetime.now(timezone.utc) - timedelta(days=1),
        status=DocumentStatus.RETIRED,
    )


@pytest.mark.asyncio
async def test_disposal_deletes_vectors_captured_before_the_cascade(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _disposal_document()
    db = _DisposalDb([document], [(11, 0, "doc_11_chunk_0"), (11, 1, None)])
    delete_vectors = AsyncMock(return_value=True)
    monkeypatch.setattr(
        disposal_service,
        "VectorSearchService",
        lambda: SimpleNamespace(api_key="pinecone-test", delete_vectors_by_id=delete_vectors),
    )
    monkeypatch.setattr(disposal_service, "storage_service", lambda: SimpleNamespace(delete=AsyncMock()))

    disposed = await disposal_service.execute_disposal(db, tenant_id=7, document_ids=[11])

    assert disposed == [11]
    # Legacy NULL vector_id falls back to the deterministic scheme.
    delete_vectors.assert_awaited_once_with(["doc_11_chunk_0", "doc_11_chunk_1"])
    assert db.events == ["chunks", "delete:11", "flush", "commit"]


@pytest.mark.asyncio
async def test_disposal_survives_pinecone_failure_without_rolling_back(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _disposal_document()
    db = _DisposalDb([document], [(11, 0, "doc_11_chunk_0")])
    monkeypatch.setattr(
        disposal_service,
        "VectorSearchService",
        lambda: SimpleNamespace(
            api_key="pinecone-test",
            delete_vectors_by_id=AsyncMock(side_effect=RuntimeError("pinecone unavailable")),
        ),
    )
    monkeypatch.setattr(disposal_service, "storage_service", lambda: SimpleNamespace(delete=AsyncMock()))

    disposed = await disposal_service.execute_disposal(db, tenant_id=7, document_ids=[11])

    assert disposed == [11]
    assert "commit" in db.events
    assert "rollback" not in db.events


@pytest.mark.asyncio
async def test_disposal_skips_vector_cleanup_when_index_unconfigured(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _disposal_document()
    db = _DisposalDb([document], [(11, 0, "doc_11_chunk_0")])
    delete_vectors = AsyncMock(return_value=True)
    monkeypatch.setattr(
        disposal_service,
        "VectorSearchService",
        lambda: SimpleNamespace(api_key="", delete_vectors_by_id=delete_vectors),
    )
    monkeypatch.setattr(disposal_service, "storage_service", lambda: SimpleNamespace(delete=AsyncMock()))

    disposed = await disposal_service.execute_disposal(db, tenant_id=7, document_ids=[11])

    assert disposed == [11]
    delete_vectors.assert_not_awaited()


@pytest.mark.asyncio
async def test_disposal_of_ineligible_document_deletes_no_vectors(monkeypatch: pytest.MonkeyPatch) -> None:
    document = _disposal_document()
    document.retention_until = datetime.now(timezone.utc) + timedelta(days=30)
    db = _DisposalDb([document], [(11, 0, "doc_11_chunk_0")])
    delete_vectors = AsyncMock(return_value=True)
    monkeypatch.setattr(
        disposal_service,
        "VectorSearchService",
        lambda: SimpleNamespace(api_key="pinecone-test", delete_vectors_by_id=delete_vectors),
    )
    monkeypatch.setattr(disposal_service, "storage_service", lambda: SimpleNamespace(delete=AsyncMock()))

    disposed = await disposal_service.execute_disposal(db, tenant_id=7, document_ids=[11])

    assert disposed == []
    delete_vectors.assert_not_awaited()
    assert db.deleted == []


# =============================================================================
# 4. Governed Knowledge must not surface orphaned vector hits
# =============================================================================


@pytest.mark.asyncio
async def test_find_documents_for_query_drops_orphaned_vector_hits(monkeypatch: pytest.MonkeyPatch) -> None:
    service = GovernedKnowledgeService()
    monkeypatch.setattr(
        service,
        "_vector_service",
        SimpleNamespace(
            search=AsyncMock(
                return_value=[
                    {"metadata": {"document_id": 404}, "score": 0.95},
                    {"metadata": {"document_id": 5}, "score": 0.80},
                ]
            )
        ),
    )
    db = AsyncMock()
    live_result = MagicMock()
    live_result.scalars.return_value.all.return_value = [5]
    db.execute = AsyncMock(return_value=live_result)

    matches = await service._find_documents_for_query(db, "clause text", 3)

    assert matches == [(5, 80.0)]
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_find_documents_for_query_returns_empty_when_all_hits_are_orphans(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = GovernedKnowledgeService()
    monkeypatch.setattr(
        service,
        "_vector_service",
        SimpleNamespace(search=AsyncMock(return_value=[{"metadata": {"document_id": 404}, "score": 0.95}])),
    )
    db = AsyncMock()
    live_result = MagicMock()
    live_result.scalars.return_value.all.return_value = []
    db.execute = AsyncMock(return_value=live_result)

    assert await service._find_documents_for_query(db, "clause text", 3) == []


@pytest.mark.asyncio
async def test_assess_operational_entity_never_reports_a_titleless_orphan(monkeypatch: pytest.MonkeyPatch) -> None:
    """An orphaned Pinecone hit must not become a RelatedDocumentHit with title=None."""
    service = GovernedKnowledgeService()
    monkeypatch.setattr(
        service,
        "_vector_service",
        SimpleNamespace(search=AsyncMock(return_value=[{"metadata": {"document_id": 404}, "score": 0.95}])),
    )
    monkeypatch.setattr(service, "_map_iso_schemes", AsyncMock(return_value=[]))
    monkeypatch.setattr(service, "_log_ai_decision", AsyncMock())
    monkeypatch.setattr(
        "src.domain.services.governed_knowledge_service.iso_compliance_service",
        SimpleNamespace(multi_stage_analyze=AsyncMock(return_value={"stages": {}, "clause_matches": []})),
    )
    db = AsyncMock()
    empty_result = MagicMock()
    empty_result.scalars.return_value.all.return_value = []
    empty_result.all.return_value = []
    db.execute = AsyncMock(return_value=empty_result)

    result = await service.assess_operational_entity(
        db,
        entity_type="incident",
        entity_id="42",
        content="Operator bypassed the guard interlock during changeover.",
        tenant_id=3,
        user=SimpleNamespace(id=1),
    )

    assert result.related_documents == []


def test_document_chunk_vector_id_matches_the_upsert_scheme() -> None:
    assert document_chunk_vector_id(11, 3) == "doc_11_chunk_3"
