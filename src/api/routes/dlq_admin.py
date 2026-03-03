"""Dead-letter queue admin endpoints for monitoring and managing failed tasks."""

import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.dependencies import CurrentSuperuser
from src.domain.exceptions import ConflictError, NotFoundError

router = APIRouter(prefix="/admin/dlq")
logger = logging.getLogger(__name__)


@router.get("")
async def list_dlq_entries(
    current_user: CurrentSuperuser,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    retried: Optional[bool] = Query(None),
):
    """List failed tasks stored in the dead-letter queue."""
    from sqlalchemy import func, select

    from src.domain.models.failed_task import FailedTask
    from src.infrastructure.database import async_session_maker

    async with async_session_maker() as session:
        query = select(FailedTask).order_by(FailedTask.failed_at.desc())
        if retried is not None:
            query = query.where(FailedTask.retried == retried)

        count_q = select(func.count(FailedTask.id))
        if retried is not None:
            count_q = count_q.where(FailedTask.retried == retried)
        total = (await session.execute(count_q)).scalar() or 0

        result = await session.execute(query.offset(offset).limit(limit))
        rows = result.scalars().all()

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "entries": [
            {
                "id": r.id,
                "task_name": r.task_name,
                "task_id": r.task_id,
                "exception": r.exception,
                "args": r.args,
                "kwargs": r.kwargs,
                "failed_at": r.failed_at.isoformat() if r.failed_at else None,
                "retried": r.retried,
                "retried_at": r.retried_at.isoformat() if r.retried_at else None,
            }
            for r in rows
        ],
    }


@router.post("/{entry_id}/retry")
async def retry_dlq_entry(entry_id: int, current_user: CurrentSuperuser):
    """Re-submit a failed task from the DLQ for execution."""
    from sqlalchemy import select

    from src.domain.models.failed_task import FailedTask
    from src.infrastructure.database import async_session_maker

    async with async_session_maker() as session:
        result = await session.execute(select(FailedTask).where(FailedTask.id == entry_id))
        entry = result.scalar_one_or_none()
        if not entry:
            raise NotFoundError("DLQ entry not found")
        if entry.retried:
            raise ConflictError("Entry already retried")

        # Attempt to re-dispatch via Celery
        try:
            from src.infrastructure.tasks.celery_app import celery_app

            celery_app.send_task(entry.task_name, args=_safe_eval(entry.args))
        except Exception as exc:
            logger.exception("Failed to re-dispatch DLQ task %s", entry.task_name)
            raise HTTPException(status_code=500, detail=f"Retry dispatch failed: {exc}") from exc

        entry.retried = True
        entry.retried_at = datetime.now(timezone.utc)
        await session.commit()

    return {"status": "retried", "entry_id": entry_id}


@router.delete("")
async def purge_dlq(
    current_user: CurrentSuperuser,
    retried_only: bool = Query(True),
):
    """Purge entries from the DLQ. By default only already-retried entries are removed."""
    from sqlalchemy import delete

    from src.domain.models.failed_task import FailedTask
    from src.infrastructure.database import async_session_maker

    async with async_session_maker() as session:
        stmt = delete(FailedTask)
        if retried_only:
            stmt = stmt.where(FailedTask.retried == True)  # noqa: E712
        result = await session.execute(stmt)
        await session.commit()

    return {"purged": result.rowcount}


def _safe_eval(raw: Optional[str]):
    """Best-effort conversion of the stored args string back to a list."""
    if not raw:
        return []
    import ast

    try:
        val = ast.literal_eval(raw)
        return val if isinstance(val, (list, tuple)) else [val]
    except Exception:
        return []
