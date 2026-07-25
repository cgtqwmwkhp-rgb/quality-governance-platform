"""P0 regression coverage: commit-then-dispatch, honest indexed_at, semantic 404 orphans.

See fix/library-index-semantic-p0.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.api.routes import documents
from src.domain.exceptions import NotFoundError
from src.domain.models.document import DocumentStatus, IndexJobStatus
from src.domain.services.index_job_service import IndexJobService


class OrderTrackingDbSession:
    """Minimal fake AsyncSession that records the order commit/dispatch happen in."""

    def __init__(self) -> None:
        self.events: list[str] = []
        self.added: list[object] = []
        self._next_id = 1

    def add(self, obj: object) -> None:
        self.added.append(obj)

    async def flush(self) -> None:
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                setattr(obj, "id", self._next_id)
                self._next_id += 1

    async def commit(self) -> None:
        self.events.append("commit")

    async def refresh(self, obj: object) -> None:
        pass

    async def rollback(self) -> None:
        self.events.append("rollback")


# =============================================================================
# 1. Commit-then-dispatch race
# =============================================================================


@pytest.mark.asyncio
async def test_reprocess_document_dispatches_only_after_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    """dispatch_index_job must never fire before the IndexJob row has been committed."""
    db = OrderTrackingDbSession()
    doc = SimpleNamespace(
        id=5,
        tenant_id=3,
        file_path="documents/policy.pdf",
        status=DocumentStatus.APPROVED,
        indexing_error=None,
    )
    current_user = SimpleNamespace(id=1, tenant_id=3, is_superuser=False)

    monkeypatch.setattr(documents, "_get_document_or_404", AsyncMock(return_value=doc))
    monkeypatch.setattr(
        documents,
        "storage_service",
        lambda: SimpleNamespace(download=AsyncMock(return_value=b"pdf-bytes")),
    )

    async def fake_create_job(db_arg, doc_arg, *, job_type, current_user):
        # No commit should have happened yet: job creation must precede dispatch.
        assert "commit" not in db_arg.events
        return SimpleNamespace(id=77)

    def fake_dispatch(job_id, tenant_id, user_id):
        db.events.append(f"dispatch:{job_id}")
        assert "commit" in db.events, "dispatch_index_job fired before commit — race condition regression"
        return True

    monkeypatch.setattr(documents, "_create_document_index_job", fake_create_job)
    monkeypatch.setattr(documents, "dispatch_index_job", fake_dispatch)

    response = await documents.reprocess_document(document_id=5, db=db, current_user=current_user)

    assert response.index_job_id == 77
    assert db.events.index("commit") < db.events.index("dispatch:77")


@pytest.mark.asyncio
async def test_bulk_reprocess_dispatches_only_after_commit(monkeypatch: pytest.MonkeyPatch) -> None:
    db = OrderTrackingDbSession()
    current_user = SimpleNamespace(id=1, tenant_id=3, is_superuser=False)
    job = SimpleNamespace(id=88, job_type="bulk", document_ids=[1, 2, 3])

    index_service_mock = AsyncMock()
    index_service_mock.create_bulk_reprocess_job = AsyncMock(return_value=job)
    monkeypatch.setattr(documents, "IndexJobService", lambda db: index_service_mock)

    def fake_dispatch(job_id, tenant_id, user_id):
        db.events.append(f"dispatch:{job_id}")
        assert "commit" in db.events, "dispatch_index_job fired before commit — race condition regression"
        return True

    monkeypatch.setattr(documents, "dispatch_index_job", fake_dispatch)
    monkeypatch.setattr(documents, "vector_index_configured", lambda: (True, None))

    payload = documents.BulkReprocessRequest(confirm_full_tenant=True)
    response = await documents.bulk_reprocess_documents(payload=payload, db=db, current_user=current_user)

    assert response.index_job_id == 88
    assert response.dispatched is True
    assert db.events.index("commit") < db.events.index("dispatch:88")


@pytest.mark.asyncio
async def test_dispatch_single_index_job_falls_back_and_recommits_on_dispatch_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Celery dispatch is unavailable, single-doc paths sync-fallback then commit again."""
    db = OrderTrackingDbSession()
    doc = SimpleNamespace(id=9, tenant_id=4)
    job = SimpleNamespace(id=55)
    current_user = SimpleNamespace(id=2, tenant_id=4)

    monkeypatch.setattr(documents, "dispatch_index_job", lambda *a, **k: False)
    process_job_mock = AsyncMock()
    monkeypatch.setattr(IndexJobService, "process_job", process_job_mock)

    dispatched = await documents._dispatch_single_index_job(
        db,
        job,
        doc,
        b"content-bytes",
        current_user=current_user,
    )

    assert dispatched is False
    process_job_mock.assert_awaited_once()
    _, kwargs = process_job_mock.call_args
    assert kwargs["tenant_id"] == 4
    assert kwargs["content_cache"] == {9: b"content-bytes"}
    assert "commit" in db.events


