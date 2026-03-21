"""Celery tasks for PAMS Van Checklist synchronisation.

Periodically copies rows from the external PAMS MySQL database into
local PostgreSQL cache tables.  On each sync, pass/fail columns are
scanned and draft defect records are auto-created for governance review.
"""

import logging
from datetime import datetime, timezone
from typing import Any

from src.infrastructure.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _sync_table(
    table_name: str,
    cache_model_cls: type,
    sync_log_cls: type,
    defect_cls: type,
    session_local_cls: type,
) -> dict[str, int]:
    """Synchronise a single PAMS table into the local cache.

    Returns a dict with rows_synced and defects_detected counts.
    """
    from sqlalchemy import MetaData, create_engine, select, text
    from sqlalchemy.orm import Session

    from src.core.config import settings

    if not settings.pams_database_url:
        logger.info("PAMS_DATABASE_URL not set — skipping %s sync", table_name)
        return {"rows_synced": 0, "defects_detected": 0}

    import os

    sync_url = settings.pams_database_url.replace("+aiomysql", "+pymysql")
    connect_args: dict = {}
    if settings.pams_ssl_ca:
        system_ca = "/etc/ssl/certs/ca-certificates.crt"
        ca_file = system_ca if os.path.exists(system_ca) else settings.pams_ssl_ca
        connect_args["ssl"] = {"ca": ca_file}
    pams_engine = create_engine(sync_url, pool_pre_ping=True, connect_args=connect_args)

    rows_synced = 0
    defects_detected = 0

    try:
        meta = MetaData()
        meta.reflect(bind=pams_engine, only=[table_name])
        if table_name not in meta.tables:
            logger.warning("PAMS table %s not found", table_name)
            return {"rows_synced": 0, "defects_detected": 0}

        tbl = meta.tables[table_name]
        pk_cols = list(tbl.primary_key.columns)
        pk_col = pk_cols[0] if pk_cols else list(tbl.columns)[0]

        with pams_engine.connect() as pams_conn:
            result = pams_conn.execute(tbl.select())
            pams_rows = result.mappings().all()

        db: Session = session_local_cls()
        try:
            all_pams_ids = [
                int({k: _safe_serialize(v) for k, v in dict(r).items()}.get(pk_col.name, 0)) for r in pams_rows
            ]
            existing_cache_rows = (
                (db.query(cache_model_cls).filter(cache_model_cls.pams_id.in_(all_pams_ids)).all())
                if all_pams_ids
                else []
            )
            cache_index = {row.pams_id: row for row in existing_cache_rows}

            for row in pams_rows:
                row_dict = {k: _safe_serialize(v) for k, v in dict(row).items()}
                pams_id = int(row_dict.get(pk_col.name, 0))

                existing = cache_index.get(pams_id)
                if existing:
                    existing.raw_data = row_dict
                    existing.synced_at = _now()
                else:
                    cache_row = cache_model_cls(
                        pams_id=pams_id,
                        raw_data=row_dict,
                        synced_at=_now(),
                    )
                    db.add(cache_row)

                rows_synced += 1

                detected = _auto_detect_defects(row_dict, pams_id, table_name, defect_cls, db)
                defects_detected += detected

                _upsert_vehicle_registry(row_dict, table_name, defect_cls, db)

            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    except Exception:
        logger.exception("PAMS sync failed for %s", table_name)
        raise
    finally:
        pams_engine.dispose()

    return {"rows_synced": rows_synced, "defects_detected": defects_detected}


