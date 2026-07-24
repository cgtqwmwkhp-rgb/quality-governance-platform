"""Celery tasks for Safety Insights Analyst deep-runs."""

from __future__ import annotations

import asyncio
import logging

from celery.exceptions import MaxRetriesExceededError  # type: ignore[import-untyped]
from sqlalchemy import update

from src.domain.models.safety_insight import SafetyInsightRun, SafetyInsightRunStatus
from src.infrastructure.database import async_session_maker
from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _mark_failed(run_id: int, error_code: str, error_detail: str) -> None:
    async with async_session_maker() as session:
        await session.execute(
            update(SafetyInsightRun)
            .where(SafetyInsightRun.id == run_id)
            .values(
                status=SafetyInsightRunStatus.FAILED,
                error_code=error_code,
                error_detail=error_detail,
                progress_message="Failed",
            )
        )
        await session.commit()


async def _process(run_id: int, tenant_id: int) -> dict:
    from src.domain.services.safety_insights_analyst import SafetyInsightsAnalystService

    async with async_session_maker() as session:
        service = SafetyInsightsAnalystService(session)
        run = await service.process_run(run_id=run_id, tenant_id=tenant_id)
        await session.commit()
        return {
            "run_id": run.id,
            "status": run.status.value if hasattr(run.status, "value") else str(run.status),
            "error_code": run.error_code,
        }


def process_safety_insight_run_inline(run_id: int, tenant_id: int, user_id: int | None = None) -> dict:
    """Synchronous inline processor for tests / Celery-unavailable environments."""
    del user_id
    try:
        return asyncio.run(_process(run_id, tenant_id))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Inline safety insight run %s failed", run_id)
        asyncio.run(_mark_failed(run_id, type(exc).__name__, str(exc)[:2000]))
        return {"run_id": run_id, "status": "failed", "error_code": type(exc).__name__}


@celery_app.task(
    name="src.infrastructure.tasks.safety_insights_tasks.process_safety_insight_run",
    bind=True,
    queue="default",
    max_retries=1,
    soft_time_limit=540,
    time_limit=600,
)
def process_safety_insight_run(self, run_id: int, tenant_id: int, user_id: int | None = None) -> dict:
    del user_id
    try:
        return asyncio.run(_process(run_id, tenant_id))
    except MaxRetriesExceededError:
        asyncio.run(
            _mark_failed(
                run_id,
                "MAX_RETRIES_EXCEEDED",
                "Safety insights deep-run failed after retries.",
            )
        )
        return {"run_id": run_id, "status": "failed", "error_code": "MAX_RETRIES_EXCEEDED"}
    except Exception as exc:
        logger.exception("Safety insight run %s failed", run_id)
        try:
            raise self.retry(exc=exc, countdown=15)
        except MaxRetriesExceededError:
            asyncio.run(
                _mark_failed(
                    run_id,
                    "MAX_RETRIES_EXCEEDED",
                    "Safety insights deep-run failed after retries.",
                )
            )
            return {"run_id": run_id, "status": "failed", "error_code": "MAX_RETRIES_EXCEEDED"}
