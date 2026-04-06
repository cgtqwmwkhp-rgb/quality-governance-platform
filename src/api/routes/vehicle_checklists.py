"""Vehicle Checklists API routes — PAMS integration.

Read-only access to the external PAMS MySQL database for van checklists,
plus governance defect management stored in QGP PostgreSQL.
"""

import logging
import math
from datetime import datetime, timezone
from typing import Any, NoReturn, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.vehicle_checklist import (
    ChecklistListResponse,
    ChecklistSchemaResponse,
    DefectActionCreate,
    DefectCreate,
    DefectListResponse,
    DefectResponse,
    DefectUpdate,
)
from src.domain.exceptions import AuthorizationError, DomainError, NotFoundError, ValidationError
from src.domain.models.pams_cache import PAMSSyncLog, PAMSVanChecklistCache, PAMSVanChecklistMonthlyCache
from src.domain.models.vehicle_defect import VehicleDefect
from src.domain.services.audit_service import record_audit_event
from src.infrastructure.pams_database import get_pams_columns, get_pams_db, get_pams_table, is_pams_available

logger = logging.getLogger(__name__)

router = APIRouter()

TABLE_MAP = {
    "daily": "vanchecklist",
    "monthly": "vanchecklistmonthly",
}

CACHE_MODEL_MAP = {
    "daily": PAMSVanChecklistCache,
    "monthly": PAMSVanChecklistMonthlyCache,
}


def _service_unavailable(message: str) -> NoReturn:
    exc = DomainError(message, code="SERVICE_UNAVAILABLE")
    exc.http_status = 503
    raise exc


def _require_pams() -> None:
    if not is_pams_available():
        _service_unavailable("PAMS database connection is not configured or unavailable.")


def _defect_to_response(d: VehicleDefect) -> DefectResponse:
    return DefectResponse(
        id=d.id,
        pams_table=d.pams_table,
        pams_record_id=d.pams_record_id,
        check_field=d.check_field,
        check_value=d.check_value,
        priority=d.priority.value if hasattr(d.priority, "value") else str(d.priority),
        status=d.status.value if hasattr(d.status, "value") else str(d.status),
        notes=d.notes,
        vehicle_reg=d.vehicle_reg,
        created_by_id=d.created_by_id,
        assigned_to_email=d.assigned_to_email,
        created_at=d.created_at.isoformat() if d.created_at else None,
        updated_at=d.updated_at.isoformat() if d.updated_at else None,
    )


# ─── Schema discovery ───────────────────────────────────────────────


