"""Celery tasks for UK regulatory / practice watch."""

import asyncio
import logging

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(
    name="src.infrastructure.tasks.regulatory_watch_tasks.run_regulatory_watch",
    queue="default",
    bind=True,
    max_retries=2,
)
def run_regulatory_watch(self, tenant_id: int = 1) -> dict:
    """Weekly UK curated-feed poll + KB impact matching (AI-first)."""
    from src.infrastructure.database import async_session_maker

    async def _run() -> dict:
        from src.domain.services.regulatory_watch_service import regulatory_watch_service

        async with async_session_maker() as db:
            return await regulatory_watch_service.run_poll_cycle(
                db,
                tenant_id=tenant_id,
                triggered_by=None,
            )

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.exception("Regulatory watch task failed")
        raise self.retry(exc=exc, countdown=300) from exc
