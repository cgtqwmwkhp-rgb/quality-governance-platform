"""Celery tasks for Safety Insights Analyst deep-runs."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from celery.exceptions import MaxRetriesExceededError  # type: ignore[import-untyped]
from sqlalchemy import select, update

from src.domain.models.safety_insight import SafetyInsightRun, SafetyInsightRunStatus
from src.infrastructure.database import async_session_maker
from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

ALL_MODULES = ["incident", "near_miss", "rta", "complaint"]


def _monthly_digest_enabled() -> bool:
    """Always-on by default; disable via env or optional settings attr."""
    raw = os.environ.get("SAFETY_INSIGHTS_MONTHLY_DIGEST_ENABLED")
    if raw is not None and raw.strip() != "":
        return raw.strip().lower() not in {"0", "false", "no", "off"}
    try:
        from src.core.config import settings

        flag = getattr(settings, "safety_insights_monthly_digest_enabled", None)
        if flag is not None:
            return bool(flag)
    except Exception:  # noqa: BLE001
        pass
    return True


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


async def _enqueue_monthly_digest_for_tenants() -> dict[str, Any]:
    """Create + enqueue an org-wide deep-run per active tenant (fail-closed)."""
    from src.domain.models.tenant import Tenant
    from src.domain.services.safety_insights_analyst import SafetyInsightsAnalystService

    results: dict[str, Any] = {
        "enabled": True,
        "tenants_considered": 0,
        "enqueued": 0,
        "failed": 0,
        "run_ids": [],
        "errors": [],
    }

    async with async_session_maker() as session:
        tenant_ids = list(
            (
                await session.execute(
                    select(Tenant.id).where(Tenant.is_active.is_(True)).order_by(Tenant.id.asc())
                )
            )
            .scalars()
            .all()
        )
        results["tenants_considered"] = len(tenant_ids)

        for tenant_id in tenant_ids:
            try:
                service = SafetyInsightsAnalystService(session)
                run = await service.create_run(
                    tenant_id=int(tenant_id),
                    user_id=None,
                    modules=list(ALL_MODULES),
                    scope="org",
                    include_synthesis=True,
                    include_benchmark=True,
                )
                await session.commit()
                process_safety_insight_run.delay(run.id, int(tenant_id), None)
                results["enqueued"] += 1
                results["run_ids"].append(run.id)
            except Exception as exc:  # noqa: BLE001
                # Fail-closed per tenant — do not abort the whole digest sweep.
                await session.rollback()
                results["failed"] += 1
                results["errors"].append(
                    {"tenant_id": int(tenant_id), "error": type(exc).__name__, "detail": str(exc)[:300]}
                )
                logger.warning(
                    "Monthly safety insights digest failed for tenant %s: %s",
                    tenant_id,
                    type(exc).__name__,
                )

    return results


@celery_app.task(
    name="src.infrastructure.tasks.safety_insights_tasks.run_monthly_safety_insights_digest",
    bind=True,
    queue="default",
    max_retries=1,
    soft_time_limit=540,
    time_limit=600,
)
def run_monthly_safety_insights_digest(self) -> dict:
    """Monthly scheduled digest: org-wide deep-run for each active tenant."""
    if not _monthly_digest_enabled():
        logger.info("Monthly safety insights digest disabled by flag")
        return {"enabled": False, "enqueued": 0, "skipped": True}

    try:
        return asyncio.run(_enqueue_monthly_digest_for_tenants())
    except Exception as exc:
        logger.exception("Monthly safety insights digest sweep failed")
        try:
            raise self.retry(exc=exc, countdown=60)
        except MaxRetriesExceededError:
            return {
                "enabled": True,
                "enqueued": 0,
                "failed": 1,
                "error_code": "MAX_RETRIES_EXCEEDED",
                "detail": str(exc)[:500],
            }
