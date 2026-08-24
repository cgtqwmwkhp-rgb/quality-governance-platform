"""Executive KPI Dashboard Service (canonical domain implementation).

Provides real-time aggregation of key performance indicators
across all modules for executive-level visibility.

Callers may import via ``src.domain.services.executive_dashboard`` or the
compatibility re-export at ``src.services.executive_dashboard``.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Awaitable, Callable, Dict, List, Optional, cast

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.metrics import percentage_or_none
from src.domain.models.asset import Asset, AssetStatus, AssetType
from src.domain.models.audit import AuditRun, AuditStatus
from src.domain.models.complaint import Complaint, ComplaintStatus, FeedbackKind, is_complaint_kind
from src.domain.models.incident import Incident, IncidentSeverity, IncidentStatus
from src.domain.models.kri import KeyRiskIndicator, KRIAlert
from src.domain.models.near_miss import NearMiss
from src.domain.models.policy_acknowledgment import AcknowledgmentStatus, PolicyAcknowledgment
from src.domain.models.risk_register import EnterpriseRisk
from src.domain.models.rta import RTA, RTAStatus
from src.domain.models.training_matrix import TrainingMatrixCell, TrainingMatrixImport
from src.domain.models.workflow_rules import SLATracking
from src.domain.services.asset_health_analytics_service import AssetHealthRow, aggregate_asset_health_kpis
from src.domain.services.hs_kpi_service import compliment_to_complaint_ratio
from src.domain.services.risk_service import register_active_clause, register_visibility_clause
from src.domain.services.session_savepoint import SavepointScope, read_savepoint

logger = logging.getLogger(__name__)

_EMPTY_INCIDENT_SUMMARY: Dict[str, Any] = {
    "total_in_period": 0,
    "open": 0,
    "by_severity": {},
    "sif_count": 0,
    "psif_count": 0,
    "critical_high": 0,
    # None (not 0): a failed summary must not look like an empty register (PX-226).
    "register_total": None,
    "register_open": None,
    "register_closed": None,
    "avg_resolution_days": None,
}
_EMPTY_NEAR_MISS_SUMMARY: Dict[str, Any] = {
    "total_in_period": 0,
    "previous_period": 0,
    "trend_percent": 0.0,
    "reporting_rate": "stable",
}
_EMPTY_COMPLAINT_SUMMARY: Dict[str, Any] = {
    "total_in_period": 0,
    "open": 0,
    "closed_in_period": 0,
    "resolution_rate": None,
    "register_total": None,
    "register_open": None,
    "register_closed": None,
    "received_in_period_closed": None,
    "avg_resolution_days": None,
    "compliments_in_period": 0,
    "compliment_to_complaint_ratio": None,
}
_EMPTY_RTA_SUMMARY: Dict[str, Any] = {
    "total_in_period": 0,
    "total": 0,
    "open": 0,
    "closed": 0,
}
_EMPTY_RISK_SUMMARY: Dict[str, Any] = {
    # None (not 0): a failed summary must not look like an empty register (PX-226).
    "register_total": None,
    "total_active": 0,
    "by_level": {},
    "high_critical": 0,
    "average_score": 0.0,
}
_EMPTY_KRI_SUMMARY: Dict[str, Any] = {
    "total_active": 0,
    "by_status": {"green": 0, "amber": 0, "red": 0, "not_measured": 0},
    "at_risk": 0,
    "pending_alerts": 0,
}
_EMPTY_COMPLIANCE_SUMMARY: Dict[str, Any] = {
    "total_assigned": 0,
    "completed": 0,
    "overdue": 0,
    "completion_rate": None,
}
_EMPTY_SLA_SUMMARY: Dict[str, Any] = {
    "total_tracked": 0,
    "met": 0,
    "breached": 0,
    "compliance_rate": None,
}
_EMPTY_TRAINING_SUMMARY: Dict[str, Any] = {
    # None (not 0) throughout: an unread matrix must not report a compliant
    # workforce, and it must not report a wholly non-compliant one either. The
    # counts are as unmeasured as the rate is, so none of them may be a number
    # (C-7). ``measured_cells`` of None is what tells a caller the difference
    # between this and a matrix that really holds no scored cells.
    "measured_cells": None,
    "compliant_cells": None,
    "completion_rate": None,
    "expiring_soon": None,
    "overdue": None,
}
_EMPTY_AUDIT_SUMMARY: Dict[str, Any] = {
    "totals": 0,
    "completed": 0,
    "in_progress": 0,
    "avg_score": None,
    "pass_rate": None,
    "essential_compliance_pct": None,
    "incomplete_critical_count": 0,
}
# Days ahead that counts as "expiring soon" for the training headline. Matches the
# 30-day horizon the training matrix UI uses for its amber band.
TRAINING_EXPIRY_HORIZON_DAYS = 30


def training_cell_is_scored(passed_on: Optional[date], expires_on: Optional[date]) -> bool:
    """Whether a matrix cell carries enough information to be scored at all.

    The denominator for every training compliance figure. A cell with neither a
    pass date nor an expiry is an unpopulated requirement, not a failure, so
    counting it as non-compliant would report a half-filled matrix as poor
    training rather than as an incomplete matrix.
    """
    return passed_on is not None or expires_on is not None


def training_cell_is_compliant(passed_on: Optional[date], expires_on: Optional[date], as_of: date) -> bool:
    """Whether a scored cell is compliant at ``as_of``.

    Passed, and either never expires or has not expired yet. ``expires_on ==
    as_of`` is still compliant: the certificate is valid for the whole of its
    expiry day.
    """
    if passed_on is None:
        return False
    return expires_on is None or expires_on >= as_of


_TREND_SERIES = (
    "incidents_weekly",
    "complaints_weekly",
    "near_misses_weekly",
    "audits_weekly",
    "training_compliance_weekly",
    "tool_compliance_weekly",
)
_EMPTY_TRENDS: Dict[str, Any] = {
    **{name: [] for name in _TREND_SERIES},
    # A wholesale failure is six failures, not six empty weeks (PX-193).
    "unavailable": list(_TREND_SERIES),
}


def _assert_no_pending_writes(db: Any) -> None:
    """Refuse construction when the shared session already holds uncommitted writes.

    The service recovers from a failed sub-query so later tiles can still run.
    Since C-8 that recovery is a savepoint unwind, which leaves writes staged
    before the savepoint alone — but it still falls back to a full
    ``Session.rollback()`` when the session cannot open a savepoint or the unwind
    itself fails, and that would silently discard them. The fence stays: this is a
    read-only path, so there is nothing here worth betting on the fallback never
    firing.
    """
    pending = [
        *(getattr(db, "new", None) or ()),
        *(getattr(db, "dirty", None) or ()),
        *(getattr(db, "deleted", None) or ()),
    ]
    if pending:
        raise RuntimeError(
            "ExecutiveDashboardService rolls its session back when a sub-query fails "
            f"(_recover_session), which would silently discard {len(pending)} pending "
            "write(s) already on this session. Construct it on a read-only path."
        )


class ExecutiveDashboardService:
    """Service for generating executive KPI dashboards."""

    def __init__(self, db: AsyncSession, *, tenant_id: Optional[int] = None):
        _assert_no_pending_writes(db)
        self.db = db
        self.tenant_id = tenant_id

    def _tenant_filter(self, model: Any) -> Any:
        """Return tenant scope, excluding soft-deleted rows when the model has them.

        Register lists filter ``deleted_at IS NULL``; dashboard aggregates must use
        the same population or register_total / open counts drift (PX-177).
        """
        clauses: list[Any] = []
        if self.tenant_id is not None:
            clauses.append(model.tenant_id == self.tenant_id)
        if hasattr(model, "deleted_at"):
            clauses.append(model.deleted_at.is_(None))
        if not clauses:
            return True  # noqa: E712  — SQLAlchemy literal
        if len(clauses) == 1:
            return clauses[0]
        return and_(*clauses)

    async def _recover_session(self, scope: Optional[SavepointScope] = None) -> None:
        """Put the transaction back into a usable state after a failed sub-query.

        PostgreSQL aborts the whole transaction on the first failing statement
        and refuses everything after it until the transaction ends. Swallowing
        the error without unwinding therefore turns one broken aggregate into
        a dashboard of zeros — every later tile reports "query failed" and falls
        back to its empty default, which is indistinguishable from real data.

        The unwind is a savepoint, not ``Session.rollback()`` (C-8). A full
        rollback ends the request's whole transaction and expires every instance
        in its identity map, including the ``current_user`` this service shares a
        session with; reading an attribute off it afterwards emits a lazy refresh,
        which over an async session raises MissingGreenlet. That is a 500 this
        repository has already paid for — ``analytics.py`` still carries a
        defensive ``tenant_id`` read from when it happened. Unwinding to the
        savepoint ``_safe_call`` opened costs the failed aggregate and nothing
        else. Same recovery as ``actions.py`` ``_read_savepoint`` (C-53).

        The rollback survives as the fallback, for the two shapes where no
        savepoint stands between the failure and the rest of the request: a
        session that cannot open one, and an unwind that failed. Leaving those
        unrecovered would trade a rare expired identity map for the guaranteed
        page of zeros #1388 removed. ``_assert_no_pending_writes`` is what keeps
        the fallback safe to take.
        """
        if scope is not None and scope.recovered:
            return
        try:
            await self.db.rollback()
        except Exception:  # pragma: no cover - the session is already unusable
            logger.warning("Dashboard session rollback failed", exc_info=True)

    async def _safe_call(self, coro, default, *, name: Optional[str] = None, unavailable: Optional[List[str]] = None):
        """Run an async function inside a savepoint, returning default on any DB error.

        The savepoint has to be opened before the statement that fails, so it is
        taken here rather than inside ``_recover_session``: recovery cannot roll
        back to a savepoint nobody took.

        When ``name`` and ``unavailable`` are given, a failure records the
        aggregate's name so the caller can tell "this could not be measured" from
        "this measured nothing". Without that record the two are the same answer,
        because most of the empty defaults below are legitimate values: an
        ``audits`` default of ``totals: 0`` is exactly what a tenant with no audit
        runs produces (C-7).

        The alternative — making every count in every empty default ``None`` — was
        rejected because it changes ``ExecutiveDashboardResponse``'s published
        field types from ``integer`` to a nullable union, which the OpenAPI
        compatibility gate classifies as a breaking change for existing clients.
        A name on a list is additive and says the same thing.
        """
        scope: Optional[SavepointScope] = None
        try:
            async with read_savepoint(self.db) as scope:
                return await coro
        except Exception as e:
            logger.warning("Dashboard query failed: %s", e)
            await self._recover_session(scope)
            if name is not None and unavailable is not None:
                unavailable.append(name)
            return default
        finally:
            # Opening the savepoint can itself raise, in which case ``coro`` was
            # never awaited and would otherwise warn on collection. Closing a
            # coroutine that already ran is a no-op.
            close = getattr(coro, "close", None)
            if close is not None:
                close()

    async def _avg_resolution_days(self, start_col: Any, end_col: Any, tf: Any) -> Optional[float]:
        """Mean days from event to closure over closed records with both timestamps.

        Averaged in Python: date subtraction is dialect-specific and this path
        must stay correct on SQLite and Postgres. Returns None when no usable
        closed pair exists (PX-225).
        """
        rows = (
            await self.db.execute(
                select(start_col, end_col).where(and_(tf, start_col.is_not(None), end_col.is_not(None)))
            )
        ).all()
        spans = [(end - start).total_seconds() / 86400 for start, end in rows if end >= start]
        return round(sum(spans) / len(spans), 1) if spans else None

    async def get_full_dashboard(
        self,
        period_days: int = 30,
        *,
        user: Any = None,
    ) -> Dict[str, Any]:
        """Get complete executive dashboard with all KPIs."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=period_days)

        # Names of the aggregates whose queries failed, so a consumer can report
        # "unavailable" instead of publishing an empty default as a measurement.
        # Same idea as ``_EMPTY_TRENDS["unavailable"]`` (PX-193), one level up.
        unavailable: List[str] = []

        incident_summary = await self._safe_call(
            self._get_incident_summary(cutoff),
            dict(_EMPTY_INCIDENT_SUMMARY),
            name="incidents",
            unavailable=unavailable,
        )
        near_miss_summary = await self._safe_call(
            self._get_near_miss_summary(cutoff),
            dict(_EMPTY_NEAR_MISS_SUMMARY),
            name="near_misses",
            unavailable=unavailable,
        )
        complaint_summary = await self._safe_call(
            self._get_complaint_summary(cutoff),
            dict(_EMPTY_COMPLAINT_SUMMARY),
            name="complaints",
            unavailable=unavailable,
        )
        rta_summary = await self._safe_call(
            self._get_rta_summary(cutoff), dict(_EMPTY_RTA_SUMMARY), name="rtas", unavailable=unavailable
        )
        risk_summary = await self._safe_call(
            self._get_risk_summary(), dict(_EMPTY_RISK_SUMMARY), name="risks", unavailable=unavailable
        )
        kri_summary = await self._safe_call(
            self._get_kri_summary(), dict(_EMPTY_KRI_SUMMARY), name="kris", unavailable=unavailable
        )
        compliance_summary = await self._safe_call(
            self._get_compliance_summary(),
            dict(_EMPTY_COMPLIANCE_SUMMARY),
            name="compliance",
            unavailable=unavailable,
        )
        sla_summary = await self._safe_call(
            self._get_sla_summary(), dict(_EMPTY_SLA_SUMMARY), name="sla_performance", unavailable=unavailable
        )
        audit_summary = await self._safe_call(
            self._get_audit_summary(period_days),
            dict(_EMPTY_AUDIT_SUMMARY),
            name="audits",
            unavailable=unavailable,
        )
        training_summary = await self._safe_call(
            self._get_training_summary(), dict(_EMPTY_TRAINING_SUMMARY), name="training", unavailable=unavailable
        )

        health_score = self._calculate_health_score(
            incident_summary,
            near_miss_summary,
            complaint_summary,
            risk_summary,
            kri_summary,
            compliance_summary,
            sla_summary,
        )

        trends = await self._safe_call(
            self._get_trends(period_days), dict(_EMPTY_TRENDS), name="trends", unavailable=unavailable
        )
        alerts = await self._safe_call(self._get_active_alerts(), [], name="alerts", unavailable=unavailable)
        safety_insights = await self._safe_call(
            self._get_safety_insights_summary(), {}, name="safety_insights", unavailable=unavailable
        )

        # None when closed to this caller; unavailable-shaped payload when open but unread.
        compliance_schedule = None
        if self._compliance_schedule_open_to(user):
            compliance_schedule = await self._safe_call(
                self._get_compliance_schedule_summary(),
                {
                    "available": False,
                    "total_active": None,
                    "current": None,
                    "due_soon": None,
                    "overdue": None,
                    "href": "/compliance-schedule",
                },
                name="compliance_schedule",
                unavailable=unavailable,
            )

        # Ensure all sparkline series keys exist even if a partial trends dict is returned.
        trends = {**dict(_EMPTY_TRENDS), **trends}

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period_days": period_days,
            "health_score": health_score,
            "incidents": incident_summary,
            "near_misses": near_miss_summary,
            "complaints": complaint_summary,
            "rtas": rta_summary,
            "risks": risk_summary,
            "kris": kri_summary,
            "compliance": compliance_summary,
            "sla_performance": sla_summary,
            "audits": audit_summary,
            "training": training_summary,
            "trends": trends,
            "alerts": alerts,
            "safety_insights": safety_insights,
            "compliance_schedule": compliance_schedule,
            "unavailable": unavailable,
        }

    async def _get_safety_insights_summary(self) -> Dict[str, Any]:
        """Latest Safety Insights Analyst themes + NM:I for executive surface."""
        if self.tenant_id is None:
            return {"available": False, "top_themes": [], "ratios": None}
        from src.domain.services.safety_insights_analyst import SafetyInsightsAnalystService

        service = SafetyInsightsAnalystService(self.db)
        run = await service.latest_succeeded(self.tenant_id)
        if run is None:
            return {"available": False, "top_themes": [], "ratios": None, "href": "/analytics/safety-insights"}
        payload = await service.serialize_run(run, include_children=True)
        return {
            "available": True,
            "run_id": run.id,
            "completed_at": payload.get("completed_at"),
            "top_themes": [
                {
                    "id": t.get("id"),
                    "label": t.get("label"),
                    "case_count": t.get("case_count"),
                    "velocity": t.get("velocity"),
                }
                for t in (payload.get("micro_themes") or [])[:3]
            ],
            "ratios": (payload.get("ratios") or {}).get("corpus"),
            "href": "/analytics/safety-insights",
        }

    @staticmethod
    def _compliance_schedule_open_to(user: Any) -> bool:
        """Whether the Compliance Schedule tile may appear for this caller.

        Mirrors search / meta features: deployment opener, subtract-only kill
        switch (last known — no I/O on the shared dashboard session), and
        ``compliance_schedule:read``. Closed means the field stays ``None`` so
        clients omit the tile rather than publishing zeros.
        """
        from src.core.config import settings
        from src.domain.services.compliance_schedule_kill_switch import compliance_schedule_kill_switch_last_known

        if user is None:
            return False
        if not settings.compliance_schedule_enabled:
            return False
        if compliance_schedule_kill_switch_last_known():
            return False
        has_permission = getattr(user, "has_permission", None)
        if not callable(has_permission):
            return False
        return bool(has_permission("compliance_schedule:read"))

    async def _get_compliance_schedule_summary(self) -> Dict[str, Any]:
        """Reuse ComplianceScheduleService.get_stats — same counts as GET /stats."""
        if self.tenant_id is None:
            return {
                "available": False,
                "total_active": None,
                "current": None,
                "due_soon": None,
                "overdue": None,
                "href": "/compliance-schedule",
            }
        from src.domain.services.compliance_schedule_service import ComplianceScheduleService

        stats = await ComplianceScheduleService(self.db).get_stats(tenant_id=self.tenant_id)
        return {
            "available": True,
            "total_active": stats["total_active"],
            "current": stats["current"],
            "due_soon": stats["due_soon"],
            "overdue": stats["overdue"],
            "href": "/compliance-schedule",
        }

    async def _get_incident_summary(self, cutoff: datetime) -> Dict[str, Any]:
        """Get incident summary statistics."""
        tf = self._tenant_filter(Incident)

        total_result = await self.db.execute(
            select(func.count(Incident.id)).where(and_(tf, Incident.incident_date >= cutoff))
        )
        total = total_result.scalar() or 0

        severity_counts = {}
        for severity in IncidentSeverity:
            count_result = await self.db.execute(
                select(func.count(Incident.id)).where(
                    and_(
                        tf,
                        Incident.incident_date >= cutoff,
                        Incident.severity == severity,
                    )
                )
            )
            severity_counts[severity.value] = count_result.scalar() or 0

        open_result = await self.db.execute(
            select(func.count(Incident.id)).where(
                and_(
                    tf,
                    Incident.status.in_(
                        [
                            IncidentStatus.REPORTED,
                            IncidentStatus.UNDER_INVESTIGATION,
                            IncidentStatus.PENDING_ACTIONS,
                            IncidentStatus.ACTIONS_IN_PROGRESS,
                        ]
                    ),
                )
            )
        )
        open_count = open_result.scalar() or 0

        sif_result = await self.db.execute(
            select(func.count(Incident.id)).where(
                and_(
                    tf,
                    Incident.incident_date >= cutoff,
                    Incident.is_sif == True,
                )
            )
        )
        sif_count = sif_result.scalar() or 0

        psif_result = await self.db.execute(
            select(func.count(Incident.id)).where(
                and_(
                    tf,
                    Incident.incident_date >= cutoff,
                    Incident.is_psif == True,
                )
            )
        )
        psif_count = psif_result.scalar() or 0

        register_total = (await self.db.execute(select(func.count(Incident.id)).where(tf))).scalar() or 0
        register_closed = (
            await self.db.execute(
                select(func.count(Incident.id)).where(and_(tf, Incident.status == IncidentStatus.CLOSED))
            )
        ).scalar() or 0
        avg_resolution_days = await self._avg_resolution_days(
            Incident.incident_date, Incident.closed_at, and_(tf, Incident.status == IncidentStatus.CLOSED)
        )

        return {
            "total_in_period": total,
            "open": open_count,
            "by_severity": severity_counts,
            "sif_count": sif_count,
            "psif_count": psif_count,
            "critical_high": severity_counts.get("critical", 0) + severity_counts.get("high", 0),
            # Register-scoped triple that reconciles exactly (PX-226). `open` above is
            # the narrower "actively worked" subset and is left for existing callers.
            "register_total": register_total,
            "register_closed": register_closed,
            "register_open": max(0, register_total - register_closed),
            "avg_resolution_days": avg_resolution_days,
        }

    async def _get_near_miss_summary(self, cutoff: datetime) -> Dict[str, Any]:
        """Get near-miss summary statistics.

        Pulse totals use event_date (coalesced to created_at) so the 7-day
        headline matches near_misses_weekly sparklines.
        """
        tf = self._tenant_filter(NearMiss)
        nm_when = func.coalesce(NearMiss.event_date, NearMiss.created_at)

        total_result = await self.db.execute(select(func.count(NearMiss.id)).where(and_(tf, nm_when >= cutoff)))
        total = total_result.scalar() or 0

        previous_cutoff = cutoff - timedelta(days=30)
        previous_result = await self.db.execute(
            select(func.count(NearMiss.id)).where(
                and_(
                    tf,
                    nm_when >= previous_cutoff,
                    nm_when < cutoff,
                )
            )
        )
        previous_total = previous_result.scalar() or 0

        if previous_total > 0:
            trend_percent = ((total - previous_total) / previous_total) * 100
        else:
            trend_percent = 100 if total > 0 else 0

        return {
            "total_in_period": total,
            "previous_period": previous_total,
            "trend_percent": round(trend_percent, 1),
            "reporting_rate": "improving" if total > previous_total else "declining",
        }

    async def _get_complaint_summary(self, cutoff: datetime) -> Dict[str, Any]:
        """Get complaint summary statistics.

        Pulse totals use received_date (coalesced to created_at) so the 7-day
        headline matches complaints_weekly sparklines.
        """
        tf = and_(self._tenant_filter(Complaint), is_complaint_kind())
        complaint_when = func.coalesce(Complaint.received_date, Complaint.created_at)

        total_result = await self.db.execute(select(func.count(Complaint.id)).where(and_(tf, complaint_when >= cutoff)))
        total = total_result.scalar() or 0

        open_result = await self.db.execute(
            select(func.count(Complaint.id)).where(
                and_(
                    tf,
                    Complaint.status.in_(
                        [
                            ComplaintStatus.RECEIVED,
                            ComplaintStatus.ACKNOWLEDGED,
                            ComplaintStatus.UNDER_INVESTIGATION,
                            ComplaintStatus.PENDING_RESPONSE,
                        ]
                    ),
                )
            )
        )
        open_count = open_result.scalar() or 0

        closed_result = await self.db.execute(
            select(func.count(Complaint.id)).where(
                and_(
                    tf,
                    Complaint.closed_at >= cutoff,
                    Complaint.status == ComplaintStatus.CLOSED,
                )
            )
        )
        closed_count = closed_result.scalar() or 0

        register_total = (await self.db.execute(select(func.count(Complaint.id)).where(tf))).scalar() or 0
        register_closed = (
            await self.db.execute(
                select(func.count(Complaint.id)).where(and_(tf, Complaint.status == ComplaintStatus.CLOSED))
            )
        ).scalar() or 0
        received_in_period_closed = (
            await self.db.execute(
                select(func.count(Complaint.id)).where(
                    and_(
                        tf,
                        complaint_when >= cutoff,
                        Complaint.status == ComplaintStatus.CLOSED,
                    )
                )
            )
        ).scalar() or 0
        avg_resolution_days = await self._avg_resolution_days(
            complaint_when, Complaint.closed_at, and_(tf, Complaint.status == ComplaintStatus.CLOSED)
        )

        compliment_tf = and_(self._tenant_filter(Complaint), Complaint.feedback_kind == FeedbackKind.COMPLIMENT)
        compliments_in_period = (
            await self.db.execute(select(func.count(Complaint.id)).where(and_(compliment_tf, complaint_when >= cutoff)))
        ).scalar() or 0

        return {
            "total_in_period": total,
            "open": open_count,
            "closed_in_period": closed_count,
            # Same cohort top and bottom (PX-226). The old numerator counted complaints
            # closed in the window regardless of when received, so the rate could exceed 100%.
            "resolution_rate": percentage_or_none(received_in_period_closed, total, digits=1),
            "register_total": register_total,
            "register_closed": register_closed,
            "register_open": max(0, register_total - register_closed),
            "received_in_period_closed": received_in_period_closed,
            "avg_resolution_days": avg_resolution_days,
            "compliments_in_period": int(compliments_in_period),
            "compliment_to_complaint_ratio": compliment_to_complaint_ratio(int(compliments_in_period), int(total)),
        }

    async def _get_rta_summary(self, cutoff: datetime) -> Dict[str, Any]:
        """Get RTA summary statistics.

        `total_in_period` answers "how many were reported in the window"; `total`,
        `open` and `closed` answer "what does the register hold right now". They are
        different populations, so both are returned explicitly and named for what they
        are. Callers must not mix them: `open` is drawn from the register, and pairing
        it with the windowed total is what produced Open 32 / Total 31 (PX-223).
        """
        tf = self._tenant_filter(RTA)
        total_in_period_result = await self.db.execute(
            select(func.count(RTA.id)).where(and_(tf, RTA.created_at >= cutoff))
        )
        total_in_period = total_in_period_result.scalar() or 0

        register_total_result = await self.db.execute(select(func.count(RTA.id)).where(tf))
        register_total = register_total_result.scalar() or 0

        closed_result = await self.db.execute(
            select(func.count(RTA.id)).where(and_(tf, RTA.status == RTAStatus.CLOSED))
        )
        closed = closed_result.scalar() or 0

        return {
            "total_in_period": total_in_period,
            "total": register_total,
            "open": register_total - closed,
            "closed": closed,
        }

    async def _get_risk_summary(self) -> Dict[str, Any]:
        """Get risk summary statistics from the Enterprise Risk Register.

        Reads ``EnterpriseRisk`` (``risks_v2``) — the store every risk-creating
        path in the platform writes to — using the same tenant and triage
        visibility predicates as ``GET /api/v1/risk-register/``. It previously
        counted the operational ``Risk`` table, which only ``POST /api/v1/risks/``
        ever writes, so the executive risk tile read an empty table while the
        register showed a full population (PX-178).

        ``register_total`` is the whole visible register and reconciles exactly
        with the register list total. ``total_active`` is the narrower
        not-closed subset that ``/risk-register/summary`` reports and that the
        health score consumes; the two are different populations on purpose and
        are named for what they are (PX-223).
        """
        tf = self._tenant_filter(EnterpriseRisk)
        vis = register_visibility_clause()

        register_total = (
            await self.db.execute(select(func.count(EnterpriseRisk.id)).where(and_(tf, vis)))
        ).scalar() or 0

        active = and_(tf, vis, register_active_clause())
        total = (await self.db.execute(select(func.count(EnterpriseRisk.id)).where(active))).scalar() or 0

        # Canonical 5x5 bands (RiskScoringEngine): low <=4, medium 5-9, high 10-16, critical >=17.
        # `negligible` is retained at 0 so the by_level key set stays stable for consumers.
        level_counts: Dict[str, int] = {"negligible": 0}
        for level, clause in (
            ("critical", EnterpriseRisk.residual_score >= 17),
            ("high", EnterpriseRisk.residual_score.between(10, 16)),
            ("medium", EnterpriseRisk.residual_score.between(5, 9)),
            ("low", EnterpriseRisk.residual_score <= 4),
        ):
            count_result = await self.db.execute(select(func.count(EnterpriseRisk.id)).where(and_(active, clause)))
            level_counts[level] = count_result.scalar() or 0

        avg_result = await self.db.execute(select(func.avg(EnterpriseRisk.residual_score)).where(active))
        avg_score = avg_result.scalar() or 0

        return {
            "register_total": register_total,
            "total_active": total,
            "by_level": level_counts,
            "high_critical": level_counts.get("critical", 0) + level_counts.get("high", 0),
            "average_score": round(float(avg_score), 1),
        }

    async def _get_kri_summary(self) -> Dict[str, Any]:
        """Get KRI summary statistics."""
        tf_kri = self._tenant_filter(KeyRiskIndicator)
        result = await self.db.execute(select(KeyRiskIndicator).where(and_(tf_kri, KeyRiskIndicator.is_active == True)))
        kris = result.scalars().all()

        status_counts = {"green": 0, "amber": 0, "red": 0, "not_measured": 0}
        for kri in kris:
            if kri.current_status:
                status_key = kri.current_status.value
                if status_key not in status_counts:
                    status_key = "not_measured"
                status_counts[status_key] += 1
            else:
                status_counts["not_measured"] += 1

        tf_alert = self._tenant_filter(KRIAlert)
        alert_result = await self.db.execute(
            select(func.count(KRIAlert.id)).where(
                and_(
                    tf_alert,
                    KRIAlert.is_acknowledged == False,
                    KRIAlert.is_resolved == False,
                )
            )
        )
        pending_alerts = alert_result.scalar() or 0

        return {
            "total_active": len(kris),
            "by_status": status_counts,
            "at_risk": status_counts["amber"] + status_counts["red"],
            "pending_alerts": pending_alerts,
        }

    async def _get_compliance_summary(self) -> Dict[str, Any]:
        """Get compliance/policy acknowledgment summary."""
        tf = self._tenant_filter(PolicyAcknowledgment)

        total_result = await self.db.execute(select(func.count(PolicyAcknowledgment.id)).where(tf))
        total = total_result.scalar() or 0

        completed_result = await self.db.execute(
            select(func.count(PolicyAcknowledgment.id)).where(
                and_(tf, PolicyAcknowledgment.status == AcknowledgmentStatus.COMPLETED)
            )
        )
        completed = completed_result.scalar() or 0

        overdue_result = await self.db.execute(
            select(func.count(PolicyAcknowledgment.id)).where(
                and_(tf, PolicyAcknowledgment.status == AcknowledgmentStatus.OVERDUE)
            )
        )
        overdue = overdue_result.scalar() or 0

        return {
            "total_assigned": total,
            "completed": completed,
            "overdue": overdue,
            "completion_rate": percentage_or_none(completed, total, digits=1),
        }

    async def _get_sla_summary(self) -> Dict[str, Any]:
        """Get SLA performance summary."""
        tf = self._tenant_filter(SLATracking)

        total_result = await self.db.execute(select(func.count(SLATracking.id)).where(tf))
        total = total_result.scalar() or 0

        met_result = await self.db.execute(
            select(func.count(SLATracking.id)).where(and_(tf, SLATracking.resolution_met == True))
        )
        met = met_result.scalar() or 0

        breached_result = await self.db.execute(
            select(func.count(SLATracking.id)).where(and_(tf, SLATracking.is_breached == True))
        )
        breached = breached_result.scalar() or 0

        return {
            "total_tracked": total,
            "met": met,
            "breached": breached,
            "compliance_rate": percentage_or_none(met, total, digits=1),
        }

    async def _get_audit_summary(self, period_days: int) -> Dict[str, Any]:
        """Live audit reporting-pack summary (essential compliance, pass rate, etc)."""
        if self.tenant_id is None:
            return dict(_EMPTY_AUDIT_SUMMARY)

        # Local import avoids a hard dependency for callers that only need the base
        # dashboard (audit_analytics_service imports several audit domain models).
        from src.domain.services.audit_analytics_service import AuditAnalyticsService

        stats = await AuditAnalyticsService(self.db).get_summary(self.tenant_id, days=period_days)
        return {
            "totals": stats["totals"],
            "completed": stats["completed"],
            "in_progress": stats["in_progress"],
            "avg_score": stats["avg_score"],
            "pass_rate": stats["pass_rate"],
            "essential_compliance_pct": stats["essential_compliance_pct"],
            "incomplete_critical_count": stats["incomplete_critical_count"],
        }

    async def _trend_series(
        self,
        name: str,
        unavailable: List[str],
        build: Callable[[], Awaitable[List[Dict[str, Any]]]],
    ) -> List[Dict[str, Any]]:
        """Run one trend builder; on failure record the series and return [].

        Savepoint-scoped for the same reason as ``_safe_call``: five more series
        run after this one and each is several statements (C-8).
        """
        scope: Optional[SavepointScope] = None
        try:
            async with read_savepoint(self.db) as scope:
                return await build()
        except Exception:
            logger.exception("%s trend failed", name)
            unavailable.append(name)
            await self._recover_session(scope)
            return []

    async def _trend_count_in_window(
        self,
        week_windows: List[tuple[datetime, datetime, str]],
        model: Any,
        date_col: Any,
        *extra,
    ) -> List[Dict[str, Any]]:
        tf = self._tenant_filter(model)
        out: List[Dict[str, Any]] = []
        for week_start, week_end, label in week_windows:
            result = await self.db.execute(
                select(func.count(model.id)).where(and_(tf, date_col >= week_start, date_col < week_end, *extra))
            )
            out.append({"week_start": label, "count": result.scalar() or 0})
        return out

    async def _trend_audits_weekly(self, week_windows: List[tuple[datetime, datetime, str]]) -> List[Dict[str, Any]]:
        audits_weekly: List[Dict[str, Any]] = []
        tf_audit = self._tenant_filter(AuditRun)
        for week_start, week_end, label in week_windows:
            result = await self.db.execute(
                select(func.avg(AuditRun.score_percentage)).where(
                    and_(
                        tf_audit,
                        AuditRun.status == AuditStatus.COMPLETED,
                        AuditRun.score_percentage.is_not(None),
                        AuditRun.completed_at >= week_start,
                        AuditRun.completed_at < week_end,
                    )
                )
            )
            avg = result.scalar()
            if avg is None:
                audits_weekly.append({"week_start": label, "count": 0, "value": None})
            else:
                pct = round(float(avg), 1)
                audits_weekly.append({"week_start": label, "count": int(pct), "value": pct})
        return audits_weekly

    async def _trend_tool_compliance_weekly(
        self, week_windows: List[tuple[datetime, datetime, str]]
    ) -> List[Dict[str, Any]]:
        tool_compliance_weekly: List[Dict[str, Any]] = []
        asset_q = select(AssetType.name, Asset.status, Asset.expiry_date, Asset.created_at)
        asset_q = asset_q.outerjoin(AssetType, Asset.asset_type_id == AssetType.id)
        if self.tenant_id is not None:
            asset_q = asset_q.where(or_(Asset.tenant_id == self.tenant_id, Asset.tenant_id.is_(None)))
        asset_result = await self.db.execute(asset_q)
        asset_rows_raw = [
            (
                asset_type,
                status.value if hasattr(status, "value") else str(status),
                expiry_date,
                created_at,
            )
            for asset_type, status, expiry_date, created_at in asset_result.all()
        ]
        for _ws, week_end, label in week_windows:
            rows_as_of = [
                AssetHealthRow(asset_type=at, status=st, expiry_date=exp)
                for at, st, exp, created_at in asset_rows_raw
                if created_at is None or created_at <= week_end
            ]
            summary_map = cast(Dict[str, Any], aggregate_asset_health_kpis(rows_as_of, as_of=week_end))
            bands = cast(Dict[str, Any], summary_map.get("expiry_bands") or {})
            by_status = cast(Dict[str, Any], summary_map.get("by_status") or {})
            in_service = int(summary_map.get("total") or 0) - int(bands.get("removed", 0) or 0)
            if in_service <= 0:
                pct = 100.0
            else:
                overdue = int(bands.get("overdue", 0) or 0)
                quarantined = int(by_status.get(AssetStatus.QUARANTINED.value, 0) or 0)
                pct = round(100.0 * (in_service - overdue - quarantined) / in_service, 1)
            tool_compliance_weekly.append({"week_start": label, "count": int(pct), "value": pct})
        return tool_compliance_weekly

    async def _load_scored_training_cells(self) -> List[TrainingMatrixCell]:
        """Scored cells of the tenant's most recent training matrix import.

        Shared by the headline summary and the weekly sparkline so the two cannot
        drift onto different denominators and contradict each other (C-7).
        """
        if self.tenant_id is None:
            return []
        latest_imp = await self.db.execute(
            select(TrainingMatrixImport.id)
            .where(TrainingMatrixImport.tenant_id == self.tenant_id)
            .order_by(TrainingMatrixImport.id.desc())
            .limit(1)
        )
        import_id = latest_imp.scalar_one_or_none()
        if import_id is None:
            return []
        cell_result = await self.db.execute(
            select(TrainingMatrixCell).where(
                and_(
                    TrainingMatrixCell.tenant_id == self.tenant_id,
                    TrainingMatrixCell.import_id == import_id,
                )
            )
        )
        return [c for c in cell_result.scalars().all() if training_cell_is_scored(c.passed_on, c.expires_on)]

    async def _get_training_summary(self) -> Dict[str, Any]:
        """Point-in-time training compliance for the tenant's latest matrix import.

        Returns the all-None shape when there is nothing to measure — no import,
        or an import with no scored cell. That is deliberately the same shape a
        failed query produces, because both are the same fact: we cannot say what
        training compliance is. Before this existed, ``/analytics/kpis`` served a
        hardcoded ``completion_rate`` of 0.0 whatever the matrix held (C-7).
        """
        scored = await self._load_scored_training_cells()
        if not scored:
            return dict(_EMPTY_TRAINING_SUMMARY)

        as_of = datetime.now(timezone.utc).date()
        horizon = as_of + timedelta(days=TRAINING_EXPIRY_HORIZON_DAYS)
        compliant = sum(1 for c in scored if training_cell_is_compliant(c.passed_on, c.expires_on, as_of))
        # Expired, not merely un-passed: an expiry in the past is a lapsed
        # certificate, which is a different piece of work from one never taken.
        overdue = sum(1 for c in scored if c.expires_on is not None and c.expires_on < as_of)
        expiring_soon = sum(1 for c in scored if c.expires_on is not None and as_of <= c.expires_on < horizon)
        return {
            "measured_cells": len(scored),
            "compliant_cells": compliant,
            "completion_rate": percentage_or_none(compliant, len(scored), digits=1),
            "expiring_soon": expiring_soon,
            "overdue": overdue,
        }

    async def _trend_training_compliance_weekly(
        self, week_windows: List[tuple[datetime, datetime, str]]
    ) -> List[Dict[str, Any]]:
        training_compliance_weekly: List[Dict[str, Any]] = []
        if self.tenant_id is None:
            return training_compliance_weekly
        scored = await self._load_scored_training_cells()
        for _ws, week_end, label in week_windows:
            as_of = week_end.date()
            if not scored:
                training_compliance_weekly.append({"week_start": label, "count": 0, "value": None})
                continue
            ok = sum(1 for cell in scored if training_cell_is_compliant(cell.passed_on, cell.expires_on, as_of))
            pct = round(100.0 * ok / len(scored), 1)
            training_compliance_weekly.append({"week_start": label, "count": int(pct), "value": pct})
        return training_compliance_weekly

    async def _get_trends(self, period_days: int) -> Dict[str, Any]:
        """Weekly series for pulse sparklines (counts + compliance/score %).

        Each series is isolated: one failing branch must not empty the others (PX-193).
        """
        weeks = max(period_days // 7, 1)
        now = datetime.now(timezone.utc)
        week_windows: List[tuple[datetime, datetime, str]] = []
        for i in range(weeks, 0, -1):
            week_end = now - timedelta(days=(i - 1) * 7)
            week_start = week_end - timedelta(days=7)
            week_windows.append((week_start, week_end, week_start.strftime("%Y-%m-%d")))

        unavailable: List[str] = []
        incidents_weekly = await self._trend_series(
            "incidents_weekly",
            unavailable,
            lambda: self._trend_count_in_window(week_windows, Incident, Incident.incident_date),
        )
        complaints_weekly = await self._trend_series(
            "complaints_weekly",
            unavailable,
            lambda: self._trend_count_in_window(
                week_windows,
                Complaint,
                func.coalesce(Complaint.received_date, Complaint.created_at),
                is_complaint_kind(),
            ),
        )
        near_misses_weekly = await self._trend_series(
            "near_misses_weekly",
            unavailable,
            lambda: self._trend_count_in_window(
                week_windows, NearMiss, func.coalesce(NearMiss.event_date, NearMiss.created_at)
            ),
        )
        audits_weekly = await self._trend_series(
            "audits_weekly", unavailable, lambda: self._trend_audits_weekly(week_windows)
        )
        tool_compliance_weekly = await self._trend_series(
            "tool_compliance_weekly",
            unavailable,
            lambda: self._trend_tool_compliance_weekly(week_windows),
        )
        training_compliance_weekly = await self._trend_series(
            "training_compliance_weekly",
            unavailable,
            lambda: self._trend_training_compliance_weekly(week_windows),
        )

        return {
            "incidents_weekly": incidents_weekly,
            "complaints_weekly": complaints_weekly,
            "near_misses_weekly": near_misses_weekly,
            "audits_weekly": audits_weekly,
            "training_compliance_weekly": training_compliance_weekly,
            "tool_compliance_weekly": tool_compliance_weekly,
            "unavailable": unavailable,
        }

    async def _get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active alerts that need attention."""
        alerts = []

        tf_alert = self._tenant_filter(KRIAlert)
        kri_alerts = await self.db.execute(
            select(KRIAlert)
            .where(
                and_(
                    tf_alert,
                    KRIAlert.is_acknowledged == False,
                    KRIAlert.is_resolved == False,
                )
            )
            .order_by(KRIAlert.triggered_at.desc())
            .limit(5)
        )
        for alert in kri_alerts.scalars().all():
            alerts.append(
                {
                    "type": "kri_threshold",
                    "severity": alert.severity.value,
                    "title": alert.title,
                    "triggered_at": alert.triggered_at.isoformat(),
                }
            )

        tf_pa = self._tenant_filter(PolicyAcknowledgment)
        overdue_result = await self.db.execute(
            select(func.count(PolicyAcknowledgment.id)).where(
                and_(tf_pa, PolicyAcknowledgment.status == AcknowledgmentStatus.OVERDUE)
            )
        )
        overdue_count = overdue_result.scalar() or 0
        if overdue_count > 0:
            alerts.append(
                {
                    "type": "policy_overdue",
                    "severity": "amber",
                    "title": f"{overdue_count} overdue policy acknowledgments",
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        tf_inc = self._tenant_filter(Incident)
        critical_result = await self.db.execute(
            select(func.count(Incident.id)).where(
                and_(
                    tf_inc,
                    Incident.status.in_(
                        [
                            IncidentStatus.REPORTED,
                            IncidentStatus.UNDER_INVESTIGATION,
                        ]
                    ),
                    Incident.severity.in_(
                        [
                            IncidentSeverity.CRITICAL,
                            IncidentSeverity.HIGH,
                        ]
                    ),
                )
            )
        )
        critical_count = critical_result.scalar() or 0
        if critical_count > 0:
            alerts.append(
                {
                    "type": "incident_critical",
                    "severity": "red",
                    "title": f"{critical_count} high/critical incidents require attention",
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                }
            )

        return sorted(alerts, key=lambda x: x["severity"], reverse=True)

    def _calculate_health_score(
        self,
        incidents: Dict,
        near_misses: Dict,
        complaints: Dict,
        risks: Dict,
        kris: Dict,
        compliance: Dict,
        sla: Dict,
    ) -> Dict[str, Any]:
        """Calculate overall organizational health score (0-100).

        Components with nothing to measure score ``None`` and are dropped from the
        weighted average rather than contributing a free 100 (PX-216). If no
        component was measurable the overall score is ``None``/``not_measured``;
        that branch is a fallback rather than a live path, because the two
        count-based components below always carry weight.
        """
        # Absolute counts, not ratios: zero critical incidents is genuinely 100,
        # and near-miss reporting culture is scored on volume reported. Both are
        # always measurable, so they stay non-nullable and always carry weight.
        incident_score: float = 100.0
        if incidents["critical_high"] > 0:
            incident_score = float(max(0, 100 - (incidents["critical_high"] * 10)))
        nm_score: float = float(min(100, near_misses["total_in_period"] * 5))

        # Ratio-based: an empty register is unmeasured, not risk-free.
        risk_score = percentage_or_none(
            max(0, risks["total_active"] - risks["high_critical"]),
            risks["total_active"],
        )
        kri_score = percentage_or_none(kris["by_status"]["green"], kris["total_active"])
        compliance_score = compliance["completion_rate"]
        sla_score = sla["compliance_rate"]

        components: Dict[str, Optional[float]] = {
            "incidents": incident_score,
            "near_miss_culture": nm_score,
            "risk_management": risk_score,
            "kri_performance": kri_score,
            "compliance": compliance_score,
            "sla_performance": sla_score,
        }
        weights = {
            "incidents": 20,
            "near_miss_culture": 10,
            "risk_management": 20,
            "kri_performance": 20,
            "compliance": 15,
            "sla_performance": 15,
        }

        measured = [(components[name], weights[name]) for name in weights if components[name] is not None]
        total_weight = sum(w for _, w in measured)
        weighted_score = sum(cast(float, s) * w for s, w in measured) / total_weight if total_weight else None

        if weighted_score is None:
            status, color = "not_measured", "grey"
        elif weighted_score >= 80:
            status, color = "healthy", "green"
        elif weighted_score >= 60:
            status, color = "attention_needed", "amber"
        else:
            status, color = "at_risk", "red"

        return {
            "score": round(weighted_score, 1) if weighted_score is not None else None,
            "status": status,
            "color": color,
            "components": {
                name: (round(value, 1) if value is not None else None) for name, value in components.items()
            },
        }
