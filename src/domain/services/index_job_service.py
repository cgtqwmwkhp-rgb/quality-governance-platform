"""Index job writer and worker for library document chunk/embed/Pinecone pipeline."""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.domain.models.document import Document, DocumentChunk, DocumentStatus, IndexJob, IndexJobStatus
from src.domain.models.user import User
from src.domain.services.document_ai_service import DocumentAIService, EmbeddingService, VectorSearchService
from src.domain.services.document_intelligence_service import DocumentIntelligenceService
from src.infrastructure.storage import storage_service

logger = logging.getLogger(__name__)

DEFAULT_BULK_REPROCESS_STATUSES = (
    DocumentStatus.INDEXED,
    DocumentStatus.APPROVED,
    DocumentStatus.PUBLISHED,
    DocumentStatus.ACTIVE,
    DocumentStatus.FAILED,
)
MAX_BULK_REPROCESS_LIMIT = 2000
_DOCUMENT_ERROR_PATTERN = re.compile(r"^Document (\d+):")


def vector_index_configured() -> tuple[bool, str | None]:
    """Return whether Voyage + Pinecone are configured for semantic upsert."""
    voyage_key = (getattr(settings, "voyage_api_key", None) or "").strip() or (
        os.getenv("VOYAGE_API_KEY") or ""
    ).strip()
    pinecone_key = (getattr(settings, "pinecone_api_key", None) or "").strip() or (
        os.getenv("PINECONE_API_KEY") or ""
    ).strip()
    if not voyage_key and not pinecone_key:
        return False, "VOYAGE_API_KEY and PINECONE_API_KEY are not configured"
    if not voyage_key:
        return False, "VOYAGE_API_KEY is not configured"
    if not pinecone_key:
        return False, "PINECONE_API_KEY is not configured"
    return True, None


