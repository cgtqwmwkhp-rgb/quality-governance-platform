"""Celery tasks for Governance Library Wave W3 — review reminders + horizon scan."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Exclusive bands for document review_date reminders (days until due).
BAND_WINDOWS: tuple[tuple[str, int, int], ...] = (
    ("due_7", 0, 7),
    ("due_30", 8, 30),
    ("due_60", 31, 60),
    ("due_90", 61, 90),
)


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def classify_review_reminder_band(
    review_date: Optional[datetime],
    *,
    now: Optional[datetime] = None,
) -> Optional[str]:
    """Map a document review_date to an exclusive reminder band.

    Bands:
    - overdue: review_date < now
    - due_7:  0..7 days inclusive
    - due_30: 8..30 days inclusive
    - due_60: 31..60 days inclusive
    - due_90: 61..90 days inclusive
    """
    if review_date is None:
        return None

    current = _as_utc(now or datetime.now(timezone.utc))
    due = _as_utc(review_date)
    days_until = int((due - current).total_seconds() // 86400)

    if days_until < 0:
        return "overdue"

    for band, low, high in BAND_WINDOWS:
        if low <= days_until <= high:
            return band
    return None


@celery_app.task(
    name="src.infrastructure.tasks.library_review_tasks.check_library_review_reminders",
    queue="notifications",
    bind=True,
    max_retries=2,
)
def check_library_review_reminders(self, tenant_id: Optional[int] = None) -> dict:
    """Daily sweep: classify filed documents into 90/60/30/7/overdue bands.

    Notification delivery is intentionally thin in W3 — classify + count only.
    Full notify/email fan-out lands in a follow-up once FE review UI exists.
    """
    from src.infrastructure.database import async_session_maker

    async def _run() -> dict:
        from sqlalchemy import select

        from src.domain.models.document import Document

        async with async_session_maker() as db:
            stmt = select(Document).where(
                Document.category_id.is_not(None),
                Document.review_date.is_not(None),
            )
            if tenant_id is not None:
                stmt = stmt.where(Document.tenant_id == tenant_id)
            result = await db.execute(stmt)
            documents = list(result.scalars().all())

            band_counts: dict[str, int] = {
                "due_90": 0,
                "due_60": 0,
                "due_30": 0,
                "due_7": 0,
                "overdue": 0,
            }
            now = datetime.now(timezone.utc)
            for doc in documents:
                band = classify_review_reminder_band(doc.review_date, now=now)
                if band and band in band_counts:
                    band_counts[band] += 1

            summary = {
                "documents_scanned": len(documents),
                "in_band": sum(band_counts.values()),
                "bands": band_counts,
            }
            logger.info("Library review reminder sweep: %s", summary)
            return summary

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.exception("Library review reminder task failed")
        raise self.retry(exc=exc, countdown=300) from exc


@celery_app.task(
    name="src.infrastructure.tasks.library_review_tasks.run_library_horizon_scan",
    queue="default",
    bind=True,
    max_retries=2,
)
def run_library_horizon_scan(
    self,
    pack_id: Optional[int] = None,
    tenant_id: Optional[int] = None,
) -> dict:
    """Horizon scan for one pack, or daily sweep of all open packs when pack_id is omitted."""
    from src.infrastructure.database import async_session_maker

    async def _run() -> dict:
        from sqlalchemy import select

        from src.domain.models.library_review import LibraryReviewPack, ReviewPackStatus
        from src.domain.services.library_review_service import run_horizon_scan

        async with async_session_maker() as db:
            if pack_id is not None:
                if tenant_id is None:
                    raise ValueError("tenant_id is required when pack_id is provided")
                findings = await run_horizon_scan(db, tenant_id=tenant_id, pack_id=pack_id)
                await db.commit()
                return {
                    "mode": "single",
                    "pack_id": pack_id,
                    "tenant_id": tenant_id,
                    "findings_created": len(findings),
                    "finding_ids": [f.id for f in findings],
                }

            stmt = select(LibraryReviewPack).where(LibraryReviewPack.status == ReviewPackStatus.OPEN)
            if tenant_id is not None:
                stmt = stmt.where(LibraryReviewPack.tenant_id == tenant_id)
            packs = list((await db.execute(stmt)).scalars().all())
            total_findings = 0
            scanned = 0
            for pack in packs:
                created = await run_horizon_scan(db, tenant_id=pack.tenant_id, pack_id=pack.id)
                total_findings += len(created)
                scanned += 1
            await db.commit()
            summary = {
                "mode": "sweep",
                "packs_scanned": scanned,
                "findings_created": total_findings,
            }
            logger.info("Library horizon scan sweep: %s", summary)
            return summary

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.exception("Library horizon scan task failed pack_id=%s", pack_id)
        raise self.retry(exc=exc, countdown=120) from exc
