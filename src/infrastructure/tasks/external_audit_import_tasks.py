"""Background tasks for external audit import processing."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from celery.exceptions import MaxRetriesExceededError  # type: ignore[import-untyped]
from sqlalchemy import update

from src.domain.models.external_audit_import import ExternalAuditImportJob, ExternalAuditImportStatus
from src.infrastructure.database import async_session_maker
from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _mark_job_failed(job_id: int, error_code: str, error_detail: str) -> None:
    """Open a fresh session and mark a job as FAILED."""
    async with async_session_maker() as session:
        await session.execute(
            update(ExternalAuditImportJob)
            .where(ExternalAuditImportJob.id == job_id)
            .values(
                status=ExternalAuditImportStatus.FAILED,
                error_code=error_code,
                error_detail=error_detail,
            )
        )
        await session.commit()


@celery_app.task(
    name="src.infrastructure.tasks.external_audit_import_tasks.process_external_audit_import_job",
    bind=True,
    queue="default",
    max_retries=2,
)
def process_external_audit_import_job(self, job_id: int, tenant_id: int | None, user_id: int | None = None) -> dict:
    """Process a queued external audit import job."""

    async def _run() -> dict:
        from src.domain.services.external_audit_import_service import ExternalAuditImportService

        async with async_session_maker() as session:
            service = ExternalAuditImportService(session)
            job = await service.process_job(job_id=job_id, tenant_id=tenant_id, user_id=user_id)
            await session.commit()
            return {
                "job_id": job.id,
                "status": str(job.status),
                "detected_scheme": job.detected_scheme,
                "outcome_status": job.outcome_status,
            }

    try:
        return asyncio.run(_run())
    except MaxRetriesExceededError:
        logger.error("External audit import job %s exhausted all retries", job_id)
        asyncio.run(_mark_job_failed(job_id, "MAX_RETRIES_EXCEEDED", "Processing failed after all retry attempts"))
        return {"job_id": job_id, "status": "failed"}
    except Exception as exc:
        logger.exception("External audit import job %s failed", job_id)
        raise self.retry(exc=exc, countdown=10)


@celery_app.task(
    name="src.infrastructure.tasks.external_audit_import_tasks.recover_stale_import_jobs",
    queue="default",
)
def recover_stale_import_jobs() -> dict:
    """Find QUEUED/PROCESSING jobs older than 30 minutes and mark them FAILED."""

    async def _run() -> dict:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=30)
        async with async_session_maker() as session:
            result = await session.execute(
                update(ExternalAuditImportJob)
                .where(
                    ExternalAuditImportJob.status.in_(
                        [
                            ExternalAuditImportStatus.QUEUED,
                            ExternalAuditImportStatus.PROCESSING,
                        ]
                    ),
                    ExternalAuditImportJob.updated_at < cutoff,
                )
                .values(
                    status=ExternalAuditImportStatus.FAILED,
                    error_code="STALE_JOB_TIMEOUT",
                    error_detail="Job exceeded 30-minute processing window and was marked failed by the recovery sweep",
                )
            )
            await session.commit()
            count = result.rowcount
            if count:
                logger.warning("Recovered %d stale import jobs", count)
            return {"recovered": count}

    return asyncio.run(_run())
