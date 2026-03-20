"""Vehicle Checklist analytics endpoints.

Provides dashboard summary cards, trend data, and failure heatmaps
for the Van Checklists governance module.
"""

import logging
import math
from datetime import datetime, timedelta, timezone
from io import StringIO
from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.vehicle_checklist import AnalyticsSummary, HeatmapEntry, TrendDataPoint
from src.domain.models.capa import CAPAAction, CAPAStatus
from src.domain.models.pams_cache import PAMSSyncLog, PAMSVanChecklistCache, PAMSVanChecklistMonthlyCache
from src.domain.models.vehicle_defect import VehicleDefect

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/summary")
async def analytics_summary(
    current_user: CurrentUser,
    db: DbSession,
) -> AnalyticsSummary:
    """Dashboard summary cards: totals, defect counts, pass rate."""
    total_daily = 0
    total_monthly = 0
    open_defects = 0
    p1 = 0
    p2 = 0
    p3 = 0
    overdue_actions = 0
    last_sync_iso: Optional[str] = None

    try:
        total_daily = (await db.execute(select(func.count()).select_from(PAMSVanChecklistCache))).scalar() or 0
    except Exception:
        logger.warning("analytics_summary: failed to count daily cache", exc_info=True)

    try:
        total_monthly = (
            await db.execute(select(func.count()).select_from(PAMSVanChecklistMonthlyCache))
        ).scalar() or 0
    except Exception:
        logger.warning("analytics_summary: failed to count monthly cache", exc_info=True)

    try:
        open_q = (
            select(func.count())
            .select_from(VehicleDefect)
            .where(VehicleDefect.status.in_(["open", "auto_detected", "acknowledged", "action_assigned"]))
        )
        open_defects = (await db.execute(open_q)).scalar() or 0

        for label, priority_val in [("p1", "P1"), ("p2", "P2"), ("p3", "P3")]:
            val = (
                await db.execute(
                    select(func.count())
                    .select_from(VehicleDefect)
                    .where(
                        VehicleDefect.priority == priority_val,
                        VehicleDefect.status.in_(["open", "auto_detected", "acknowledged", "action_assigned"]),
                    )
                )
            ).scalar() or 0
            if label == "p1":
                p1 = val
            elif label == "p2":
                p2 = val
            else:
                p3 = val
    except Exception:
        logger.warning("analytics_summary: failed to count defects", exc_info=True)

    try:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        overdue_q = (
            select(func.count())
            .select_from(CAPAAction)
            .where(
                CAPAAction.source_reference.like("vehicle_defect:%"),
                CAPAAction.status.in_([CAPAStatus.OPEN, CAPAStatus.IN_PROGRESS]),
                CAPAAction.due_date < now,
            )
        )
        overdue_actions = (await db.execute(overdue_q)).scalar() or 0
    except Exception:
        logger.warning("analytics_summary: failed to count overdue actions", exc_info=True)

    try:
        last_sync_row = (
            await db.execute(
                select(PAMSSyncLog)
                .where(PAMSSyncLog.status == "success")
                .order_by(PAMSSyncLog.completed_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if last_sync_row and last_sync_row.completed_at:
            last_sync_iso = last_sync_row.completed_at.isoformat()
    except Exception:
        logger.warning("analytics_summary: failed to get last sync", exc_info=True)

    return AnalyticsSummary(
        total_daily_checks=total_daily,
        total_monthly_checks=total_monthly,
        open_defects=open_defects,
        p1_defects=p1,
        p2_defects=p2,
        p3_defects=p3,
        overdue_actions=overdue_actions,
        last_sync=last_sync_iso,
    )


@router.get("/trends")
async def analytics_trends(
    current_user: CurrentUser,
    db: DbSession,
    days: int = Query(30, ge=7, le=365),
) -> list[TrendDataPoint]:
    """Defect creation trend over time grouped by day."""
    cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=days)

    q = text("""
        SELECT
            DATE(created_at) as dt,
            COUNT(*) FILTER (WHERE priority = 'P1') as p1,
            COUNT(*) FILTER (WHERE priority = 'P2') as p2,
            COUNT(*) FILTER (WHERE priority = 'P3') as p3,
            COUNT(*) as total
        FROM vehicle_defects
        WHERE created_at >= :cutoff
        GROUP BY DATE(created_at)
        ORDER BY dt
    """)

    result = await db.execute(q, {"cutoff": cutoff})
    rows = result.mappings().all()

    return [
        TrendDataPoint(
            date=str(row["dt"]),
            p1=row["p1"],
            p2=row["p2"],
            p3=row["p3"],
            total=row["total"],
        )
        for row in rows
    ]


@router.get("/heatmap")
async def analytics_heatmap(
    current_user: CurrentUser,
    db: DbSession,
    limit: int = Query(20, ge=1, le=100),
) -> list[HeatmapEntry]:
    """Most frequently failed check fields across all defects."""
    q = (
        select(
            VehicleDefect.check_field,
            VehicleDefect.pams_table,
            func.count().label("failure_count"),
        )
        .group_by(VehicleDefect.check_field, VehicleDefect.pams_table)
        .order_by(func.count().desc())
        .limit(limit)
    )

    rows = (await db.execute(q)).all()
    return [
        HeatmapEntry(
            check_field=row[0],
            pams_table=row[1],
            failure_count=row[2],
        )
        for row in rows
    ]


# ─── CSV Exports ─────────────────────────────────────────────────────


@router.get("/export/daily")
async def export_daily_csv(
    current_user: CurrentUser,
    db: DbSession,
) -> StreamingResponse:
    """Export all cached daily checklists as CSV."""
    rows = (
        (await db.execute(select(PAMSVanChecklistCache).order_by(PAMSVanChecklistCache.pams_id.desc()))).scalars().all()
    )

    return _build_csv_response(rows, "daily_checklists.csv")


@router.get("/export/monthly")
async def export_monthly_csv(
    current_user: CurrentUser,
    db: DbSession,
) -> StreamingResponse:
    """Export all cached monthly checklists as CSV."""
    rows = (
        (await db.execute(select(PAMSVanChecklistMonthlyCache).order_by(PAMSVanChecklistMonthlyCache.pams_id.desc())))
        .scalars()
        .all()
    )

    return _build_csv_response(rows, "monthly_checklists.csv")


@router.get("/export/defects")
async def export_defects_csv(
    current_user: CurrentUser,
    db: DbSession,
) -> StreamingResponse:
    """Export defect register as CSV."""
    rows = (await db.execute(select(VehicleDefect).order_by(VehicleDefect.created_at.desc()))).scalars().all()

    import csv

    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "ID",
            "PAMS Table",
            "Record ID",
            "Check Field",
            "Check Value",
            "Priority",
            "Status",
            "Vehicle Reg",
            "Notes",
            "Assigned To",
            "Created At",
        ]
    )
    for d in rows:
        writer.writerow(
            [
                d.id,
                d.pams_table,
                d.pams_record_id,
                d.check_field,
                d.check_value,
                d.priority.value if hasattr(d.priority, "value") else d.priority,
                d.status.value if hasattr(d.status, "value") else d.status,
                d.vehicle_reg,
                d.notes,
                d.assigned_to_email,
                d.created_at.isoformat() if d.created_at else "",
            ]
        )

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=defects_register.csv"},
    )


def _build_csv_response(cache_rows: list, filename: str) -> StreamingResponse:
    """Build a CSV StreamingResponse from cache rows with JSON raw_data."""
    import csv

    output = StringIO()
    writer = csv.writer(output)

    if not cache_rows:
        writer.writerow(["No data"])
        output.seek(0)
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    first_data = cache_rows[0].raw_data or {}
    headers = ["pams_id", "synced_at"] + list(first_data.keys())
    writer.writerow(headers)

    for row in cache_rows:
        data = row.raw_data or {}
        csv_row = [row.pams_id, row.synced_at.isoformat() if row.synced_at else ""]
        for h in list(first_data.keys()):
            val = data.get(h, "")
            if isinstance(val, datetime):
                val = val.isoformat()
            csv_row.append(val)
        writer.writerow(csv_row)

    output.seek(0)
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
