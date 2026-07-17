"""Unified Governance Calendar feed — aggregates timed work across modules."""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Optional, cast

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

EVENT_TYPES = frozenset({"audit", "deadline", "review", "training", "meeting"})


def _as_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _day_bounds(start: date, end: date) -> tuple[datetime, datetime]:
    start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
    end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)
    return start_dt, end_dt


def _iso_date(dt: datetime) -> str:
    return _as_utc(dt).date().isoformat()


def _status_for(dt: datetime, raw_status: Optional[str], *, today: date) -> str:
    status = (raw_status or "").lower()
    if status in {"completed", "closed", "cancelled", "verified"}:
        return "completed"
    event_day = _as_utc(dt).date()
    if event_day < today:
        return "overdue"
    if event_day == today:
        return "today"
    return "upcoming"


class CalendarFeedService:
    """Build a tenant-scoped calendar event feed from live operational tables."""

    def __init__(self, db: AsyncSession, *, tenant_id: Optional[int]) -> None:
        self.db = db
        self.tenant_id = tenant_id

    async def get_feed(
        self,
        *,
        start: date,
        end: date,
        types: Optional[list[str]] = None,
    ) -> dict[str, Any]:
        if end < start:
            start, end = end, start
        # Guard unbounded ranges
        if (end - start).days > 400:
            end = start + timedelta(days=400)

        wanted = {t.strip().lower() for t in (types or []) if t and t.strip()}
        if wanted:
            wanted &= EVENT_TYPES
        else:
            wanted = set(EVENT_TYPES)

        start_dt, end_dt = _day_bounds(start, end)
        today = datetime.now(timezone.utc).date()
        events: list[dict[str, Any]] = []
        sources_ok: list[str] = []
        sources_failed: list[str] = []

        loaders = [
            ("audit_runs", self._load_audit_runs),
            ("scheduled_audits", self._load_scheduled_audits),
            ("capa_actions", self._load_capa_actions),
            ("certificates", self._load_certificates),
            ("assessments", self._load_assessments),
            ("inductions", self._load_inductions),
        ]
        for name, loader in loaders:
            try:
                chunk = await loader(start_dt, end_dt, today)
                events.extend(chunk)
                sources_ok.append(name)
            except Exception:
                logger.warning("calendar feed source failed: %s", name, exc_info=True)
                sources_failed.append(name)

        if wanted != EVENT_TYPES:
            events = [e for e in events if e.get("type") in wanted]

        events.sort(key=lambda e: (e.get("date") or "", e.get("title") or ""))

        return {
            "start": start.isoformat(),
            "end": end.isoformat(),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total": len(events),
            "events": events,
            "sources_ok": sources_ok,
            "sources_failed": sources_failed,
        }

    async def _load_audit_runs(self, start_dt: datetime, end_dt: datetime, today: date) -> list[dict[str, Any]]:
        from src.domain.models.audit import AuditRun

        start_naive = start_dt.replace(tzinfo=None)
        end_naive = end_dt.replace(tzinfo=None)
        stmt = select(AuditRun).where(
            AuditRun.scheduled_date.is_not(None),
            or_(
                and_(AuditRun.scheduled_date >= start_dt, AuditRun.scheduled_date <= end_dt),
                and_(AuditRun.scheduled_date >= start_naive, AuditRun.scheduled_date <= end_naive),
            ),
        )
        if self.tenant_id is not None:
            stmt = stmt.where(AuditRun.tenant_id == self.tenant_id)
        result = await self.db.execute(stmt.limit(500))
        rows = list(result.scalars().all())
        out: list[dict[str, Any]] = []
        for run in rows:
            when = run.scheduled_date or run.due_date
            if when is None:
                continue
            status_val = run.status.value if hasattr(run.status, "value") else str(run.status)
            out.append(
                {
                    "id": f"audit_run:{run.id}",
                    "title": run.title or run.reference_number or f"Audit #{run.id}",
                    "type": "audit",
                    "date": _iso_date(when),
                    "status": _status_for(when, status_val, today=today),
                    "priority": "high" if status_val in {"overdue"} else "medium",
                    "owner": None,
                    "source_module": "audit_run",
                    "source_id": str(run.id),
                    "href": f"/audits/{run.id}/execute",
                    "description": run.location or run.assurance_scheme,
                }
            )
        return out

    async def _load_scheduled_audits(self, start_dt: datetime, end_dt: datetime, today: date) -> list[dict[str, Any]]:
        from src.domain.models.compliance_automation import ScheduledAudit

        start_naive = start_dt.replace(tzinfo=None)
        end_naive = end_dt.replace(tzinfo=None)
        stmt = select(ScheduledAudit).where(
            ScheduledAudit.is_active == True,  # noqa: E712
            ScheduledAudit.next_due_date >= start_naive,
            ScheduledAudit.next_due_date <= end_naive,
        )
        if self.tenant_id is not None:
            stmt = stmt.where(or_(ScheduledAudit.tenant_id == self.tenant_id, ScheduledAudit.tenant_id.is_(None)))
        result = await self.db.execute(stmt.limit(200))
        rows = list(result.scalars().all())
        out: list[dict[str, Any]] = []
        for row in rows:
            when = row.next_due_date
            out.append(
                {
                    "id": f"scheduled_audit:{row.id}",
                    "title": row.name,
                    "type": "audit",
                    "date": _iso_date(when),
                    "status": _status_for(when, None, today=today),
                    "priority": "medium",
                    "owner": None,
                    "source_module": "scheduled_audit",
                    "source_id": str(row.id),
                    "href": "/audits",
                    "description": f"{row.frequency} · {row.audit_type}",
                }
            )
        return out

    async def _load_capa_actions(self, start_dt: datetime, end_dt: datetime, today: date) -> list[dict[str, Any]]:
        from src.domain.models.capa import CAPAAction

        start_naive = start_dt.replace(tzinfo=None)
        end_naive = end_dt.replace(tzinfo=None)
        stmt = select(CAPAAction).where(
            CAPAAction.due_date.is_not(None),
            CAPAAction.due_date >= start_naive,
            CAPAAction.due_date <= end_naive,
        )
        if self.tenant_id is not None:
            stmt = stmt.where(CAPAAction.tenant_id == self.tenant_id)
        result = await self.db.execute(stmt.limit(500))
        rows = list(result.scalars().all())
        out: list[dict[str, Any]] = []
        for row in rows:
            if row.due_date is None:
                continue
            when = cast(datetime, row.due_date)
            status_val = row.status.value if hasattr(row.status, "value") else str(row.status)
            out.append(
                {
                    "id": f"capa:{row.id}",
                    "title": row.title or row.reference_number or f"Action #{row.id}",
                    "type": "deadline",
                    "date": _iso_date(when),
                    "status": _status_for(when, status_val, today=today),
                    "priority": (
                        "high"
                        if str(getattr(row.priority, "value", row.priority)).lower() in {"high", "critical"}
                        else "medium"
                    ),
                    "owner": None,
                    "source_module": "capa_action",
                    "source_id": str(row.id),
                    "href": f"/actions?source_type=capa&q={row.reference_number or row.id}",
                    "description": row.reference_number,
                }
            )
        return out

    async def _load_certificates(self, start_dt: datetime, end_dt: datetime, today: date) -> list[dict[str, Any]]:
        from src.domain.models.compliance_automation import Certificate

        start_naive = start_dt.replace(tzinfo=None)
        end_naive = end_dt.replace(tzinfo=None)
        stmt = select(Certificate).where(
            Certificate.expiry_date >= start_naive,
            Certificate.expiry_date <= end_naive,
        )
        if self.tenant_id is not None:
            stmt = stmt.where(or_(Certificate.tenant_id == self.tenant_id, Certificate.tenant_id.is_(None)))
        result = await self.db.execute(stmt.limit(200))
        rows = list(result.scalars().all())
        out: list[dict[str, Any]] = []
        for row in rows:
            when = row.expiry_date
            out.append(
                {
                    "id": f"certificate:{row.id}",
                    "title": f"Cert expiry: {row.name}",
                    "type": "deadline",
                    "date": _iso_date(when),
                    "status": _status_for(when, row.status, today=today),
                    "priority": "high" if row.is_critical else "medium",
                    "owner": row.entity_name,
                    "source_module": "certificate",
                    "source_id": str(row.id),
                    "href": "/compliance-automation",
                    "description": row.issuing_body or row.certificate_type,
                }
            )
        return out

    async def _load_assessments(self, start_dt: datetime, end_dt: datetime, today: date) -> list[dict[str, Any]]:
        from src.domain.models.assessment import AssessmentRun

        stmt = select(AssessmentRun).where(
            AssessmentRun.scheduled_date.is_not(None),
            AssessmentRun.scheduled_date >= start_dt,
            AssessmentRun.scheduled_date <= end_dt,
        )
        if self.tenant_id is not None:
            stmt = stmt.where(or_(AssessmentRun.tenant_id == self.tenant_id, AssessmentRun.tenant_id.is_(None)))
        result = await self.db.execute(stmt.limit(300))
        rows = list(result.scalars().all())
        out: list[dict[str, Any]] = []
        for row in rows:
            when = row.scheduled_date
            if when is None:
                continue
            status_val = row.status.value if hasattr(row.status, "value") else str(row.status)
            out.append(
                {
                    "id": f"assessment:{row.id}",
                    "title": row.title or row.reference_number or f"Assessment #{row.id}",
                    "type": "training",
                    "date": _iso_date(when),
                    "status": _status_for(when, status_val, today=today),
                    "priority": "medium",
                    "owner": None,
                    "source_module": "assessment",
                    "source_id": str(row.id),
                    "href": f"/workforce/assessments/{row.id}/execute",
                    "description": row.location,
                }
            )
        return out

    async def _load_inductions(self, start_dt: datetime, end_dt: datetime, today: date) -> list[dict[str, Any]]:
        from src.domain.models.induction import InductionRun

        stmt = select(InductionRun).where(
            InductionRun.scheduled_date.is_not(None),
            InductionRun.scheduled_date >= start_dt,
            InductionRun.scheduled_date <= end_dt,
        )
        if self.tenant_id is not None and hasattr(InductionRun, "tenant_id"):
            stmt = stmt.where(or_(InductionRun.tenant_id == self.tenant_id, InductionRun.tenant_id.is_(None)))
        result = await self.db.execute(stmt.limit(300))
        rows = list(result.scalars().all())
        out: list[dict[str, Any]] = []
        for row in rows:
            when = row.scheduled_date
            if when is None:
                continue
            status_val = row.status.value if hasattr(row.status, "value") else str(row.status)
            ref = getattr(row, "reference_number", None) or f"Induction #{row.id}"
            out.append(
                {
                    "id": f"induction:{row.id}",
                    "title": getattr(row, "title", None) or ref,
                    "type": "training",
                    "date": _iso_date(when),
                    "status": _status_for(when, status_val, today=today),
                    "priority": "medium",
                    "owner": None,
                    "source_module": "induction",
                    "source_id": str(row.id),
                    "href": f"/workforce/training/{row.id}/execute",
                    "description": None,
                }
            )
        return out
