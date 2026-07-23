"""Calculations and data access for the H&S performance board."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, datetime, time, timezone
from typing import Any

from sqlalchemy import func, or_, select

from src.domain.models.complaint import Complaint
from src.domain.models.hs_reporting_period import HsReportingPeriod
from src.domain.models.incident import Incident
from src.domain.models.near_miss import NearMiss
from src.domain.models.rta import RoadTrafficCollision

RATE_UNIT = "per_100000_hours"


def pro_rated_hours(*, average_fte: float, hours_per_fte_year: float, period_start: date, period_end: date) -> float:
    """Return Excel-compatible annual-hours pro-rata, inclusive of both dates."""
    days = max(0, (period_end - period_start).days + 1)
    return average_fte * hours_per_fte_year * days / 365


def effective_hours(period: HsReportingPeriod) -> float:
    """Prefer admin-entered manual hours; otherwise FTE pro-rata."""
    if period.manual_hours is not None and period.manual_hours > 0:
        return float(period.manual_hours)
    return pro_rated_hours(
        average_fte=period.average_fte,
        hours_per_fte_year=period.hours_per_fte_year,
        period_start=period.period_start,
        period_end=period.period_end,
    )


def rate_per_100000(*, count: int, hours: float) -> float:
    return round((count / hours) * 100000, 2) if hours else 0.0


class HsKpiService:
    def __init__(self, db) -> None:
        self.db = db

    async def _count(self, model, field, tenant_id: int, start: date, end: date, *conditions) -> int:
        start_dt = datetime.combine(start, time.min, tzinfo=timezone.utc)
        end_dt = datetime.combine(end, time.max, tzinfo=timezone.utc)
        query = (
            select(func.count())
            .select_from(model)
            .where(model.tenant_id == tenant_id, field >= start_dt, field <= end_dt, *conditions)
        )
        return int((await self.db.execute(query)).scalar() or 0)

    async def period_summary(self, period: HsReportingPeriod) -> dict[str, Any]:
        start, end = period.period_start, period.period_end
        injuries = await self._count(
            Incident,
            Incident.incident_date,
            period.tenant_id,
            start,
            end,
            or_(Incident.is_injury.is_(True), Incident.is_minor_injury.is_(True)),
        )
        incident_ltis = await self._count(
            Incident, Incident.incident_date, period.tenant_id, start, end, Incident.is_lti.is_(True)
        )
        rtas = await self._count(
            RoadTrafficCollision, RoadTrafficCollision.collision_date, period.tenant_id, start, end
        )
        rta_lti_column = getattr(RoadTrafficCollision, "is_lti", None)
        rta_ltis = (
            await self._count(
                RoadTrafficCollision,
                RoadTrafficCollision.collision_date,
                period.tenant_id,
                start,
                end,
                rta_lti_column.is_(True),
            )
            if rta_lti_column is not None
            else 0
        )
        riddor_incidents = await self._count(
            Incident, Incident.incident_date, period.tenant_id, start, end, Incident.is_riddor_reportable.is_(True)
        )
        rta_riddor_column = getattr(RoadTrafficCollision, "is_riddor_reportable", None)
        riddor_rtas = (
            await self._count(
                RoadTrafficCollision,
                RoadTrafficCollision.collision_date,
                period.tenant_id,
                start,
                end,
                rta_riddor_column.is_(True),
            )
            if rta_riddor_column is not None
            else 0
        )
        hours = effective_hours(period)
        return {
            "reporting_year": period.reporting_year,
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "average_fte": period.average_fte,
            "hours_per_fte_year": period.hours_per_fte_year,
            "manual_hours": period.manual_hours,
            "hours": round(hours, 2),
            "hours_source": "manual" if period.manual_hours is not None and period.manual_hours > 0 else "calculated",
            "injuries": injuries,
            "near_misses": await self._count(NearMiss, NearMiss.event_date, period.tenant_id, start, end),
            "rtas": rtas,
            "complaints": await self._count(Complaint, Complaint.received_date, period.tenant_id, start, end),
            "ltis": incident_ltis + rta_ltis,
            "riddor": riddor_incidents + riddor_rtas,
            "ltifr": rate_per_100000(count=incident_ltis + rta_ltis, hours=hours),
            "afr": rate_per_100000(count=injuries, hours=hours),
            "rate_unit": RATE_UNIT,
        }

    async def summary(self, tenant_id: int) -> dict[str, Any]:
        periods = (
            (
                await self.db.execute(
                    select(HsReportingPeriod)
                    .where(HsReportingPeriod.tenant_id == tenant_id)
                    .order_by(HsReportingPeriod.reporting_year)
                )
            )
            .scalars()
            .all()
        )
        by_year = [await self.period_summary(period) for period in periods]
        return {"rate_unit": RATE_UNIT, "by_year": by_year}

    async def ensure_default_periods(self, tenant_id: int) -> list[HsReportingPeriod]:
        """Create the workbook's baseline inputs once per tenant."""
        existing = {
            row.reporting_year
            for row in (
                await self.db.execute(select(HsReportingPeriod).where(HsReportingPeriod.tenant_id == tenant_id))
            ).scalars()
        }
        defaults = (
            (2024, date(2024, 10, 1), date(2024, 12, 31), 95),
            (2025, date(2025, 1, 1), date(2025, 12, 31), 105),
            (2026, date(2026, 1, 1), date(2026, 12, 31), 109),
        )
        for year, start, end, fte in defaults:
            if year not in existing:
                self.db.add(
                    HsReportingPeriod(
                        tenant_id=tenant_id,
                        reporting_year=year,
                        period_start=start,
                        period_end=end,
                        average_fte=fte,
                        hours_per_fte_year=2124,
                    )
                )
        await self.db.flush()
        return (
            (
                await self.db.execute(
                    select(HsReportingPeriod)
                    .where(HsReportingPeriod.tenant_id == tenant_id)
                    .order_by(HsReportingPeriod.reporting_year)
                )
            )
            .scalars()
            .all()
        )
