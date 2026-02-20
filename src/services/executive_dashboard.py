"""Executive KPI Dashboard Service.

Provides real-time aggregation of key performance indicators
across all modules for executive-level visibility.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.complaint import Complaint, ComplaintStatus
from src.domain.models.incident import Incident, IncidentSeverity, IncidentStatus
from src.domain.models.kri import KeyRiskIndicator, KRIAlert, ThresholdStatus
from src.domain.models.near_miss import NearMiss
from src.domain.models.policy_acknowledgment import AcknowledgmentStatus, PolicyAcknowledgment
from src.domain.models.risk import Risk, RiskStatus
from src.domain.models.rta import RTA
from src.domain.models.workflow_rules import SLATracking

logger = logging.getLogger(__name__)


class ExecutiveDashboardService:
    """Service for generating executive KPI dashboards."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _safe_call(self, coro, default):
        """Run an async function, returning default on any DB error."""
        try:
            return await coro
        except Exception as e:
            logger.warning("Dashboard query failed: %s", e)
            return default

    async def get_full_dashboard(
        self,
        period_days: int = 30,
    ) -> Dict[str, Any]:
        """Get complete executive dashboard with all KPIs."""
        cutoff = datetime.utcnow() - timedelta(days=period_days)

        empty_summary = {"total_in_period": 0, "open": 0, "critical_high": 0}
        empty_risk = {
            "total_active": 0,
            "by_level": {},
            "high_critical": 0,
            "average_score": 0,
        }
        empty_kri = {
            "total_active": 0,
            "by_status": {"green": 0, "amber": 0, "red": 0, "not_measured": 0},
            "at_risk": 0,
            "pending_alerts": 0,
        }
        empty_compliance = {"total_assigned": 0, "completed": 0, "overdue": 0, "completion_rate": 100}
        empty_sla = {"total_tracked": 0, "met": 0, "breached": 0, "compliance_rate": 100}

        incident_summary = await self._safe_call(
            self._get_incident_summary(cutoff), {**empty_summary, "by_severity": {}, "high_severity": 0}
        )
        near_miss_summary = await self._safe_call(self._get_near_miss_summary(cutoff), empty_summary)
        complaint_summary = await self._safe_call(self._get_complaint_summary(cutoff), empty_summary)
        rta_summary = await self._safe_call(self._get_rta_summary(cutoff), empty_summary)
        risk_summary = await self._safe_call(self._get_risk_summary(), empty_risk)
        kri_summary = await self._safe_call(self._get_kri_summary(), empty_kri)
        compliance_summary = await self._safe_call(self._get_compliance_summary(), empty_compliance)
        sla_summary = await self._safe_call(self._get_sla_summary(), empty_sla)

        health_score = self._calculate_health_score(
            incident_summary,
            near_miss_summary,
            complaint_summary,
            risk_summary,
            kri_summary,
            compliance_summary,
            sla_summary,
        )

        trends = await self._safe_call(self._get_trends(period_days), {})
        alerts = await self._safe_call(self._get_active_alerts(), [])

        return {
            "generated_at": datetime.utcnow().isoformat(),
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
            "trends": trends,
            "alerts": alerts,
        }

    async def _get_incident_summary(self, cutoff: datetime) -> Dict[str, Any]:
        """Get incident summary statistics."""
        # Total in period
        total_result = await self.db.execute(select(func.count(Incident.id)).where(Incident.incident_date >= cutoff))
        total = total_result.scalar() or 0

        # By severity
        severity_counts = {}
        for severity in IncidentSeverity:
            count_result = await self.db.execute(
                select(func.count(Incident.id)).where(
                    and_(
                        Incident.incident_date >= cutoff,
                        Incident.severity == severity,
                    )
                )
            )
            severity_counts[severity.value] = count_result.scalar() or 0

        # Open incidents
        open_result = await self.db.execute(
            select(func.count(Incident.id)).where(
                Incident.status.in_(
                    [
                        IncidentStatus.REPORTED,
                        IncidentStatus.UNDER_INVESTIGATION,
                        IncidentStatus.PENDING_ACTIONS,
                        IncidentStatus.ACTIONS_IN_PROGRESS,
                    ]
                )
            )
        )
        open_count = open_result.scalar() or 0

        # SIF/pSIF count
        sif_result = await self.db.execute(
            select(func.count(Incident.id)).where(
                and_(
                    Incident.incident_date >= cutoff,
                    Incident.is_sif == True,
                )
            )
        )
        sif_count = sif_result.scalar() or 0

        psif_result = await self.db.execute(
            select(func.count(Incident.id)).where(
                and_(
                    Incident.incident_date >= cutoff,
                    Incident.is_psif == True,
                )
            )
        )
        psif_count = psif_result.scalar() or 0

        return {
            "total_in_period": total,
            "open": open_count,
            "by_severity": severity_counts,
            "sif_count": sif_count,
            "psif_count": psif_count,
            "critical_high": severity_counts.get("critical", 0) + severity_counts.get("high", 0),
        }

    async def _get_near_miss_summary(self, cutoff: datetime) -> Dict[str, Any]:
        """Get near-miss summary statistics."""
        total_result = await self.db.execute(select(func.count(NearMiss.id)).where(NearMiss.created_at >= cutoff))
        total = total_result.scalar() or 0

        # Compare to previous period
        previous_cutoff = cutoff - timedelta(days=30)
        previous_result = await self.db.execute(
            select(func.count(NearMiss.id)).where(
                and_(
                    NearMiss.created_at >= previous_cutoff,
                    NearMiss.created_at < cutoff,
                )
            )
        )
        previous_total = previous_result.scalar() or 0

        # Trend
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
        """Get complaint summary statistics."""
        total_result = await self.db.execute(select(func.count(Complaint.id)).where(Complaint.created_at >= cutoff))
        total = total_result.scalar() or 0

        # Open complaints
        open_result = await self.db.execute(
            select(func.count(Complaint.id)).where(
                Complaint.status.in_(
                    [
                        ComplaintStatus.RECEIVED,
                        ComplaintStatus.ACKNOWLEDGED,
                        ComplaintStatus.UNDER_INVESTIGATION,
                        ComplaintStatus.PENDING_RESPONSE,
                    ]
                )
            )
        )
        open_count = open_result.scalar() or 0

        # Closed in period
        closed_result = await self.db.execute(
            select(func.count(Complaint.id)).where(
                and_(
                    Complaint.closed_at >= cutoff,
                    Complaint.status == ComplaintStatus.CLOSED,
                )
            )
        )
        closed_count = closed_result.scalar() or 0

        return {
            "total_in_period": total,
            "open": open_count,
            "closed_in_period": closed_count,
            "resolution_rate": round((closed_count / total * 100), 1) if total > 0 else 100,
        }

    async def _get_rta_summary(self, cutoff: datetime) -> Dict[str, Any]:
        """Get RTA summary statistics."""
        total_result = await self.db.execute(select(func.count(RTA.id)).where(RTA.created_at >= cutoff))
        total = total_result.scalar() or 0

        return {
            "total_in_period": total,
        }

    async def _get_risk_summary(self) -> Dict[str, Any]:
        """Get risk summary statistics."""
        # Total active risks
        total_result = await self.db.execute(select(func.count(Risk.id)).where(Risk.is_active == True))
        total = total_result.scalar() or 0

        # By risk level
        level_counts = {}
        for level in ["critical", "high", "medium", "low", "negligible"]:
            count_result = await self.db.execute(
                select(func.count(Risk.id)).where(
                    and_(
                        Risk.is_active == True,
                        Risk.risk_level == level,
                    )
                )
            )
            level_counts[level] = count_result.scalar() or 0

        # Average risk score
        avg_result = await self.db.execute(select(func.avg(Risk.risk_score)).where(Risk.is_active == True))
        avg_score = avg_result.scalar() or 0

        return {
            "total_active": total,
            "by_level": level_counts,
            "high_critical": level_counts.get("critical", 0) + level_counts.get("high", 0),
            "average_score": round(avg_score, 1),
        }

    async def _get_kri_summary(self) -> Dict[str, Any]:
        """Get KRI summary statistics."""
        result = await self.db.execute(select(KeyRiskIndicator).where(KeyRiskIndicator.is_active == True))
        kris = result.scalars().all()

        status_counts = {"green": 0, "amber": 0, "red": 0, "not_measured": 0}
        for kri in kris:
            if kri.current_status:
                status_counts[kri.current_status.value] += 1
            else:
                status_counts["not_measured"] += 1

        # Pending alerts
        alert_result = await self.db.execute(
            select(func.count(KRIAlert.id)).where(
                and_(
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
        total_result = await self.db.execute(select(func.count(PolicyAcknowledgment.id)))
        total = total_result.scalar() or 0

        completed_result = await self.db.execute(
            select(func.count(PolicyAcknowledgment.id)).where(
                PolicyAcknowledgment.status == AcknowledgmentStatus.COMPLETED
            )
        )
        completed = completed_result.scalar() or 0

        overdue_result = await self.db.execute(
            select(func.count(PolicyAcknowledgment.id)).where(
                PolicyAcknowledgment.status == AcknowledgmentStatus.OVERDUE
            )
        )
        overdue = overdue_result.scalar() or 0

        return {
            "total_assigned": total,
            "completed": completed,
            "overdue": overdue,
            "completion_rate": round((completed / total * 100), 1) if total > 0 else 100,
        }

    async def _get_sla_summary(self) -> Dict[str, Any]:
        """Get SLA performance summary."""
        total_result = await self.db.execute(select(func.count(SLATracking.id)))
        total = total_result.scalar() or 0

        met_result = await self.db.execute(select(func.count(SLATracking.id)).where(SLATracking.resolution_met == True))
        met = met_result.scalar() or 0

        breached_result = await self.db.execute(
            select(func.count(SLATracking.id)).where(SLATracking.is_breached == True)
        )
        breached = breached_result.scalar() or 0

        return {
            "total_tracked": total,
            "met": met,
            "breached": breached,
            "compliance_rate": round((met / total * 100), 1) if total > 0 else 100,
        }

    async def _get_trends(self, period_days: int) -> Dict[str, Any]:
        """Get trend data for charts."""
        # Weekly incident counts for the period
        weeks = period_days // 7
        incident_trend = []

        for i in range(weeks, 0, -1):
            week_end = datetime.utcnow() - timedelta(days=(i - 1) * 7)
            week_start = week_end - timedelta(days=7)

            result = await self.db.execute(
                select(func.count(Incident.id)).where(
                    and_(
                        Incident.incident_date >= week_start,
                        Incident.incident_date < week_end,
                    )
                )
            )
            count = result.scalar() or 0
            incident_trend.append(
                {
                    "week_start": week_start.strftime("%Y-%m-%d"),
                    "count": count,
                }
            )

        return {
            "incidents_weekly": incident_trend,
        }

    async def _get_active_alerts(self) -> List[Dict[str, Any]]:
        """Get active alerts that need attention."""
        alerts = []

        # KRI alerts
        kri_alerts = await self.db.execute(
            select(KRIAlert)
            .where(
                and_(
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

        # Overdue policy acknowledgments
        overdue_result = await self.db.execute(
            select(func.count(PolicyAcknowledgment.id)).where(
                PolicyAcknowledgment.status == AcknowledgmentStatus.OVERDUE
            )
        )
        overdue_count = overdue_result.scalar() or 0
        if overdue_count > 0:
            alerts.append(
                {
                    "type": "policy_overdue",
                    "severity": "amber",
                    "title": f"{overdue_count} overdue policy acknowledgments",
                    "triggered_at": datetime.utcnow().isoformat(),
                }
            )

        # High/Critical open incidents
        critical_result = await self.db.execute(
            select(func.count(Incident.id)).where(
                and_(
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
                    "triggered_at": datetime.utcnow().isoformat(),
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
        """Calculate overall organizational health score (0-100)."""
        scores = []
        weights = []

        # Incident score (lower is better for critical/high)
        incident_score = 100
        if incidents["critical_high"] > 0:
            incident_score = max(0, 100 - (incidents["critical_high"] * 10))
        scores.append(incident_score)
        weights.append(20)

        # Near-miss reporting (higher is better - indicates good safety culture)
        nm_score = min(100, near_misses["total_in_period"] * 5)  # Encourage reporting
        scores.append(nm_score)
        weights.append(10)

        # Risk score
        risk_score = 100
        high_risk_ratio = risks["high_critical"] / max(1, risks["total_active"])
        risk_score = max(0, 100 - (high_risk_ratio * 100))
        scores.append(risk_score)
        weights.append(20)

        # KRI score
        kri_score = 100
        if kris["total_active"] > 0:
            green_ratio = kris["by_status"]["green"] / kris["total_active"]
            kri_score = green_ratio * 100
        scores.append(kri_score)
        weights.append(20)

        # Compliance score
        compliance_score = compliance["completion_rate"]
        scores.append(compliance_score)
        weights.append(15)

        # SLA score
        sla_score = sla["compliance_rate"]
        scores.append(sla_score)
        weights.append(15)

        # Weighted average
        total_weight = sum(weights)
        weighted_score = sum(s * w for s, w in zip(scores, weights)) / total_weight

        # Determine status
        if weighted_score >= 80:
            status = "healthy"
            color = "green"
        elif weighted_score >= 60:
            status = "attention_needed"
            color = "amber"
        else:
            status = "at_risk"
            color = "red"

        return {
            "score": round(weighted_score, 1),
            "status": status,
            "color": color,
            "components": {
                "incidents": round(incident_score, 1),
                "near_miss_culture": round(nm_score, 1),
                "risk_management": round(risk_score, 1),
                "kri_performance": round(kri_score, 1),
                "compliance": round(compliance_score, 1),
                "sla_performance": round(sla_score, 1),
            },
        }
