"""Vehicle / van checklist Assist gatherers (harvested from FR-ASSIST-DEPTH-02)."""

from __future__ import annotations

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.vehicle_defect import DefectStatus, VehicleDefect
from src.domain.services.copilot_grounding import GroundedFacts, GroundedRef

_OPEN_DEFECT_STATUSES = (
    DefectStatus.OPEN,
    DefectStatus.AUTO_DETECTED,
    DefectStatus.ACKNOWLEDGED,
    DefectStatus.ACTION_ASSIGNED,
)
_HEATMAP_TOP_N = 20
_MAX_SAMPLE_REFS = 10


async def gather_vehicle_check_top_failures(db: AsyncSession, *, tenant_id: int) -> GroundedFacts:
    """Heatmap-equivalent: most frequent failed check fields from vehicle_defects."""
    total = int(
        (
            await db.execute(
                select(func.count()).select_from(VehicleDefect).where(VehicleDefect.tenant_id == tenant_id)
            )
        ).scalar()
        or 0
    )
    heat_rows = (
        await db.execute(
            select(
                VehicleDefect.check_field,
                VehicleDefect.pams_table,
                func.count().label("failure_count"),
            )
            .where(VehicleDefect.tenant_id == tenant_id)
            .group_by(VehicleDefect.check_field, VehicleDefect.pams_table)
            .order_by(func.count().desc())
            .limit(_HEATMAP_TOP_N)
        )
    ).all()
    failure_rows = [(f"{str(row[0] or 'unknown')} ({str(row[1] or 'unknown')})", int(row[2])) for row in heat_rows]
    sample = (
        await db.execute(
            select(VehicleDefect.id, VehicleDefect.check_field, VehicleDefect.vehicle_reg)
            .where(VehicleDefect.tenant_id == tenant_id)
            .order_by(VehicleDefect.id.desc())
            .limit(_MAX_SAMPLE_REFS)
        )
    ).all()
    refs = [
        GroundedRef(
            module="vehicle_defect",
            id=int(row.id),
            reference_number=f"VD-{int(row.id)}",
            path="/vehicle-checklists",
        )
        for row in sample
    ]
    return GroundedFacts(
        intent="vehicle_check_top_failures",
        tenant_id=tenant_id,
        label="Vehicle-check failure heatmap (defect count)",
        count=total,
        refs=refs,
        extras={"top_failure_fields": len(failure_rows)},
        breakdowns=[("Top failed check fields", failure_rows)],
    )


async def gather_vehicle_check_defect_summary(db: AsyncSession, *, tenant_id: int) -> GroundedFacts:
    """Open defect totals by priority — mirrors vehicle checklist analytics summary."""
    open_filter = and_(
        VehicleDefect.tenant_id == tenant_id,
        VehicleDefect.status.in_(_OPEN_DEFECT_STATUSES),
    )
    open_total = int(
        (await db.execute(select(func.count()).select_from(VehicleDefect).where(open_filter))).scalar() or 0
    )
    priority_rows: list[tuple[str, int]] = []
    for label in ("P1", "P2", "P3"):
        val = int(
            (
                await db.execute(
                    select(func.count()).select_from(VehicleDefect).where(open_filter, VehicleDefect.priority == label)
                )
            ).scalar()
            or 0
        )
        priority_rows.append((label, val))
    sample = (
        await db.execute(
            select(VehicleDefect.id).where(open_filter).order_by(VehicleDefect.id.desc()).limit(_MAX_SAMPLE_REFS)
        )
    ).all()
    refs = [
        GroundedRef(
            module="vehicle_defect",
            id=int(row.id),
            reference_number=f"VD-{int(row.id)}",
            path="/vehicle-checklists",
        )
        for row in sample
    ]
    return GroundedFacts(
        intent="vehicle_check_defect_summary",
        tenant_id=tenant_id,
        label="Open vehicle-check defects",
        count=open_total,
        refs=refs,
        extras={
            "open_p1": priority_rows[0][1],
            "open_p2": priority_rows[1][1],
            "open_p3": priority_rows[2][1],
        },
        breakdowns=[("Open defects by priority", priority_rows)],
    )


__all__ = [
    "gather_vehicle_check_defect_summary",
    "gather_vehicle_check_top_failures",
]