class IndexJobService:
    """Create and process background document indexing jobs."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.intelligence_service = DocumentIntelligenceService()

    async def create_job(
        self,
        *,
        document_ids: list[int],
        job_type: str,
        tenant_id: int | None,
        created_by_id: int | None,
    ) -> IndexJob:
        if not document_ids:
            raise ValueError("document_ids must not be empty")

        job = IndexJob(
            job_type=job_type,
            document_ids=document_ids,
            tenant_id=tenant_id,
            created_by_id=created_by_id,
            status=IndexJobStatus.PENDING,
        )
        self.db.add(job)
        await self.db.flush()
        return job

    async def get_job(self, job_id: int, tenant_id: int | None = None) -> IndexJob | None:
        stmt = select(IndexJob).where(IndexJob.id == job_id)
        if tenant_id is not None:
            stmt = stmt.where(IndexJob.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none()

    async def resolve_bulk_reprocess_document_ids(
        self,
        *,
        tenant_id: int,
        document_ids: list[int] | None = None,
        statuses: tuple[DocumentStatus, ...] | None = None,
        limit: int = 500,
    ) -> list[int]:
        """Resolve tenant-scoped library documents eligible for bulk reindex."""
        if document_ids:
            stmt = (
                select(Document.id)
                .where(
                    Document.id.in_(document_ids),
                    Document.tenant_id == tenant_id,
                    Document.is_active.is_(True),
                )
                .order_by(Document.id)
            )
            result = await self.db.execute(stmt)
            resolved = list(result.scalars())
            missing = sorted(set(document_ids) - set(resolved))
            if missing:
                raise ValueError(f"Documents not found or inactive for tenant: {missing}")
            return resolved

        effective_statuses = statuses or DEFAULT_BULK_REPROCESS_STATUSES
        stmt = (
            select(Document.id)
            .where(
                Document.tenant_id == tenant_id,
                Document.is_active.is_(True),
                Document.is_latest.is_(True),
                Document.status.in_(effective_statuses),
            )
            .order_by(Document.id)
            .limit(min(limit, MAX_BULK_REPROCESS_LIMIT))
        )
        result = await self.db.execute(stmt)
        return list(result.scalars())

    async def resolve_resume_document_ids(self, job_id: int, *, tenant_id: int) -> list[int]:
        """Return document IDs that failed or were not reached in a prior bulk job."""
        job = await self.get_job(job_id, tenant_id=tenant_id)
        if job is None:
            raise ValueError(f"Index job {job_id} not found")
        if not job.document_ids:
            return []

        failed_ids: set[int] = set()
        for entry in job.error_log or []:
            if not isinstance(entry, dict):
                continue
            message = str(entry.get("message") or "")
            match = _DOCUMENT_ERROR_PATTERN.match(message)
            if match:
                failed_ids.add(int(match.group(1)))

        processed_count = int(getattr(job, "documents_processed", 0) or 0)
        remaining_ids = list(job.document_ids[processed_count:])
        resume_ids = sorted(set(remaining_ids) | failed_ids)
        if not resume_ids:
            raise ValueError(f"Index job {job_id} has no remaining documents to resume")
        return resume_ids

    async def create_bulk_reprocess_job(
        self,
        *,
        tenant_id: int,
        created_by_id: int,
        document_ids: list[int] | None = None,
        confirm_full_tenant: bool = False,
        resume_from_job_id: int | None = None,
        limit: int = 500,
    ) -> IndexJob:
        """Create a tenant-scoped bulk reindex job with explicit full-tenant consent."""
        if resume_from_job_id is not None:
            resolved_ids = await self.resolve_resume_document_ids(resume_from_job_id, tenant_id=tenant_id)
        elif document_ids:
            resolved_ids = await self.resolve_bulk_reprocess_document_ids(
                tenant_id=tenant_id,
                document_ids=document_ids,
            )
        elif confirm_full_tenant:
            resolved_ids = await self.resolve_bulk_reprocess_document_ids(
                tenant_id=tenant_id,
                limit=limit,
            )
        else:
            raise ValueError(
                "Bulk reprocess requires explicit document_ids, confirm_full_tenant=true, "
                "or resume_from_job_id"
            )

        if not resolved_ids:
            raise ValueError("No eligible library documents found for bulk reprocess")

        return await self.create_job(
            document_ids=resolved_ids,
            job_type="bulk",
            tenant_id=tenant_id,
            created_by_id=created_by_id,
        )

    async def _append_error(self, job: IndexJob, message: str) -> None:
        errors: list[dict[str, Any]] = list(job.error_log or [])
        errors.append({"at": datetime.now(timezone.utc).isoformat(), "message": message})
        job.error_log = errors

    async def process_job(
        self,
        job_id: int,
        *,
        tenant_id: int | None = None,
        content_cache: dict[int, bytes] | None = None,
        current_user: User | None = None,
    ) -> IndexJob:
        """Run OCR → chunk → embed → Pinecone for each document in the job."""
        job = await self.get_job(job_id, tenant_id=tenant_id)
        if job is None:
            raise ValueError(f"Index job {job_id} not found")

        job.status = IndexJobStatus.PROCESSING
        job.started_at = datetime.now(timezone.utc)
        await self.db.flush()

        ai_service = DocumentAIService()
        embedding_service = EmbeddingService()
        vector_service = VectorSearchService()
        chunks_total = 0
        chunks_succeeded = 0
        chunks_failed = 0
        documents_processed = 0
        documents_succeeded = 0
        documents_failed = 0

        try:
            for document_id in job.document_ids:
                document = await self.db.get(Document, document_id)
                if document is None:
                    await self._append_error(job, f"Document {document_id} not found")
                    documents_failed += 1
                    chunks_failed += 1
                    documents_processed += 1
                    job.documents_processed = documents_processed
                    job.documents_failed = documents_failed
                    continue

                document.status = DocumentStatus.PROCESSING
                content = (content_cache or {}).get(document_id)
                if content is None:
                    content = await storage_service().download(document.file_path)

                extraction = await self.intelligence_service.process(
                    self.db,
                    document_id,
                    purpose="library",
                    content=content,
                )

                text_content = extraction.text.strip()
                if extraction.hard_ocr_failure or not text_content:
                    document.status = DocumentStatus.FAILED if extraction.hard_ocr_failure else DocumentStatus.APPROVED
                    if extraction.hard_ocr_failure:
                        document.indexing_error = extraction.note or "OCR extraction failed"
                    await self._append_error(
                        job,
                        f"Document {document_id}: no searchable text extracted",
                    )
                    documents_failed += 1
                    documents_processed += 1
                    job.documents_processed = documents_processed
                    job.documents_failed = documents_failed
                    continue

                file_ext = document.file_name.rsplit(".", 1)[-1].lower() if document.file_name else ""
                analysis = await ai_service.analyze_document(text_content, document.file_name, file_ext)
                document.ai_summary = analysis.summary
                document.ai_tags = analysis.tags
                document.ai_keywords = analysis.keywords
                document.ai_topics = analysis.topics
                document.ai_entities = analysis.entities
                document.ai_confidence = analysis.confidence
                document.ai_processed_at = datetime.now(timezone.utc)
                document.has_tables = document.has_tables or analysis.has_tables
                document.has_images = analysis.has_images
                document.word_count = len(text_content.split())

                previous_vector_ids = [
                    row
                    for row in (
                        await self.db.execute(
                            select(DocumentChunk.vector_id).where(
                                DocumentChunk.document_id == document.id,
                                DocumentChunk.vector_id.is_not(None),
                            )
                        )
                    ).scalars()
                ]
                if previous_vector_ids and not job.previous_vector_ids:
                    job.previous_vector_ids = previous_vector_ids

                await self.db.execute(delete(DocumentChunk).where(DocumentChunk.document_id == document.id))

                chunks = await ai_service.generate_chunks(text_content)
                document.chunk_count = len(chunks)
                chunks_total += len(chunks)

                for chunk in chunks:
                    self.db.add(
                        DocumentChunk(
                            document_id=document.id,
                            tenant_id=document.tenant_id,
                            content=chunk.content,
                            chunk_index=chunk.index,
                            token_count=chunk.token_count,
                            heading=chunk.heading,
                            char_start=chunk.char_start,
                            char_end=chunk.char_end,
                        )
                    )

                embeddings = await embedding_service.generate_embeddings([chunk.content for chunk in chunks])
                if embeddings and await vector_service.upsert_chunks(
                    document.id,
                    chunks,
                    embeddings,
                    extra_metadata={
                        "tenant_id": document.tenant_id or 0,
                        "document_type": (
                            document.document_type.value
                            if hasattr(document.document_type, "value")
                            else str(document.document_type)
                        ),
                    },
                ):
                    document.indexed_at = datetime.now(timezone.utc)
                    document.status = DocumentStatus.INDEXED
                    document.indexing_error = None
                    chunks_succeeded += len(chunks)
                else:
                    # Chunks + AI metadata are usable for quiz/map/Q&A even when Voyage/Pinecone
                    # are not configured. Mark content-ready via indexed_at; keep APPROVED so
                    # publish can still set PUBLISHED without losing readiness signals.
                    document.indexed_at = datetime.now(timezone.utc)
                    document.status = DocumentStatus.APPROVED
                    document.indexing_error = (
                        document.indexing_error
                        or "Vector indexing unavailable — searchable chunks stored; "
                        "semantic search requires VOYAGE_API_KEY + PINECONE_API_KEY"
                    )
                    chunks_succeeded += len(chunks)

                documents_succeeded += 1
                documents_processed += 1
                job.documents_processed = documents_processed
                job.documents_succeeded = documents_succeeded
                job.documents_failed = documents_failed
                job.chunks_processed = chunks_total
                job.chunks_succeeded = chunks_succeeded
                job.chunks_failed = chunks_failed
                job.chunk_count = chunks_total
                await self.db.flush()

                if current_user is not None:
                    await self._trigger_governed_kb_mapping(document, text_content, current_user)

            job.status = IndexJobStatus.COMPLETED if documents_failed == 0 else IndexJobStatus.FAILED
            if documents_failed and documents_succeeded:
                job.status = IndexJobStatus.COMPLETED
        except Exception as exc:
            logger.exception("Index job %s failed", job_id)
            job.status = IndexJobStatus.FAILED
            await self._append_error(job, str(exc))
            raise
        finally:
            job.completed_at = datetime.now(timezone.utc)
            await self.db.flush()

        return job

    async def _trigger_governed_kb_mapping(self, document: Document, text_content: str, current_user: User) -> None:
        try:
            from src.domain.services.governed_knowledge_service import governed_knowledge_service

            doc_type = (
                document.document_type.value
                if hasattr(document.document_type, "value")
                else str(document.document_type)
            )
            await governed_knowledge_service.map_document_to_schemes(
                self.db,
                document.id,
                text_content,
                doc_type,
                document.tenant_id,
                current_user,
            )
        except Exception:
            logger.warning(
                "Governed KB evidence mapping failed for document %s; indexing continues",
                document.id,
                exc_info=True,
            )


def dispatch_index_job(job_id: int, tenant_id: int | None, user_id: int | None = None) -> bool:
    """Enqueue a Celery index job; return False when dispatch is unavailable."""
    try:
        from src.infrastructure.tasks.document_index_tasks import process_document_index_job

        process_document_index_job.delay(job_id, tenant_id, user_id)
        return True
    except Exception:
        logger.warning("Celery dispatch unavailable for index job %s", job_id, exc_info=True)
        return False


__all__ = [
    "DEFAULT_BULK_REPROCESS_STATUSES",
    "IndexJobService",
    "dispatch_index_job",
    "vector_index_configured",
]
