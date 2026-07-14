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
        from src.services.external_audit_import_service import ExternalAuditImportService

        async with async_session_maker() as session:
            service = ExternalAuditImportService(session)
            job = await service.process_job(job_id=job_id, tenant_id=tenant_id, user_id=user_id)
            await session.commit()
            return {
                "job_id": job.id,
                "status": str(job.status),
                "detected_scheme": job.detected_scheme,
                "outcome_status": job.outcome_status,
                "error_code": job.error_code,
            }

    try:
        return asyncio.run(_run())
    except MaxRetriesExceededError:
        logger.error("External audit import job %s exhausted all retries", job_id)
        asyncio.run(
            _mark_job_failed(
                job_id,
                "MAX_RETRIES_EXCEEDED",
                "Processing failed after all retry attempts. Review logs and retry the job.",
            )
        )
        return {"job_id": job_id, "status": "failed", "error_code": "MAX_RETRIES_EXCEEDED"}
    except Exception as exc:
        logger.exception("External audit import job %s failed", job_id)
        try:
            raise self.retry(exc=exc, countdown=10)
        except MaxRetriesExceededError:
            logger.error("External audit import job %s exhausted retries after exception", job_id)
            asyncio.run(
                _mark_job_failed(
                    job_id,
                    "MAX_RETRIES_EXCEEDED",
                    "Processing failed after all retry attempts. Review logs and retry the job.",
                )
            )
            return {"job_id": job_id, "status": "failed", "error_code": "MAX_RETRIES_EXCEEDED"}


@celery_app.task(
    name="src.infrastructure.tasks.external_audit_import_tasks.promote_external_audit_import_job",
    bind=True,
    queue="default",
    max_retries=2,
)
def promote_external_audit_import_job(self, job_id: int, tenant_id: int | None, user_id: int) -> dict:
    """Run a previously durable promotion claim in independently committed chunks."""

    async def _run() -> dict:
        from src.services.external_audit_import_service import ExternalAuditImportService

        async with async_session_maker() as session:
            service = ExternalAuditImportService(session)
            job = await service.run_promote_chunks(job_id=job_id, tenant_id=tenant_id, user_id=user_id)
            return {
                "job_id": job.id,
                "status": str(job.status),
                "promote_succeeded": job.promote_succeeded,
                "promote_failed": job.promote_failed,
            }

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.exception("External audit promotion job %s failed", job_id)
        try:
            raise self.retry(exc=exc, countdown=10)
        except MaxRetriesExceededError:
            # The service has already returned the job to review_required, preserving
            # accepted drafts and per-draft error codes for an operator retry.
            return {"job_id": job_id, "status": "review_required", "error_code": "PROMOTION_RETRIES_EXHAUSTED"}


@celery_app.task(
    name="src.infrastructure.tasks.external_audit_import_tasks.recover_stale_import_jobs",
    queue="default",
)
def recover_stale_import_jobs() -> dict:
    """Recover stale imports; expired promotion leases return to review_required.

    QUEUED jobs get ``STALE_QUEUE_TIMEOUT`` so a missing worker/broker never
    leaves imports silently queued forever. In-flight processing uses
    ``STALE_JOB_TIMEOUT``.
    """

    async def _run() -> dict:
        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(minutes=30)
        async with async_session_maker() as session:
            queued = await session.execute(
                update(ExternalAuditImportJob)
                .where(
                    ExternalAuditImportJob.status == ExternalAuditImportStatus.QUEUED,
                    ExternalAuditImportJob.updated_at < cutoff,
                )
                .values(
                    status=ExternalAuditImportStatus.FAILED,
                    error_code="STALE_QUEUE_TIMEOUT",
                    error_detail=(
                        "Job remained queued beyond the 30-minute recovery window without a "
                        "worker picking it up. Retry queueing or process synchronously."
                    ),
                )
            )
            in_flight = await session.execute(
                update(ExternalAuditImportJob)
                .where(
                    ExternalAuditImportJob.status.in_(
                        [
                            ExternalAuditImportStatus.PROCESSING,
                        ]
                    ),
                    ExternalAuditImportJob.updated_at < cutoff,
                )
                .values(
                    status=ExternalAuditImportStatus.FAILED,
                    error_code="STALE_JOB_TIMEOUT",
                    error_detail=(
                        "Job exceeded 30-minute processing window and was marked failed by the recovery sweep"
                    ),
                )
            )
            promoting = await session.execute(
                update(ExternalAuditImportJob)
                .where(
                    ExternalAuditImportJob.status == ExternalAuditImportStatus.PROMOTING,
                    ExternalAuditImportJob.promote_lease_expires_at < datetime.now(timezone.utc),
                )
                .values(
                    status=ExternalAuditImportStatus.REVIEW_REQUIRED,
                    promote_lease_expires_at=None,
                    error_code="STALE_PROMOTION_LEASE",
                    error_detail="Promotion lease expired; accepted drafts remain available for a safe retry.",
                )
            )
            await session.commit()
            count = int(queued.rowcount or 0) + int(in_flight.rowcount or 0) + int(promoting.rowcount or 0)
            if count:
                logger.warning("Recovered %d stale import jobs", count)
            return {
                "recovered": count,
                "queued_recovered": int(queued.rowcount or 0),
                "processing_recovered": int(in_flight.rowcount or 0),
                "promoting_recovered": int(promoting.rowcount or 0),
            }

    return asyncio.run(_run())
