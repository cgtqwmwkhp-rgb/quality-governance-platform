"""Risk Scoring Service.

Provides dynamic risk score recalculation, KRI tracking,
and automated alerts when thresholds are breached.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.incident import Incident, IncidentSeverity, IncidentStatus
from src.domain.models.kri import (
    KeyRiskIndicator,
    KRIAlert,
    KRICategory,
    KRIMeasurement,
    KRITrendDirection,
    RiskScoreHistory,
    ThresholdStatus,
)
from src.domain.models.near_miss import NearMiss
from src.domain.models.risk import Risk, RiskAssessment, RiskStatus

logger = logging.getLogger(__name__)


class RiskScoringService:
    """Service for dynamic risk score calculation and updates."""

    # Score adjustment factors
    SEVERITY_IMPACT = {
        IncidentSeverity.CRITICAL: 2,
        IncidentSeverity.HIGH: 1,
        IncidentSeverity.MEDIUM: 0,
        IncidentSeverity.LOW: 0,
        IncidentSeverity.NEGLIGIBLE: 0,
    }

    # Near miss velocity thresholds (count per month)
    NEAR_MISS_VELOCITY_HIGH = 10
    NEAR_MISS_VELOCITY_MEDIUM = 5

    def __init__(self, db: AsyncSession):
        self.db = db

    async def recalculate_risk_score_for_incident(
        self,
        incident_id: int,
        trigger_type: str = "incident",
    ) -> Optional[Dict[str, Any]]:
        """Recalculate linked risk scores when an incident occurs.

        Args:
            incident_id: ID of the incident
            trigger_type: What triggered this update

        Returns:
            Dict with updated risk scores
        """
        # Get the incident
        result = await self.db.execute(select(Incident).where(Incident.id == incident_id))
        incident = result.scalar_one_or_none()

        if not incident:
            return None

        # Get linked risks
        linked_risk_ids = []
        if getattr(incident, "linked_risk_ids", None):  # type: ignore[attr-defined]  # SA column  # TYPE-IGNORE: MYPY-OVERRIDE
            try:
                linked_risk_ids = [int(x.strip()) for x in str(incident.linked_risk_ids).split(",") if x.strip()]
            except ValueError:
                pass

        if not linked_risk_ids:
            # Try to find related risks by category/department
            result = await self.db.execute(
                select(Risk).where(
                    and_(
                        Risk.department == incident.department,  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                        Risk.is_active == True,  # noqa: E712  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                    )
                )
            )
            risks = result.scalars().all()
            linked_risk_ids = [r.id for r in risks]

        updated_risks = []

        for risk_id in linked_risk_ids:
            update_result = await self._update_risk_score(
                risk_id=risk_id,
                trigger_type=trigger_type,
                trigger_entity_type="incident",
                trigger_entity_id=incident_id,
                severity=incident.severity,
            )
            if update_result:
                updated_risks.append(update_result)

        return {
            "incident_id": incident_id,
            "risks_updated": len(updated_risks),
            "updates": updated_risks,
        }

    async def recalculate_risk_score_for_near_miss(
        self,
        near_miss_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Update risk scores when a near miss is reported.

        Near misses affect the "velocity" component of risk.
        """
        result = await self.db.execute(select(NearMiss).where(NearMiss.id == near_miss_id))
        near_miss = result.scalar_one_or_none()

        if not near_miss:
            return None

        # Get linked risks
        linked_risk_ids = []
        if getattr(near_miss, "linked_risk_ids", None):  # type: ignore[attr-defined]  # SA column  # TYPE-IGNORE: MYPY-OVERRIDE
            try:
                linked_risk_ids = [int(x.strip()) for x in str(near_miss.linked_risk_ids).split(",") if x.strip()]
            except ValueError:
                pass

        updated_risks = []

        for risk_id in linked_risk_ids:
            update_result = await self._update_risk_velocity(
                risk_id=risk_id,
                trigger_entity_type="near_miss",
                trigger_entity_id=near_miss_id,
            )
            if update_result:
                updated_risks.append(update_result)

        return {
            "near_miss_id": near_miss_id,
            "risks_updated": len(updated_risks),
            "updates": updated_risks,
        }

    async def _update_risk_score(
        self,
        risk_id: int,
        trigger_type: str,
        trigger_entity_type: str,
        trigger_entity_id: int,
        severity: Optional[IncidentSeverity] = None,
    ) -> Optional[Dict[str, Any]]:
        """Update a specific risk's score."""
        result = await self.db.execute(select(Risk).where(Risk.id == risk_id))
        risk = result.scalar_one_or_none()

        if not risk:
            return None

        # Calculate score adjustment
        old_score: int = int(risk.risk_score or 0)
        old_likelihood: int = int(risk.likelihood or 0)

        # Increase likelihood based on incident severity
        if severity:
            adjustment = self.SEVERITY_IMPACT.get(severity, 0)
            new_likelihood = min(5, old_likelihood + adjustment)

            if new_likelihood != old_likelihood:
                risk.likelihood = new_likelihood
                risk.risk_score = int(risk.likelihood) * int(risk.impact)
                risk.risk_level = self._calculate_risk_level(risk.risk_score)

                # Record history
                history = RiskScoreHistory(
                    risk_id=risk_id,
                    recorded_at=datetime.now(timezone.utc),
                    likelihood=risk.likelihood,
                    impact=risk.impact,
                    risk_score=risk.risk_score,
                    risk_level=risk.risk_level,
                    trigger_type=trigger_type,
                    trigger_entity_type=trigger_entity_type,
                    trigger_entity_id=trigger_entity_id,
                    previous_score=old_score,
                    score_change=int(risk.risk_score) - old_score,
                    change_reason=f"Automatic update from {trigger_entity_type} #{trigger_entity_id}",
                )
                self.db.add(history)
                await self.db.commit()

                return {
                    "risk_id": risk_id,
                    "old_score": old_score,
                    "new_score": risk.risk_score,
                    "old_level": self._calculate_risk_level(old_score),
                    "new_level": risk.risk_level,
                }

        return None

    async def _update_risk_velocity(
        self,
        risk_id: int,
        trigger_entity_type: str,
        trigger_entity_id: int,
    ) -> Optional[Dict[str, Any]]:
        """Update risk based on near-miss velocity (frequency)."""
        result = await self.db.execute(select(Risk).where(Risk.id == risk_id))
        risk = result.scalar_one_or_none()

        if not risk:
            return None

        # Count near misses linked to this risk in the last month
        one_month_ago = datetime.now(timezone.utc) - timedelta(days=30)

        count_result = await self.db.execute(
            select(func.count(NearMiss.id)).where(
                and_(
                    NearMiss.linked_risk_ids.contains(str(risk_id)),
                    NearMiss.created_at >= one_month_ago,
                )
            )
        )
        near_miss_count = count_result.scalar() or 0

        # Adjust likelihood based on velocity
        old_likelihood: int = int(risk.likelihood or 0)
        old_score: int = int(risk.risk_score or 0)

        if near_miss_count >= self.NEAR_MISS_VELOCITY_HIGH:
            velocity_adjustment = 2
        elif near_miss_count >= self.NEAR_MISS_VELOCITY_MEDIUM:
            velocity_adjustment = 1
        else:
            velocity_adjustment = 0

        new_likelihood = min(5, max(1, int(risk.likelihood or 0) + velocity_adjustment))

        if new_likelihood != old_likelihood:
            risk.likelihood = new_likelihood
            risk.risk_score = int(risk.likelihood) * int(risk.impact)
            risk.risk_level = self._calculate_risk_level(risk.risk_score)

            # Record history
            history = RiskScoreHistory(
                risk_id=risk_id,
                recorded_at=datetime.now(timezone.utc),
                likelihood=risk.likelihood,
                impact=risk.impact,
                risk_score=risk.risk_score,
                risk_level=risk.risk_level,
                trigger_type="near_miss_velocity",
                trigger_entity_type=trigger_entity_type,
                trigger_entity_id=trigger_entity_id,
                previous_score=old_score,
                score_change=int(risk.risk_score) - old_score,
                change_reason=f"Near-miss velocity update: {near_miss_count} incidents in last 30 days",
            )
            self.db.add(history)
            await self.db.commit()

            return {
                "risk_id": risk_id,
                "near_miss_count": near_miss_count,
                "old_score": old_score,
                "new_score": risk.risk_score,
            }

        return None

    def _calculate_risk_level(self, score: int) -> str:
        """Calculate risk level from score."""
        if score >= 20:
            return "critical"
        elif score >= 15:
            return "high"
        elif score >= 10:
            return "medium"
        elif score >= 5:
            return "low"
        else:
            return "negligible"

    async def get_risk_trend(
        self,
        risk_id: int,
        days: int = 90,
    ) -> List[Dict[str, Any]]:
        """Get risk score trend over time."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(
            select(RiskScoreHistory)
            .where(
                and_(
                    RiskScoreHistory.risk_id == risk_id,
                    RiskScoreHistory.recorded_at >= cutoff,
                )
            )
            .order_by(RiskScoreHistory.recorded_at)
        )
        history = result.scalars().all()

        return [
            {
                "date": h.recorded_at.isoformat(),
                "score": h.risk_score,
                "level": h.risk_level,
                "trigger": h.trigger_type,
            }
            for h in history
        ]


class KRIService:
    """Service for Key Risk Indicator management and tracking."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def calculate_kri(self, kri_id: int) -> Optional[Dict[str, Any]]:
        """Calculate and update a KRI value."""
        result = await self.db.execute(select(KeyRiskIndicator).where(KeyRiskIndicator.id == kri_id))
        kri = result.scalar_one_or_none()

        if not kri or not kri.auto_calculate:
            return None

        # Calculate based on data source
        value = await self._calculate_from_source(kri)

        if value is None:
            return None

        # Determine status
        new_status = kri.calculate_status(value)

        # Determine trend
        trend = await self._calculate_trend(kri, value)

        # Store measurement
        measurement = KRIMeasurement(
            kri_id=kri_id,
            measurement_date=datetime.now(timezone.utc),
            value=value,
            status=new_status,
            period_start=datetime.now(timezone.utc) - timedelta(days=30),
            period_end=datetime.now(timezone.utc),
        )
        self.db.add(measurement)

        # Check for alerts
        await self._check_thresholds(kri, value, new_status)

        # Update KRI current values
        old_status = kri.current_status
        kri.current_value = value
        kri.current_status = new_status
        kri.last_updated = datetime.now(timezone.utc)
        kri.trend_direction = trend

        await self.db.commit()

        return {
            "kri_id": kri_id,
            "kri_code": kri.code,
            "value": value,
            "status": new_status.value,
            "previous_status": old_status.value if old_status else None,
            "trend": trend.value if trend else None,
        }

    async def _calculate_from_source(self, kri: KeyRiskIndicator) -> Optional[float]:
        """Calculate KRI value from its data source."""
        data_source = kri.data_source

        # Incident-based KRIs
        if data_source == "incident_count":
            return await self._count_incidents(days=30)
        elif data_source == "incident_rate_per_1000":
            return await self._calculate_incident_rate()
        elif data_source == "critical_incident_count":
            return await self._count_incidents(days=30, severity=IncidentSeverity.CRITICAL)
        elif data_source == "open_incident_count":
            return await self._count_open_incidents()
        elif data_source == "incident_closure_rate":
            return await self._calculate_closure_rate("incident")

        # Near-miss KRIs
        elif data_source == "near_miss_count":
            return await self._count_near_misses(days=30)
        elif data_source == "near_miss_reporting_ratio":
            return await self._calculate_near_miss_ratio()

        # Complaint KRIs
        elif data_source == "complaint_count":
            return await self._count_complaints(days=30)
        elif data_source == "complaint_resolution_days":
            return await self._calculate_avg_resolution_days("complaint")

        # Audit KRIs
        elif data_source == "audit_finding_count":
            return await self._count_audit_findings(days=30)
        elif data_source == "high_risk_finding_count":
            return await self._count_high_risk_findings()

        # Risk KRIs
        elif data_source == "high_risk_count":
            return await self._count_high_risks()
        elif data_source == "overdue_action_count":
            return await self._count_overdue_actions()

        # Default
        logger.warning(f"Unknown data source: {data_source}")
        return None

    async def _count_incidents(
        self,
        days: int,
        severity: Optional[IncidentSeverity] = None,
    ) -> float:
        """Count incidents in the specified period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        query = select(func.count(Incident.id)).where(Incident.incident_date >= cutoff)

        if severity:
            query = query.where(Incident.severity == severity)

        result = await self.db.execute(query)
        return float(result.scalar() or 0)

    async def _count_open_incidents(self) -> float:
        """Count currently open incidents."""
        result = await self.db.execute(
            select(func.count(Incident.id)).where(
                Incident.status.in_(  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                    [
                        IncidentStatus.REPORTED,
                        IncidentStatus.UNDER_INVESTIGATION,
                        IncidentStatus.PENDING_ACTIONS,
                        IncidentStatus.ACTIONS_IN_PROGRESS,
                    ]
                )
            )
        )
        return float(result.scalar() or 0)

    async def _calculate_incident_rate(self) -> float:
        """Calculate incident rate per 1000 employees.

        Uses a configurable workforce size; defaults to 250 if not
        available from tenant settings.
        """
        incident_count = await self._count_incidents(days=30)
        workforce_size = await self._get_workforce_size()
        if workforce_size <= 0:
            logger.warning("Workforce size unavailable, defaulting to 250")
            workforce_size = 250
        return (incident_count / workforce_size) * 1000

    async def _get_workforce_size(self) -> int:
        """Retrieve the workforce headcount from tenant settings or default."""
        try:
            from src.domain.models.tenant import Tenant

            result = await self.db.execute(select(Tenant).limit(1))
            tenant = result.scalar_one_or_none()
            if tenant and hasattr(tenant, "employee_count") and tenant.employee_count:
                return int(tenant.employee_count)
        except Exception:
            logger.debug("Could not retrieve workforce size from tenant settings")
        return 250

    async def _calculate_closure_rate(self, entity_type: str) -> float:
        """Calculate percentage of cases closed within target."""
        # Simplified: count closed vs total in last 90 days
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)

        if entity_type == "incident":
            total_result = await self.db.execute(select(func.count(Incident.id)).where(Incident.created_at >= cutoff))
            total = total_result.scalar() or 0

            closed_result = await self.db.execute(
                select(func.count(Incident.id)).where(
                    and_(
                        Incident.created_at >= cutoff,
                        Incident.status == IncidentStatus.CLOSED,
                    )
                )
            )
            closed = closed_result.scalar() or 0

            if total == 0:
                return 100.0
            return (closed / total) * 100

        return 0.0

    async def _count_near_misses(self, days: int) -> float:
        """Count near misses in period."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(select(func.count(NearMiss.id)).where(NearMiss.created_at >= cutoff))
        return float(result.scalar() or 0)

    async def _calculate_near_miss_ratio(self) -> float:
        """Calculate near-miss to incident ratio (higher is better)."""
        days = 90
        near_misses = await self._count_near_misses(days)
        incidents = await self._count_incidents(days)

        if incidents == 0:
            return near_misses * 10 if near_misses > 0 else 0

        return near_misses / incidents

    async def _count_complaints(self, days: int) -> float:
        """Count complaints in period."""
        from src.domain.models.complaint import Complaint

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        result = await self.db.execute(select(func.count(Complaint.id)).where(Complaint.created_at >= cutoff))
        return float(result.scalar() or 0)

    async def _calculate_avg_resolution_days(self, entity_type: str) -> float:
        """Calculate average resolution time in days from closed records."""
        if entity_type == "complaint":
            from src.domain.models.complaint import Complaint, ComplaintStatus

            cutoff = datetime.now(timezone.utc) - timedelta(days=90)
            result = await self.db.execute(
                select(Complaint.received_date, Complaint.resolved_date).where(
                    and_(
                        Complaint.status.in_([ComplaintStatus.RESOLVED, ComplaintStatus.CLOSED]),  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                        Complaint.resolved_date.isnot(None),  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                        Complaint.created_at >= cutoff,
                    )
                )
            )
            rows = result.all()
            if not rows:
                return 0.0
            total_days = sum(
                (row.resolved_date - row.received_date).total_seconds() / 86400
                for row in rows
                if row.resolved_date and row.received_date
            )
            return round(total_days / len(rows), 1) if rows else 0.0

        if entity_type == "incident":
            cutoff = datetime.now(timezone.utc) - timedelta(days=90)
            result = await self.db.execute(
                select(Incident.created_at, Incident.closed_at).where(
                    and_(
                        Incident.status == IncidentStatus.CLOSED,
                        Incident.closed_at.isnot(None),  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                        Incident.created_at >= cutoff,
                    )
                )
            )
            rows = result.all()
            if not rows:
                return 0.0
            total_days = sum(
                (row.closed_at - row.created_at).total_seconds() / 86400
                for row in rows
                if row.closed_at and row.created_at
            )
            return round(total_days / len(rows), 1) if rows else 0.0

        return 0.0

    async def _count_audit_findings(self, days: int) -> float:
        """Count audit findings in period."""
        from src.domain.models.audit import AuditFinding

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        result = await self.db.execute(select(func.count(AuditFinding.id)).where(AuditFinding.created_at >= cutoff))
        return float(result.scalar() or 0)

    async def _count_high_risk_findings(self) -> float:
        """Count high-risk audit findings that are still open."""
        from src.domain.models.audit import AuditFinding, FindingStatus

        result = await self.db.execute(
            select(func.count(AuditFinding.id)).where(
                and_(
                    AuditFinding.severity.in_(["critical", "high"]),  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                    AuditFinding.status.in_([FindingStatus.OPEN, FindingStatus.IN_PROGRESS]),  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                )
            )
        )
        return float(result.scalar() or 0)

    async def _count_high_risks(self) -> float:
        """Count risks rated high or critical."""
        result = await self.db.execute(
            select(func.count(Risk.id)).where(
                and_(
                    Risk.risk_level.in_(["high", "critical"]),  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                    Risk.is_active == True,  # noqa: E712  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                )
            )
        )
        return float(result.scalar() or 0)

    async def _count_overdue_actions(self) -> float:
        """Count overdue corrective actions."""
        from src.domain.models.incident import ActionStatus, IncidentAction

        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(func.count(IncidentAction.id)).where(
                and_(
                    IncidentAction.due_date < now,
                    IncidentAction.status.in_([ActionStatus.OPEN, ActionStatus.IN_PROGRESS]),  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                )
            )
        )
        return float(result.scalar() or 0)

    async def _calculate_trend(
        self,
        kri: KeyRiskIndicator,
        current_value: float,
    ) -> Optional[KRITrendDirection]:
        """Calculate trend direction based on recent measurements."""
        # Get last 3 measurements
        result = await self.db.execute(
            select(KRIMeasurement)
            .where(KRIMeasurement.kri_id == kri.id)
            .order_by(KRIMeasurement.measurement_date.desc())  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
            .limit(3)
        )
        measurements = result.scalars().all()

        if len(measurements) < 2:
            return None

        # Compare with average of previous measurements
        previous_avg = sum(m.value for m in measurements) / len(measurements)

        if kri.lower_is_better:
            if current_value < previous_avg * 0.9:
                return KRITrendDirection.IMPROVING
            elif current_value > previous_avg * 1.1:
                return KRITrendDirection.DETERIORATING
            else:
                return KRITrendDirection.STABLE
        else:
            if current_value > previous_avg * 1.1:
                return KRITrendDirection.IMPROVING
            elif current_value < previous_avg * 0.9:
                return KRITrendDirection.DETERIORATING
            else:
                return KRITrendDirection.STABLE

    async def _check_thresholds(
        self,
        kri: KeyRiskIndicator,
        value: float,
        new_status: ThresholdStatus,
    ) -> None:
        """Check if thresholds are breached and create alerts."""
        # Check if status worsened (compare enum ordinal values)
        if kri.current_status and str(new_status.value) > str(kri.current_status.value):  # type: ignore[operator]  # ThresholdStatus enum comparison  # TYPE-IGNORE: MYPY-OVERRIDE
            # Status worsened - create alert
            threshold = kri.amber_threshold if new_status == ThresholdStatus.AMBER else kri.red_threshold

            alert = KRIAlert(
                kri_id=kri.id,
                alert_type="threshold_breach",
                severity=new_status,
                triggered_at=datetime.now(timezone.utc),
                trigger_value=value,
                previous_value=kri.current_value,
                threshold_breached=threshold,
                title=f"KRI Threshold Breach: {kri.name}",
                message=f"KRI '{kri.code}' has breached the {new_status.value} threshold. "
                f"Current value: {value} (threshold: {threshold})",
            )
            self.db.add(alert)

    async def calculate_all_kris(self) -> List[Dict[str, Any]]:
        """Calculate all active KRIs."""
        result = await self.db.execute(
            select(KeyRiskIndicator).where(
                and_(
                    KeyRiskIndicator.is_active == True,  # noqa: E712  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                    KeyRiskIndicator.auto_calculate == True,  # noqa: E712  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                )
            )
        )
        kris = result.scalars().all()

        results = []
        for kri in kris:
            calc_result = await self.calculate_kri(kri.id)
            if calc_result:
                results.append(calc_result)

        return results

    async def get_kri_dashboard(self) -> Dict[str, Any]:
        """Get KRI dashboard summary."""
        result = await self.db.execute(
            select(KeyRiskIndicator).where(KeyRiskIndicator.is_active == True)
        )  # noqa: E712  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
        kris = result.scalars().all()

        summary = {
            "total": len(kris),
            "by_status": {
                "green": 0,
                "amber": 0,
                "red": 0,
                "not_measured": 0,
            },
            "by_category": {},
            "alerts_pending": 0,
            "kris": [],
        }

        for kri in kris:
            if kri.current_status:
                summary["by_status"][kri.current_status.value] += 1
            else:
                summary["by_status"]["not_measured"] += 1

            category = kri.category.value
            if category not in summary["by_category"]:
                summary["by_category"][category] = 0
            summary["by_category"][category] += 1

            summary["kris"].append(
                {
                    "id": kri.id,
                    "code": kri.code,
                    "name": kri.name,
                    "category": category,
                    "value": kri.current_value,
                    "status": kri.current_status.value if kri.current_status else None,
                    "trend": kri.trend_direction.value if kri.trend_direction else None,
                }
            )

        # Count pending alerts
        alert_result = await self.db.execute(
            select(func.count(KRIAlert.id)).where(
                and_(
                    KRIAlert.is_acknowledged == False,  # noqa: E712  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                    KRIAlert.is_resolved == False,  # noqa: E712  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
                )
            )
        )
        summary["alerts_pending"] = alert_result.scalar() or 0

        return summary


# ============== Risk Matrix Configuration ==============

RISK_MATRIX = {
    1: {
        1: ("very_low", "#22c55e"),
        2: ("low", "#84cc16"),
        3: ("low", "#84cc16"),
        4: ("medium", "#eab308"),
        5: ("medium", "#eab308"),
    },
    2: {
        1: ("low", "#84cc16"),
        2: ("low", "#84cc16"),
        3: ("medium", "#eab308"),
        4: ("medium", "#eab308"),
        5: ("high", "#f97316"),
    },
    3: {
        1: ("low", "#84cc16"),
        2: ("medium", "#eab308"),
        3: ("medium", "#eab308"),
        4: ("high", "#f97316"),
        5: ("high", "#f97316"),
    },
    4: {
        1: ("medium", "#eab308"),
        2: ("medium", "#eab308"),
        3: ("high", "#f97316"),
        4: ("high", "#f97316"),
        5: ("critical", "#ef4444"),
    },
    5: {
        1: ("medium", "#eab308"),
        2: ("high", "#f97316"),
        3: ("high", "#f97316"),
        4: ("critical", "#ef4444"),
        5: ("critical", "#ef4444"),
    },
}


def calculate_risk_level(likelihood: int, impact: int) -> tuple[int, str, str]:
    """Calculate risk score and level from likelihood and impact.

    Returns (score, level_name, color_hex).
    """
    score = likelihood * impact
    row = RISK_MATRIX.get(likelihood, {})
    level, color = row.get(impact, ("medium", "#eab308"))  # type: ignore[union-attr]  # dict.get always returns dict here  # TYPE-IGNORE: MYPY-OVERRIDE
    return score, level, color
