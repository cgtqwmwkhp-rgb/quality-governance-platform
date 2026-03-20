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

    sync_url = settings.pams_database_url.replace("+aiomysql", "+pymysql")
    connect_args: dict = {}
    if settings.pams_ssl_ca:
        connect_args["ssl_ca"] = settings.pams_ssl_ca
        connect_args["ssl_verify_cert"] = True
        connect_args["ssl_verify_identity"] = True
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
            for row in pams_rows:
                row_dict = {k: _safe_serialize(v) for k, v in dict(row).items()}
                pams_id = int(row_dict.get(pk_col.name, 0))

                existing = db.query(cache_model_cls).filter(cache_model_cls.pams_id == pams_id).first()

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
        detected += 1

    return detected


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