@pytest.mark.asyncio
async def test_dispatch_bulk_index_job_leaves_pending_on_dispatch_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bulk dispatch failures must NOT synchronously process — leave the job pending."""
    db = OrderTrackingDbSession()
    job = SimpleNamespace(id=66)
    current_user = SimpleNamespace(id=2, tenant_id=4)

    monkeypatch.setattr(documents, "dispatch_index_job", lambda *a, **k: False)

    dispatched = await documents._dispatch_bulk_index_job(
        db,
        job=job,
        tenant_id=4,
        current_user=current_user,
    )

    assert dispatched is False
    assert db.events == []  # no synchronous fallback / extra commit for bulk


# =============================================================================
# 2. Semantic search must not 404 on orphaned vector hits
# =============================================================================


class _FakeSearchDb:
    def __init__(self) -> None:
        self.added: list[object] = []
        self.commit = AsyncMock()

    def add(self, obj: object) -> None:
        self.added.append(obj)


@pytest.mark.asyncio
async def test_semantic_search_skips_orphaned_vector_hits_and_returns_200(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    db = _FakeSearchDb()
    current_user = SimpleNamespace(id=1, tenant_id=3, is_superuser=False)

    matches = [
        {"metadata": {"document_id": 404, "content_preview": "orphan"}, "score": 0.95},
        {
            "metadata": {"document_id": 5, "content_preview": "y", "page_number": 1, "heading": "H"},
            "score": 0.8,
        },
    ]
    search_calls: list[dict] = []

    async def fake_search(query, top_k=10, filter_dict=None):
        search_calls.append(filter_dict)
        return matches

    monkeypatch.setattr(
        documents, "VectorSearchService", lambda: SimpleNamespace(search=AsyncMock(side_effect=fake_search))
    )

    async def fake_get_document(db_arg, doc_id, user, **kwargs):
        if doc_id == 404:
            raise NotFoundError("Document not found")
        return SimpleNamespace(id=5, title="Doc 5", tenant_id=3, reference_number="DOC-5")

    monkeypatch.setattr(documents, "_get_document_or_404", fake_get_document)

    response = await documents.semantic_search(
        db=db,
        current_user=current_user,
        q="policy text search",
        top_k=10,
        document_type=None,
    )

    assert response.total == 1
    assert len(response.results) == 1
    assert response.results[0].document_id == 5
    # Non-superuser tenant filter uses Pinecone's explicit $eq operator form.
    assert search_calls[0] == {"tenant_id": {"$eq": 3}}


@pytest.mark.asyncio
async def test_semantic_search_skips_non_numeric_document_id_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeSearchDb()
    current_user = SimpleNamespace(id=1, tenant_id=3, is_superuser=True)

    matches = [{"metadata": {"document_id": "not-an-int", "content_preview": "bad"}, "score": 0.5}]
    monkeypatch.setattr(
        documents,
        "VectorSearchService",
        lambda: SimpleNamespace(search=AsyncMock(return_value=matches)),
    )
    get_doc_mock = AsyncMock()
    monkeypatch.setattr(documents, "_get_document_or_404", get_doc_mock)

    response = await documents.semantic_search(
        db=db,
        current_user=current_user,
        q="policy text search",
        top_k=10,
        document_type=None,
    )

    assert response.total == 0
    assert response.results == []
    get_doc_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_semantic_search_document_type_filter_uses_eq_operator(monkeypatch: pytest.MonkeyPatch) -> None:
    db = _FakeSearchDb()
    current_user = SimpleNamespace(id=1, tenant_id=3, is_superuser=True)
    search_calls: list[dict] = []

    async def fake_search(query, top_k=10, filter_dict=None):
        search_calls.append(filter_dict)
        return []

    monkeypatch.setattr(
        documents, "VectorSearchService", lambda: SimpleNamespace(search=AsyncMock(side_effect=fake_search))
    )

    await documents.semantic_search(
        db=db,
        current_user=current_user,
        q="policy text search",
        top_k=10,
        document_type="policy",
    )

    assert search_calls[0] == {"document_type": {"$eq": "policy"}}


# =============================================================================
# 3. indexed_at honesty
# =============================================================================


def _make_process_job_fixture(monkeypatch: pytest.MonkeyPatch, *, upsert_result: bool):
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
    previous_chunks_result = MagicMock()
    previous_chunks_result.all.return_value = []
    db.execute = AsyncMock(return_value=previous_chunks_result)

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
        lambda: SimpleNamespace(upsert_chunks=AsyncMock(return_value=upsert_result)),
    )
    return service, document


@pytest.mark.asyncio
async def test_indexed_at_not_set_when_upsert_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    service, document = _make_process_job_fixture(monkeypatch, upsert_result=False)

    result = await service.process_job(5, tenant_id=1)

    assert document.indexed_at is None
    assert document.indexing_error is not None
    assert document.status == DocumentStatus.APPROVED
    assert result.documents_succeeded == 1


@pytest.mark.asyncio
async def test_indexed_at_set_when_upsert_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    service, document = _make_process_job_fixture(monkeypatch, upsert_result=True)

    await service.process_job(5, tenant_id=1)

    assert document.indexed_at is not None
    assert document.indexing_error is None
    assert document.status == DocumentStatus.INDEXED


# =============================================================================
# 4. Celery defensive retry on missing job
# =============================================================================


def test_process_document_index_job_retries_when_job_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from src.infrastructure.tasks import document_index_tasks as tasks

    class FakeRetry(Exception):
        pass

    retry_calls: list[tuple] = []

    def fake_retry(exc=None, countdown=None):
        retry_calls.append((exc, countdown))
        raise FakeRetry("retry-requested")

    # `.run` is Celery's bound-method entrypoint (self is the Task singleton
    # itself); patch the task's own `.retry`/`.request` rather than fabricating
    # a standalone `self`.
    monkeypatch.setattr(tasks.process_document_index_job, "retry", fake_retry)
    monkeypatch.setattr(
        tasks.asyncio,
        "run",
        MagicMock(side_effect=ValueError("Index job 42 not found")),
    )

    tasks.process_document_index_job.push_request(retries=0)
    try:
        with pytest.raises(FakeRetry):
            tasks.process_document_index_job.run(42, 1, None)
    finally:
        tasks.process_document_index_job.pop_request()

    assert len(retry_calls) == 1
    exc, countdown = retry_calls[0]
    assert isinstance(exc, ValueError)
    assert countdown == 10
