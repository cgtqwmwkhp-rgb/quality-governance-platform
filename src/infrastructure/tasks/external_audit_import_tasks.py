"""Background tasks for external audit import processing."""

from __future__ import annotations

import asyncio
import logging

from src.infrastructure.database import async_session_maker
from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


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
    except Exception as exc:
        logger.exception("External audit import job %s failed", job_id)
        raise self.retry(exc=exc, countdown=10)