@router.get("/schema")
async def get_schema(
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Return auto-discovered column names for both PAMS tables."""
    _require_pams()
    return {
        "daily": get_pams_columns("vanchecklist"),
        "monthly": get_pams_columns("vanchecklistmonthly"),
    }


# ─── List checklists (prefer cache, fallback to live PAMS) ──────────


async def _list_from_cache(
    db: AsyncSession,
    cache_model: Any,
    page: int,
    page_size: int,
    search: Optional[str],
) -> ChecklistListResponse:
    """Read cached rows from QGP PostgreSQL."""
    count_q = select(func.count()).select_from(cache_model)
    total = (await db.execute(count_q)).scalar() or 0

    q = select(cache_model).order_by(cache_model.pams_id.desc()).offset((page - 1) * page_size).limit(page_size)
    rows = (await db.execute(q)).scalars().all()

    items = []
    for row in rows:
        data = dict(row.raw_data) if row.raw_data else {}
        data["_pams_id"] = row.pams_id
        data["_synced_at"] = row.synced_at.isoformat() if row.synced_at else None
        items.append(data)

    return ChecklistListResponse(
        items=items,
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


async def _list_from_live_pams(
    table_name: str,
    page: int,
    page_size: int,
) -> ChecklistListResponse:
    """Query PAMS MySQL directly (fallback when cache is empty)."""
    _require_pams()
    pams_tbl = get_pams_table(table_name)
    if pams_tbl is None:
        raise NotFoundError(f"PAMS table {table_name} not found")

    try:
        async for pams_session in get_pams_db():
            count_q = select(func.count()).select_from(pams_tbl)
            total = (await pams_session.execute(count_q)).scalar() or 0

            pk_cols = list(pams_tbl.primary_key.columns)
            order_col = pk_cols[0] if pk_cols else list(pams_tbl.columns)[0]

            q = select(pams_tbl).order_by(order_col.desc()).offset((page - 1) * page_size).limit(page_size)
            result = await pams_session.execute(q)
            rows = result.mappings().all()

            items = []
            for row in rows:
                items.append({k: _serialise_value(v) for k, v in dict(row).items()})

            return ChecklistListResponse(
                items=items,
                total=total,
                page=page,
                page_size=page_size,
                pages=max(1, math.ceil(total / page_size)),
            )
    except HTTPException:
        raise
    except Exception:
        logger.exception("PAMS live query failed for %s", table_name)
        _service_unavailable("PAMS database is temporarily unavailable. Please try again shortly.")

    _service_unavailable("Could not obtain PAMS session")


def _serialise_value(v: Any) -> Any:
    """Make arbitrary DB values JSON-safe."""
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return v


@router.get("/daily")
async def list_daily(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(None),
) -> ChecklistListResponse:
    """List daily van checklists (cached or live)."""
    cache_count = (await db.execute(select(func.count()).select_from(PAMSVanChecklistCache))).scalar() or 0

    if cache_count > 0:
        return await _list_from_cache(db, PAMSVanChecklistCache, page, page_size, search)

    return await _list_from_live_pams("vanchecklist", page, page_size)


@router.get("/monthly")
async def list_monthly(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    search: Optional[str] = Query(None),
) -> ChecklistListResponse:
    """List monthly van checklists (cached or live)."""
    cache_count = (await db.execute(select(func.count()).select_from(PAMSVanChecklistMonthlyCache))).scalar() or 0

    if cache_count > 0:
        return await _list_from_cache(db, PAMSVanChecklistMonthlyCache, page, page_size, search)

    return await _list_from_live_pams("vanchecklistmonthly", page, page_size)


# ─── Single record detail ───────────────────────────────────────────


@router.get("/daily/{record_id}")
async def get_daily_record(
    record_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> dict[str, Any]:
    """Get a single daily checklist record."""
    cached = (
        await db.execute(select(PAMSVanChecklistCache).where(PAMSVanChecklistCache.pams_id == record_id))
    ).scalar_one_or_none()

    if cached and cached.raw_data:
        data = dict(cached.raw_data)
        data["_pams_id"] = cached.pams_id
        return data

    _require_pams()
    pams_tbl = get_pams_table("vanchecklist")
    if pams_tbl is None:
        raise NotFoundError("PAMS vanchecklist table not found")

    pk_col = list(pams_tbl.primary_key.columns)[0]
    async for pams_session in get_pams_db():
        result = await pams_session.execute(select(pams_tbl).where(pk_col == record_id))
        row = result.mappings().first()
        if not row:
            raise NotFoundError("Record not found")
        return {k: _serialise_value(v) for k, v in dict(row).items()}

    _service_unavailable("Could not obtain PAMS session")


@router.get("/monthly/{record_id}")
async def get_monthly_record(
    record_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> dict[str, Any]:
    """Get a single monthly checklist record."""
    cached = (
        await db.execute(select(PAMSVanChecklistMonthlyCache).where(PAMSVanChecklistMonthlyCache.pams_id == record_id))
    ).scalar_one_or_none()

    if cached and cached.raw_data:
        data = dict(cached.raw_data)
        data["_pams_id"] = cached.pams_id
        return data

    _require_pams()
    pams_tbl = get_pams_table("vanchecklistmonthly")
    if pams_tbl is None:
        raise NotFoundError("PAMS vanchecklistmonthly table not found")

    pk_col = list(pams_tbl.primary_key.columns)[0]
    async for pams_session in get_pams_db():
        result = await pams_session.execute(select(pams_tbl).where(pk_col == record_id))
        row = result.mappings().first()
        if not row:
            raise NotFoundError("Record not found")
        return {k: _serialise_value(v) for k, v in dict(row).items()}

    _service_unavailable("Could not obtain PAMS session")


# ─── Defect CRUD ─────────────────────────────────────────────────────


@router.post("/defects", status_code=status.HTTP_201_CREATED)
async def create_defect(
    payload: DefectCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> DefectResponse:
    """Flag a vehicle defect with P1/P2/P3 priority."""
    defect = VehicleDefect(
        pams_table=payload.pams_table,
        pams_record_id=payload.pams_record_id,
        check_field=payload.check_field,
        check_value=payload.check_value,
        priority=payload.priority,
        notes=payload.notes,
        vehicle_reg=payload.vehicle_reg,
        tenant_id=current_user.tenant_id,
        created_by_id=current_user.id,
        assigned_to_email=payload.assigned_to_email,
    )
    db.add(defect)
    await db.flush()

    await _log_audit_trail(db, current_user, defect, "created")

    if payload.priority == "P1":
        await _create_p1_notification(db, current_user, defect)

    return _defect_to_response(defect)


@router.get("/defects")
async def list_defects(
    current_user: CurrentUser,
    db: DbSession,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    priority: Optional[str] = Query(None, pattern="^(P1|P2|P3)$"),
    status_filter: Optional[str] = Query(None, alias="status"),
) -> DefectListResponse:
    """List all flagged vehicle defects."""
    base = select(VehicleDefect).where(VehicleDefect.tenant_id == current_user.tenant_id)
    count_base = (
        select(func.count()).select_from(VehicleDefect).where(VehicleDefect.tenant_id == current_user.tenant_id)
    )

    if priority:
        base = base.where(VehicleDefect.priority == priority)
        count_base = count_base.where(VehicleDefect.priority == priority)
    if status_filter:
        base = base.where(VehicleDefect.status == status_filter)
        count_base = count_base.where(VehicleDefect.status == status_filter)

    total = (await db.execute(count_base)).scalar() or 0

    q = base.order_by(VehicleDefect.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
    defects = (await db.execute(q)).scalars().all()

    return DefectListResponse(
        items=[_defect_to_response(d) for d in defects],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, math.ceil(total / page_size)),
    )


@router.get("/defects/{defect_id}")
async def get_defect(
    defect_id: int,
    current_user: CurrentUser,
    db: DbSession,
) -> DefectResponse:
    """Get a single defect by ID."""
    defect = (
        await db.execute(
            select(VehicleDefect).where(
                VehicleDefect.id == defect_id,
                VehicleDefect.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not defect:
        raise NotFoundError("Defect not found")
    return _defect_to_response(defect)


@router.patch("/defects/{defect_id}")
async def update_defect(
    defect_id: int,
    payload: DefectUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> DefectResponse:
    """Update a vehicle defect (priority, status, notes)."""
    defect = (
        await db.execute(
            select(VehicleDefect).where(
                VehicleDefect.id == defect_id,
                VehicleDefect.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not defect:
        raise NotFoundError("Defect not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(defect, field, value)

    await db.flush()
    await _log_audit_trail(db, current_user, defect, "updated")
    return _defect_to_response(defect)


@router.post("/defects/{defect_id}/actions", status_code=status.HTTP_201_CREATED)
async def create_defect_action(
    defect_id: int,
    payload: DefectActionCreate,
    current_user: CurrentUser,
    db: DbSession,
) -> dict[str, Any]:
    """Create an action against a vehicle defect (stored as CAPAAction)."""
    from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType

    defect = (
        await db.execute(
            select(VehicleDefect).where(
                VehicleDefect.id == defect_id,
                VehicleDefect.tenant_id == current_user.tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not defect:
        raise NotFoundError("Defect not found")

    priority_map = {"P1": CAPAPriority.CRITICAL, "P2": CAPAPriority.HIGH, "P3": CAPAPriority.MEDIUM}
    defect_priority_str = defect.priority.value if hasattr(defect.priority, "value") else str(defect.priority)
    capa_priority = priority_map.get(defect_priority_str, CAPAPriority.MEDIUM)

    ref_num = f"VD-{defect.id:05d}-{datetime.now(timezone.utc).strftime('%y%m%d')}"

    due_date_parsed = None
    if payload.due_date:
        try:
            due_date_parsed = datetime.fromisoformat(payload.due_date)
        except ValueError:
            raise ValidationError("Invalid due_date format. Use YYYY-MM-DD.")

    action = CAPAAction(
        reference_number=ref_num,
        title=payload.title,
        description=payload.description,
        capa_type=CAPAType.CORRECTIVE,
        status=CAPAStatus.OPEN,
        priority=capa_priority,
        source_type=CAPASource.NCR,
        source_id=defect.id,
        source_reference=f"vehicle_defect:{defect.id}",
        created_by_id=current_user.id,
        due_date=due_date_parsed,
    )
    db.add(action)

    defect.status = "action_assigned"  # type: ignore[assignment]
    await db.flush()

    await _log_audit_trail(db, current_user, defect, "action_created")

    return {
        "id": action.id,
        "reference_number": action.reference_number,
        "title": action.title,
        "status": action.status.value if hasattr(action.status, "value") else str(action.status),
        "priority": action.priority.value if hasattr(action.priority, "value") else str(action.priority),
        "defect_id": defect.id,
    }


# ─── Audit trail + notifications helpers ─────────────────────────────


async def _log_audit_trail(
    db: AsyncSession,
    current_user: Any,
    defect: VehicleDefect,
    action: str,
) -> None:
    """Record an audit event for a vehicle defect operation."""
    try:
        priority_str = defect.priority.value if hasattr(defect.priority, "value") else str(defect.priority)
        status_str = defect.status.value if hasattr(defect.status, "value") else str(defect.status)
        await record_audit_event(
            db=db,
            event_type=f"vehicle_defect.{action}",
            entity_type="vehicle_defect",
            entity_id=str(defect.id),
            action=action,
            description=(
                f"Vehicle defect {action}: {priority_str} on {defect.check_field} "
                f"(vehicle {defect.vehicle_reg or 'unknown'})"
            ),
            payload={
                "priority": priority_str,
                "status": status_str,
                "check_field": defect.check_field,
                "pams_table": defect.pams_table,
                "vehicle_reg": defect.vehicle_reg,
            },
            actor_user_id=current_user.id,
        )
    except Exception:
        logger.warning("Failed to log audit trail for defect %s", defect.id, exc_info=True)


async def _create_p1_notification(
    db: AsyncSession,
    current_user: Any,
    defect: VehicleDefect,
) -> None:
    """Create an in-app notification when a P1 defect is flagged."""
    try:
        from src.domain.models.notification import Notification, NotificationPriority, NotificationType
        from src.domain.models.user import User

        admin_users = (
            (  # noqa: E712
                await db.execute(
                    select(User).where(
                        User.is_superuser == True,
                        User.tenant_id == current_user.tenant_id,
                    )
                )
            )
            .scalars()
            .all()
        )

        for user in admin_users:
            if user.id == current_user.id:
                continue
            notification = Notification(
                user_id=user.id,
                type=NotificationType.COMPLIANCE_ALERT,
                priority=NotificationPriority.CRITICAL,
                title=f"P1 Vehicle Defect: {defect.vehicle_reg or 'Unknown Vehicle'}",
                message=(
                    f"Critical defect flagged on {defect.check_field} — "
                    f"vehicle {defect.vehicle_reg or 'unknown'}. Immediate action required."
                ),
                entity_type="vehicle_defect",
                entity_id=str(defect.id),
                action_url="/vehicle-checklists",
                sender_id=current_user.id,
            )
            db.add(notification)
    except Exception:
        logger.warning("Failed to create P1 notification for defect %s", defect.id, exc_info=True)


# ─── Manual sync trigger (admin only) ───────────────────────────────


@router.post("/sync", status_code=status.HTTP_202_ACCEPTED)
async def trigger_sync(
    current_user: CurrentUser,
) -> dict[str, str]:
    """Manually trigger a PAMS sync (admin only)."""
    if not current_user.is_superuser:
        raise AuthorizationError("Admin access required")

    _require_pams()

    try:
        from src.infrastructure.tasks.pams_sync_tasks import sync_pams_checklists

        sync_pams_checklists.delay()
        return {"status": "sync_queued", "message": "PAMS sync task has been queued."}
    except Exception:
        logger.exception("Failed to queue PAMS sync task")
        raise DomainError("Failed to queue sync task")