def _parse_datetime(val: Any) -> "datetime | None":
    """Best-effort parse of a datetime value from PAMS raw data."""
    if val is None:
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo else val.replace(tzinfo=timezone.utc)
    s = str(val).strip()
    if not s:
        return None
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y"):
        try:
            dt = datetime.strptime(s, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _extract_vehicle_reg(row_dict: dict[str, Any]) -> str:
    """Extract the vehicle registration from a PAMS row, normalised."""
    return str(
        row_dict.get("vanReg")
        or row_dict.get("VehicleReg")
        or row_dict.get("vanID")
        or row_dict.get("registration")
        or row_dict.get("reg")
        or ""
    ).strip()


def _upsert_vehicle_registry(
    row_dict: dict[str, Any],
    table_name: str,
    defect_cls: type,
    db: Any,
) -> None:
    """Create or update a VehicleRegistry row from a PAMS checklist record."""
    from src.domain.models.vehicle_registry import ComplianceStatus, FleetStatus, VehicleRegistry

    vehicle_reg = _extract_vehicle_reg(row_dict)
    if not vehicle_reg:
        return

    entry = db.query(VehicleRegistry).filter(VehicleRegistry.vehicle_reg == vehicle_reg).first()
    if entry is None:
        entry = VehicleRegistry(
            vehicle_reg=vehicle_reg,
            fleet_status=FleetStatus.ACTIVE,
            compliance_status=ComplianceStatus.COMPLIANT,
        )
        db.add(entry)

    pams_van_id = str(row_dict.get("vanID") or "").strip()
    if pams_van_id:
        entry.pams_van_id = pams_van_id

    check_dt = _parse_datetime(row_dict.get("startTimeDate") or row_dict.get("DateSubmitted") or row_dict.get("date"))

    if table_name == "vanchecklist":
        if check_dt and (entry.last_daily_check_at is None or check_dt > entry.last_daily_check_at):
            entry.last_daily_check_at = check_dt
            all_pass = not any(
                str(v).strip().lower() in FAIL_VALUES
                for k, v in row_dict.items()
                if k not in _SKIP_KEYS_FOR_PASS and v is not None
            )
            entry.last_daily_check_pass = all_pass
    elif table_name == "vanchecklistmonthly":
        if check_dt and (entry.last_monthly_check_at is None or check_dt > entry.last_monthly_check_at):
            entry.last_monthly_check_at = check_dt

    road_tax = _parse_datetime(row_dict.get("roadTaxExpiryDate"))
    if road_tax:
        entry.road_tax_expiry = road_tax
    fire_ext = _parse_datetime(row_dict.get("fireExtinguisherExpiryDate"))
    if fire_ext:
        entry.fire_extinguisher_expiry = fire_ext
    tooling = _parse_datetime(row_dict.get("toolingCalibrationExpiryDate"))
    if tooling:
        entry.tooling_calibration_expiry = tooling

    open_critical = (
        db.query(defect_cls)
        .filter(
            defect_cls.vehicle_reg == vehicle_reg,
            defect_cls.priority.in_(["P1", "P2"]),
            defect_cls.status.in_(["open", "auto_detected", "acknowledged", "action_assigned"]),
        )
        .count()
    )
    if open_critical > 0:
        entry.compliance_status = ComplianceStatus.NON_COMPLIANT
    elif entry.compliance_status == ComplianceStatus.NON_COMPLIANT:
        entry.compliance_status = ComplianceStatus.COMPLIANT


_SKIP_KEYS_FOR_PASS = {
    "id",
    "ID",
    "inc_id",
    "created_at",
    "updated_at",
    "date",
    "driver",
    "vehicle",
    "registration",
    "reg",
    "VehicleReg",
    "DriverName",
    "DateSubmitted",
    "userName",
    "vanID",
    "vanReg",
    "startTimeDate",
    "endTimeDate",
    "technician",
    "comments",
    "notes",
    "mileage",
    "Mileage",
    "bodyWorkDamage",
    "defects",
    "uploaded",
    "roadTaxExpiryDate",
    "toolingCalibrationExpiryDate",
    "fireExtinguisherExpiryDate",
}

FAIL_VALUES = {"fail", "no", "0", "false", "failed", "n"}


def _auto_detect_defects(
    row_dict: dict[str, Any],
    pams_id: int,
    table_name: str,
    defect_cls: type,
    db: Any,
) -> int:
    """Scan a row for pass/fail column values and auto-create draft defects."""
    pams_table_label = "daily" if table_name == "vanchecklist" else "monthly"
    detected = 0

    skip_keys = {
        "id",
        "ID",
        "inc_id",
        "created_at",
        "updated_at",
        "date",
        "driver",
        "vehicle",
        "registration",
        "reg",
        "VehicleReg",
        "DriverName",
        "DateSubmitted",
        "userName",
        "vanID",
        "vanReg",
        "startTimeDate",
        "endTimeDate",
        "technician",
        "comments",
        "notes",
        "mileage",
        "Mileage",
        "bodyWorkDamage",
        "defects",
        "uploaded",
        "roadTaxExpiryDate",
        "toolingCalibrationExpiryDate",
        "fireExtinguisherExpiryDate",
    }

    for col_name, col_value in row_dict.items():
        if col_name in skip_keys:
            continue
        str_val = str(col_value).strip().lower() if col_value is not None else ""
        if str_val not in FAIL_VALUES:
            continue

        existing_defect = (
            db.query(defect_cls)
            .filter(
                defect_cls.pams_table == pams_table_label,
                defect_cls.pams_record_id == pams_id,
                defect_cls.check_field == col_name,
                defect_cls.status.in_(["open", "auto_detected", "acknowledged", "action_assigned"]),
            )
            .first()
        )
        if existing_defect:
            continue

        vehicle_reg = str(
            row_dict.get("vanID")
            or row_dict.get("vanReg")
            or row_dict.get("registration")
            or row_dict.get("reg")
            or row_dict.get("VehicleReg")
            or ""
        ).strip()

        defect = defect_cls(
            pams_table=pams_table_label,
            pams_record_id=pams_id,
            check_field=col_name,
            check_value=str(col_value),
            priority="P3",
            status="auto_detected",
            notes="Auto-detected during PAMS sync",
            vehicle_reg=vehicle_reg,
        )
        db.add(defect)
        db.flush()
        detected += 1

        _auto_create_capa_for_defect(defect, vehicle_reg, col_name, str(col_value), db)

    return detected


def _auto_create_capa_for_defect(
    defect: Any,
    vehicle_reg: str,
    check_field: str,
    check_value: str,
    db: Any,
) -> None:
    """Auto-create a CAPA action for P1/P2 defects during sync."""
    priority = getattr(defect, "priority", "P3")
    if priority not in ("P1", "P2"):
        return
    try:
        from src.domain.services.vehicle_capa_pipeline import create_capa_from_defect_sync

        create_capa_from_defect_sync(
            defect_id=defect.id,
            defect_priority=priority,
            vehicle_reg=vehicle_reg,
            check_field=check_field,
            check_value=check_value,
            db=db,
        )
    except Exception:
        logger.warning("Failed to auto-create CAPA for defect %s", defect.id, exc_info=True)


def _safe_serialize(v: Any) -> Any:
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, bytes):
        return v.decode("utf-8", errors="replace")
    return v


