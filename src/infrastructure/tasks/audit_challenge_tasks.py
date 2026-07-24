"""Celery tasks for the Audit Builder Check & Challenge coach."""

from __future__ import annotations

import asyncio
import logging

from celery.exceptions import MaxRetriesExceededError  # type: ignore[import-untyped]
from sqlalchemy import update

from src.domain.models.audit_challenge import AuditChallengeSession, AuditChallengeSessionStatus
from src.infrastructure.database import async_session_maker
from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


async def _mark_failed(session_id: int, error_code: str, error_detail: str) -> None:
    async with async_session_maker() as session:
        await session.execute(
            update(AuditChallengeSession)
            .where(AuditChallengeSession.id == session_id)
            .values(
                status=AuditChallengeSessionStatus.FAILED,
                error_code=error_code,
                error_detail=error_detail,
                progress_message="Failed",
            )
        )
        await session.commit()


async def _process(session_id: int, tenant_id: int) -> dict:
    from src.domain.services.audit_challenge_service import AuditChallengeService

    async with async_session_maker() as session:
        service = AuditChallengeService(session)
        result = await service.process_session(session_id, tenant_id)
        await session.commit()
        return {
            "session_id": result.id,
            "status": result.status.value if hasattr(result.status, "value") else str(result.status),
            "error_code": result.error_code,
        }


def process_audit_challenge_session_inline(session_id: int, tenant_id: int, user_id: int | None = None) -> dict:
    """Synchronous inline processor for tests / Celery-unavailable environments."""
    del user_id
    try:
        return asyncio.run(_process(session_id, tenant_id))
    except Exception as exc:  # noqa: BLE001
        logger.exception("Inline audit challenge session %s failed", session_id)
        asyncio.run(_mark_failed(session_id, type(exc).__name__, str(exc)[:2000]))
        return {"session_id": session_id, "status": "failed", "error_code": type(exc).__name__}


@celery_app.task(
    name="src.infrastructure.tasks.audit_challenge_tasks.process_audit_challenge_session",
    bind=True,
    queue="default",
    max_retries=1,
    soft_time_limit=180,
    time_limit=210,
)
def process_audit_challenge_session(self, session_id: int, tenant_id: int, user_id: int | None = None) -> dict:
    del user_id
    try:
        return asyncio.run(_process(session_id, tenant_id))
    except MaxRetriesExceededError:
        asyncio.run(
            _mark_failed(
                session_id,
                "MAX_RETRIES_EXCEEDED",
                "Check & Challenge coach run failed after retries.",
            )
        )
        return {"session_id": session_id, "status": "failed", "error_code": "MAX_RETRIES_EXCEEDED"}
    except Exception as exc:
        logger.exception("Audit challenge session %s failed", session_id)
        try:
            raise self.retry(exc=exc, countdown=10)
        except MaxRetriesExceededError:
            asyncio.run(
                _mark_failed(
                    session_id,
                    "MAX_RETRIES_EXCEEDED",
                    "Check & Challenge coach run failed after retries.",
                )
            )
            return {"session_id": session_id, "status": "failed", "error_code": "MAX_RETRIES_EXCEEDED"}
