"""Safety Insights Analyst API — async deep-run over H&S case corpora."""

from __future__ import annotations

import logging
import os
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.domain.models.user import User
from src.domain.services.safety_insights_analyst import SafetyInsightsAnalystService

logger = logging.getLogger(__name__)

router = APIRouter()


class DeepRunCreate(BaseModel):
    modules: list[str] = Field(default_factory=lambda: ["incident", "near_miss", "rta", "complaint"])
    scope: str = Field(default="org", pattern="^(org|topic)$")
    topic_query: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    min_cluster_size: int = Field(default=2, ge=2, le=20)
    include_synthesis: bool = True
    include_benchmark: bool = False


async def _dispatch_run(
    *,
    service: SafetyInsightsAnalystService,
    run_id: int,
    tenant_id: int,
    user_id: Optional[int],
) -> None:
    """Enqueue Celery, or process inline when SAFETY_INSIGHTS_INLINE=1 / broker missing."""
    inline = os.environ.get("SAFETY_INSIGHTS_INLINE", "").strip().lower() in {"1", "true", "yes"}
    if not inline:
        try:
            from src.infrastructure.tasks.safety_insights_tasks import process_safety_insight_run

            process_safety_insight_run.delay(run_id, tenant_id, user_id)
            return
        except Exception as exc:  # noqa: BLE001
            logger.warning("Safety insights Celery enqueue failed (%s); falling back inline", type(exc).__name__)
    await service.process_run(run_id=run_id, tenant_id=tenant_id)


@router.post("/runs")
async def start_deep_run(
    payload: DeepRunCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("analytics:create"))],
):
    assert current_user.tenant_id is not None
    service = SafetyInsightsAnalystService(db)
    try:
        run = await service.create_run(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            modules=payload.modules,
            scope=payload.scope,
            topic_query=payload.topic_query,
            date_from=service.parse_date_bound(payload.date_from, end=False),
            date_to=service.parse_date_bound(payload.date_to, end=True),
            min_cluster_size=payload.min_cluster_size,
            include_synthesis=payload.include_synthesis,
            include_benchmark=payload.include_benchmark,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # Persist the queued row before Celery workers can claim it.
    await db.commit()
    await db.refresh(run)
    try:
        await _dispatch_run(
            service=service,
            run_id=run.id,
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
        )
    except RuntimeError as exc:
        if "GEMINI_UNAVAILABLE" in str(exc):
            await db.commit()
            raise HTTPException(
                status_code=503,
                detail="Gemini AI is unavailable — cannot cluster micro-themes",
            ) from exc
        raise
    await db.commit()
    fresh = await service.get_run(run.id, current_user.tenant_id)
    return await service.serialize_run(fresh or run, include_children=True)


@router.get("/runs")
async def list_runs(
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(default=20, ge=1, le=100),
):
    assert current_user.tenant_id is not None
    service = SafetyInsightsAnalystService(db)
    runs = await service.list_runs(current_user.tenant_id, limit=limit)
    return {
        "items": [await service.serialize_run(r, include_children=False) for r in runs],
        "total": len(runs),
    }


@router.get("/runs/{run_id}")
async def get_run(run_id: int, db: DbSession, current_user: CurrentUser):
    assert current_user.tenant_id is not None
    service = SafetyInsightsAnalystService(db)
    run = await service.get_run(run_id, current_user.tenant_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return await service.serialize_run(run, include_children=True)


@router.get("/latest")
async def latest_run(db: DbSession, current_user: CurrentUser):
    assert current_user.tenant_id is not None
    service = SafetyInsightsAnalystService(db)
    run = await service.latest_succeeded(current_user.tenant_id)
    if run is None:
        return {"run": None, "top_themes": [], "ratios": None}
    payload = await service.serialize_run(run, include_children=True)
    return {
        "run": {
            "id": payload["id"],
            "completed_at": payload["completed_at"],
            "corpus_summary": payload["corpus_summary"],
        },
        "top_themes": (payload.get("micro_themes") or [])[:5],
        "ratios": payload.get("ratios"),
        "synthesis_available": payload.get("synthesis_available"),
        "research_available": payload.get("research_available"),
    }


@router.get("/themes/{theme_id}/cases")
async def theme_cases(theme_id: int, db: DbSession, current_user: CurrentUser):
    assert current_user.tenant_id is not None
    service = SafetyInsightsAnalystService(db)
    data = await service.theme_case_ids(theme_id, current_user.tenant_id)
    if data is None:
        raise HTTPException(status_code=404, detail="Theme not found")
    return data


@router.post("/runs/{run_id}/export")
async def export_run(run_id: int, db: DbSession, current_user: CurrentUser):
    """Board-pack JSON export (PDF follow-on in Wave 2)."""
    assert current_user.tenant_id is not None
    service = SafetyInsightsAnalystService(db)
    run = await service.get_run(run_id, current_user.tenant_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    payload = await service.serialize_run(run, include_children=True)
    return {"format": "json", "board_pack": payload}
