"""Automated CAPA Pipeline for Vehicle Defects.

Auto-creates CAPA actions from vehicle defects with priority-based SLAs
and escalation chains. Runs during PAMS sync (synchronous context) and
can also be triggered via API.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger(__name__)

SLA_DAYS = {
    "P1": 1,
    "P2": 3,
    "P3": 14,
}

PRIORITY_MAP = {
    "P1": "critical",
    "P2": "high",
    "P3": "medium",
}


def create_capa_from_defect_sync(
    defect_id: int,
    defect_priority: str,
    vehicle_reg: str,
    check_field: str,
    check_value: str,
    db: Any,
) -> int | None:
    """Create a CAPA action from a vehicle defect (synchronous, for Celery tasks).

    Returns the new CAPA id, or None if a CAPA already exists for this defect.
    """
    from src.domain.models.capa import CAPAAction, CAPASource, CAPAStatus, CAPAType

    existing = (
        db.query(CAPAAction)
        .filter(
            CAPAAction.source_type == CAPASource.VEHICLE_DEFECT.value,
            CAPAAction.source_id == defect_id,
        )
        .first()
    )
    if existing:
        return None

    sla_days = SLA_DAYS.get(defect_priority, 14)
    capa_priority = PRIORITY_MAP.get(defect_priority, "medium")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    count = db.query(CAPAAction).count()
    ref = f"CAPA-{now.year}-{count + 1:04d}"

    action = CAPAAction(
        reference_number=ref,
        title=f"Vehicle Defect: {check_field} failed on {vehicle_reg}",
        description=(
            f"Auto-generated from vehicle defect.\n"
            f"Vehicle: {vehicle_reg}\n"
            f"Check: {check_field}\n"
            f"Value: {check_value}\n"
            f"Priority: {defect_priority}"
        ),
        capa_type=CAPAType.CORRECTIVE.value,
        status=CAPAStatus.OPEN.value,
        priority=capa_priority,
        source_type=CAPASource.VEHICLE_DEFECT.value,
        source_id=defect_id,
        due_date=now + timedelta(days=sla_days),
        created_by_id=1,
        created_at=now,
    )
    db.add(action)
    logger.info(
        "Auto-created CAPA %s for defect %d (vehicle %s, priority %s, SLA %dd)",
        ref, defect_id, vehicle_reg, defect_priority, sla_days,
    )
    return action.id


async def create_capa_from_defect_async(
    defect_id: int,
    defect_priority: str,
    vehicle_reg: str,
    check_field: str,
    check_value: str,
    user_id: int,
    tenant_id: int | None,
    db: Any,
) -> dict | None:
    """Create a CAPA action from a vehicle defect (async, for API endpoints).

    Returns the new CAPA dict, or None if one already exists.
    """
    from sqlalchemy import func, select

    from src.domain.models.capa import CAPAAction, CAPASource, CAPAStatus, CAPAType

    existing = await db.execute(
        select(CAPAAction).where(
            CAPAAction.source_type == CAPASource.VEHICLE_DEFECT.value,
            CAPAAction.source_id == defect_id,
        )
    )
    if existing.scalar_one_or_none():
        return None

    sla_days = SLA_DAYS.get(defect_priority, 14)
    capa_priority = PRIORITY_MAP.get(defect_priority, "medium")
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    count_result = await db.execute(select(func.count(CAPAAction.id)))
    count = count_result.scalar() or 0
    ref = f"CAPA-{now.year}-{count + 1:04d}"

    action = CAPAAction(
        reference_number=ref,
        title=f"Vehicle Defect: {check_field} failed on {vehicle_reg}",
        description=(
            f"Auto-generated from vehicle defect.\n"
            f"Vehicle: {vehicle_reg}\n"
            f"Check: {check_field}\n"
            f"Value: {check_value}\n"
            f"Priority: {defect_priority}"
        ),
        capa_type=CAPAType.CORRECTIVE.value,
        status=CAPAStatus.OPEN.value,
        priority=capa_priority,
        source_type=CAPASource.VEHICLE_DEFECT.value,
        source_id=defect_id,
        due_date=now + timedelta(days=sla_days),
        created_by_id=user_id,
        tenant_id=tenant_id,
        created_at=now,
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)

    return {
        "capa_id": action.id,
        "reference_number": ref,
        "priority": capa_priority,
        "sla_days": sla_days,
        "due_date": str(action.due_date),
    }
