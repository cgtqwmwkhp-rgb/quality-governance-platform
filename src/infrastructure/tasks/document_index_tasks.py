"""Background tasks for library document index jobs."""

from __future__ import annotations

import asyncio
import logging

from celery.exceptions import MaxRetriesExceededError
from sqlalchemy import update

from src.domain.models.document import IndexJob, IndexJobStatus
from src.infrastructure.database import async_session_maker
from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _mark_job_failed(job_id: int, detail: str) -> None:
    async with async_session_maker() as session:
        await session.execute(
            update(IndexJob)
            .where(IndexJob.id == job_id)
            .values(
                status=IndexJobStatus.FAILED,
                error_log=[{"message": detail}],
            )
        )
        await session.commit()


@celery_app.task(
    name="src.infrastructure.tasks.document_index_tasks.process_document_index_job",
    bind=True,
    queue="default",
    max_retries=2,
)
def process_document_index_job(
    self,
    job_id: int,
    tenant_id: int | None,
    user_id: int | None = None,
) -> dict:
    """Process a queued library document index job."""

    async def _run() -> dict:
        from src.domain.models.user import User
        from src.domain.services.index_job_service import IndexJobService

        async with async_session_maker() as session:
            service = IndexJobService(session)
            current_user = await session.get(User, user_id) if user_id else None
            job = await service.process_job(job_id, tenant_id=tenant_id, current_user=current_user)
            await session.commit()
            return {
                "job_id": job.id,
                "status": job.status.value if hasattr(job.status, "value") else str(job.status),
                "chunks_processed": job.chunks_processed,
                "chunks_succeeded": job.chunks_succeeded,
                "chunks_failed": job.chunks_failed,
            }

    try:
        return asyncio.run(_run())
    except MaxRetriesExceededError:
        logger.error("Document index job %s exhausted all retries", job_id)
        asyncio.run(_mark_job_failed(job_id, "Processing failed after all retry attempts."))
        return {"job_id": job_id, "status": "failed", "error_code": "MAX_RETRIES_EXCEEDED"}
    except Exception as exc:
        logger.exception("Document index job %s failed", job_id)
        try:
            raise self.retry(exc=exc, countdown=10)
        except MaxRetriesExceededError:
            asyncio.run(_mark_job_failed(job_id, "Processing failed after all retry attempts."))
            return {"job_id": job_id, "status": "failed", "error_code": "MAX_RETRIES_EXCEEDED"}