@celery_app.task(
    bind=True,
    name="src.infrastructure.tasks.pams_sync_tasks.sync_pams_checklists",
    queue="default",
    max_retries=2,
    soft_time_limit=300,
)
def sync_pams_checklists(self) -> dict[str, Any]:  # type: ignore[override]
    """Celery task: sync both PAMS tables and log results."""
    from src.domain.models.pams_cache import PAMSSyncLog, PAMSVanChecklistCache, PAMSVanChecklistMonthlyCache
    from src.domain.models.vehicle_defect import VehicleDefect
    from src.infrastructure.database import SessionLocal

    results: dict[str, Any] = {}

    for table_name, cache_cls in [
        ("vanchecklist", PAMSVanChecklistCache),
        ("vanchecklistmonthly", PAMSVanChecklistMonthlyCache),
    ]:
        log_entry = PAMSSyncLog(
            table_name=table_name,
            started_at=_now(),
        )
        db = SessionLocal()
        try:
            db.add(log_entry)
            db.flush()

            stats = _sync_table(table_name, cache_cls, PAMSSyncLog, VehicleDefect, SessionLocal)

            log_entry.rows_synced = stats["rows_synced"]
            log_entry.defects_detected = stats["defects_detected"]
            log_entry.status = "success"
            log_entry.completed_at = _now()
            db.commit()

            results[table_name] = stats
            logger.info(
                "PAMS sync complete: %s — %d rows, %d defects detected",
                table_name,
                stats["rows_synced"],
                stats["defects_detected"],
            )
        except Exception as exc:
            log_entry.status = "error"
            log_entry.error_message = str(exc)[:500]
            log_entry.completed_at = _now()
            try:
                db.commit()
            except Exception:
                db.rollback()
            results[table_name] = {"error": str(exc)}
            logger.exception("PAMS sync error for %s", table_name)
        finally:
            db.close()

    _send_p1_notifications()

    return results


def _send_p1_notifications() -> None:
    """Create in-app notifications for new auto-detected P1-eligible defects."""
    try:
        from sqlalchemy import select

        from src.domain.models.notification import Notification, NotificationPriority, NotificationType
        from src.domain.models.user import User
        from src.domain.models.vehicle_defect import VehicleDefect
        from src.infrastructure.database import SessionLocal

        db = SessionLocal()
        try:
            auto_defects = db.query(VehicleDefect).filter(VehicleDefect.status == "auto_detected").all()
            if not auto_defects:
                return

            admin_users = db.query(User).filter(User.is_superuser == True).all()  # noqa: E712
            if not admin_users:
                return

            for user in admin_users:
                existing = (
                    db.query(Notification)
                    .filter(
                        Notification.user_id == user.id,
                        Notification.entity_type == "vehicle_defect_batch",
                        Notification.is_read == False,  # noqa: E712
                    )
                    .first()
                )
                if existing:
                    continue

                notification = Notification(
                    user_id=user.id,
                    type=NotificationType.COMPLIANCE_ALERT,
                    priority=NotificationPriority.HIGH,
                    title="Vehicle Defects Detected",
                    message=f"{len(auto_defects)} vehicle checklist defect(s) require review.",
                    entity_type="vehicle_defect_batch",
                    action_url="/vehicle-checklists",
                )
                db.add(notification)

            db.commit()
        except Exception:
            db.rollback()
            logger.warning("Failed to send P1 notifications", exc_info=True)
        finally:
            db.close()
    except Exception:
        logger.warning("P1 notification import error", exc_info=True)
