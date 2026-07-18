"""Index job writer and worker for library document chunk/embed/Pinecone pipeline."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.document import Document, DocumentChunk, DocumentStatus, IndexJob, IndexJobStatus
from src.domain.models.user import User
from src.domain.services.document_ai_service import DocumentAIService, EmbeddingService, VectorSearchService
from src.domain.services.document_intelligence_service import DocumentIntelligenceService
from src.infrastructure.storage import storage_service

logger = logging.getLogger(__name__)


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

        try:
            for document_id in job.document_ids:
                document = await self.db.get(Document, document_id)
                if document is None:
                    await self._append_error(job, f"Document {document_id} not found")
                    chunks_failed += 1
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
                    document.status = DocumentStatus.APPROVED
                    document.indexing_error = document.indexing_error or "Vector indexing unavailable"
                    chunks_failed += len(chunks)

                job.chunks_processed = chunks_total
                job.chunks_succeeded = chunks_succeeded
                job.chunks_failed = chunks_failed
                job.chunk_count = chunks_total
                await self.db.flush()

                if current_user is not None:
                    await self._trigger_governed_kb_mapping(document, text_content, current_user)

            job.status = IndexJobStatus.COMPLETED if chunks_failed == 0 else IndexJobStatus.FAILED
            if chunks_failed and chunks_succeeded:
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


__all__ = ["IndexJobService", "dispatch_index_job"]
