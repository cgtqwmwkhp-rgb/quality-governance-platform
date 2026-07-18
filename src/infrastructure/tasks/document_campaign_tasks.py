"""Background tasks for document campaign reminder processing."""

from __future__ import annotations

import asyncio
import logging

from src.infrastructure.database import async_session_maker
from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="src.infrastructure.tasks.document_campaign_tasks.process_campaign_reminders",
    queue="default",
    bind=True,
    max_retries=3,
)
def process_campaign_reminders(self) -> dict:
    """Hourly sweep: mark overdue assignments and send due campaign reminders."""

    async def _run() -> dict:
        from src.domain.services.document_campaign_service import DocumentCampaignService

        async with async_session_maker() as session:
            service = DocumentCampaignService(session)
            return await service.process_due_reminders()

    try:
        result = asyncio.run(_run())
        logger.info("Campaign reminder sweep completed: %s", result)
        return result
    except Exception as exc:
        logger.exception("Campaign reminder sweep failed")
        raise self.retry(exc=exc, countdown=300) from exc
