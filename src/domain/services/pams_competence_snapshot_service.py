"""Read-only snapshot of PAMS engineer competence into QGP Postgres (CB-PR1).

Never writes PAMS. Join is ``pams_technician_id`` then exact email. No fuzzy name.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session

from src.core.config import settings
from src.domain.exceptions import BadRequestError, ExternalServiceError
from src.domain.models.engineer import Engineer
from src.domain.models.pams_cache import PamsCompetenceCurrent, PamsCompetenceRow, PamsCompetenceSnapshot
from src.domain.models.user import User
from src.domain.services.pams_technician_sync_service import apply_tenant_guc_sync, resolve_tenant_id

logger = logging.getLogger(__name__)

PAMS_COMPETENCE_VIEW = "vw_plantex_engineercompetence"
# Constant SQL — view name is not user input (Bandit B608).
PAMS_COMPETENCE_SELECT = text("SELECT * FROM vw_plantex_engineercompetence")
STALE_AFTER = timedelta(hours=25)
SOURCE_NAME = PAMS_COMPETENCE_VIEW


@dataclass(frozen=True)
class MappedCompetenceRow:
    pams_technician_id: int | None
    engineer_name: str | None
    email: str | None
    depot: str | None
    characteristic_key: str
    thorough_exam: bool | None
    raw_data: dict[str, Any]


@dataclass
class SnapshotCounts:
    fetched: int = 0
    stored: int = 0
    skipped: int = 0
    mapped_engineers: int = 0
    snapshot_id: int | None = None
    status: str = "success"

    def as_dict(self) -> dict[str, Any]:
        return {
            "fetched": self.fetched,
            "stored": self.stored,
            "skipped": self.skipped,
            "mapped_engineers": self.mapped_engineers,
            "snapshot_id": self.snapshot_id,
            "status": self.status,
        }


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _clean_str(value: object | None, *, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    if isinstance(value, (bytes, bytearray)):
        if not value:
            return None
        try:
            text_value = value.decode("utf-8", errors="ignore").strip()
        except Exception:
            return None
    else:
        text_value = str(value).strip()
    if not text_value:
        return None
    if max_len is not None:
        return text_value[:max_len]
    return text_value


def _row_get(row: Mapping[str, Any], *names: str) -> object | None:
    lower = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        if name.lower() in lower:
            return lower[name.lower()]
    return None


def _coerce_optional_int(value: object | None) -> int | None:
    if value is None or isinstance(value, bool) or value == "":
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        return int(text)
    except (TypeError, ValueError):
        return None


def _coerce_optional_bool(value: object | None) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) != 0
    text_value = str(value).strip().lower()
    if text_value in {"1", "true", "yes", "y"}:
        return True
    if text_value in {"0", "false", "no", "n"}:
        return False
    return None


def map_competence_row(row: Mapping[str, Any]) -> MappedCompetenceRow | None:
    """Map one PAMS competence view row. Skip rows with no characteristic."""
    characteristic = _clean_str(
        _row_get(row, "characteristic", "skillname", "skill_name", "skill"),
        max_len=80,
    )
    if not characteristic:
        return None

    raw = {str(k): _json_safe(v) for k, v in row.items()}
    return MappedCompetenceRow(
        pams_technician_id=_coerce_optional_int(_row_get(row, "technician_id", "technicianid", "pams_technician_id")),
        engineer_name=_clean_str(_row_get(row, "engineername", "engineer_name", "display_name", "name"), max_len=255),
        email=_clean_str(_row_get(row, "email"), max_len=255),
        depot=_clean_str(_row_get(row, "depot", "postcode"), max_len=32),
        characteristic_key=characteristic,
        thorough_exam=_coerce_optional_bool(_row_get(row, "thorough_exam", "thoroughexam")),
        raw_data=raw,
    )


def _json_safe(value: object) -> object:
    if isinstance(value, (bytes, bytearray)):
        if not value:
            return None
        try:
            return value.decode("utf-8", errors="ignore")
        except Exception:
            return None
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def resolve_engineer_id(
    mapped: MappedCompetenceRow,
    *,
    by_pams_id: Mapping[int, Engineer],
    by_email: Mapping[str, Engineer],
) -> int | None:
    """Exact join only: PAMS technician id, then email. Never a name match."""
    if mapped.pams_technician_id is not None:
        engineer = by_pams_id.get(mapped.pams_technician_id)
        if engineer is not None:
            return engineer.id
    if mapped.email:
        engineer = by_email.get(mapped.email.strip().lower())
        if engineer is not None:
            return engineer.id
    return None


def _build_pams_engine():
    if not settings.pams_database_url:
        raise BadRequestError("PAMS_DATABASE_URL is not configured")
    sync_url = settings.pams_database_url.replace("+aiomysql", "+pymysql")
    connect_args: dict[str, Any] = {}
    if settings.pams_ssl_ca:
        system_ca = "/etc/ssl/certs/ca-certificates.crt"
        ca_file = system_ca if os.path.exists(system_ca) else settings.pams_ssl_ca
        connect_args["ssl"] = {"ca": ca_file}
    return create_engine(sync_url, pool_pre_ping=True, connect_args=connect_args)


def fetch_pams_competence_rows() -> list[dict[str, Any]]:
    """Raw SELECT of the competence view — do not reflect views."""
    engine = _build_pams_engine()
    try:
        with engine.connect() as conn:
            result = conn.execute(PAMS_COMPETENCE_SELECT)
            return [dict(row._mapping) for row in result]
    except BadRequestError:
        raise
    except Exception as exc:
        logger.exception("PAMS %s read failed", PAMS_COMPETENCE_VIEW)
        raise ExternalServiceError(
            "Unable to read PAMS competence view — check PAMS_DATABASE_URL / PAMS_SSL_CA",
            details={"cause": type(exc).__name__, "view": PAMS_COMPETENCE_VIEW},
        ) from exc
    finally:
        engine.dispose()


def _load_source_rows(rows: Sequence[Mapping[str, Any]] | None) -> list[Mapping[str, Any]]:
    if rows is not None:
        return [dict(row) for row in rows]
    return list(fetch_pams_competence_rows())


def _engineer_lookups(db: Session, tenant_id: int) -> tuple[dict[int, Engineer], dict[str, Engineer]]:
    engineers = list(db.scalars(select(Engineer).where(Engineer.tenant_id == tenant_id)).all())
    by_pams_id = {eng.pams_technician_id: eng for eng in engineers if eng.pams_technician_id is not None}
    by_user_id = {eng.user_id: eng for eng in engineers if eng.user_id is not None}
    users = list(db.scalars(select(User).where(User.tenant_id == tenant_id)).all())
    by_email: dict[str, Engineer] = {}
    for user in users:
        email = (user.email or "").strip().lower()
        if not email or user.id not in by_user_id:
            continue
        by_email[email] = by_user_id[user.id]
    return by_pams_id, by_email


def sync_pams_competence_snapshot(
    db: Session,
    *,
    tenant_id: int | None = None,
    rows: Sequence[Mapping[str, Any]] | None = None,
) -> SnapshotCounts:
    """Write a new snapshot and flip the current pointer only after rows are intact."""
    resolved_tenant = resolve_tenant_id(tenant_id)
    apply_tenant_guc_sync(db, resolved_tenant)
    counts = SnapshotCounts()
    snapshot = PamsCompetenceSnapshot(
        tenant_id=resolved_tenant,
        status="loading",
        source_name=SOURCE_NAME,
        row_count=0,
        started_at=_now(),
    )
    db.add(snapshot)
    db.flush()
    counts.snapshot_id = snapshot.id

    try:
        source = _load_source_rows(rows)
        counts.fetched = len(source)
        by_pams_id, by_email = _engineer_lookups(db, resolved_tenant)
        mapped_engineer_ids: set[int] = set()
        stored = 0
        for raw in source:
            mapped = map_competence_row(raw)
            if mapped is None:
                counts.skipped += 1
                continue
            engineer_id = resolve_engineer_id(mapped, by_pams_id=by_pams_id, by_email=by_email)
            if engineer_id is not None:
                mapped_engineer_ids.add(engineer_id)
            db.add(
                PamsCompetenceRow(
                    snapshot_id=snapshot.id,
                    pams_technician_id=mapped.pams_technician_id,
                    engineer_id=engineer_id,
                    engineer_name=mapped.engineer_name,
                    email=mapped.email,
                    depot=mapped.depot,
                    characteristic_key=mapped.characteristic_key,
                    thorough_exam=mapped.thorough_exam,
                    raw_data=mapped.raw_data,
                )
            )
            stored += 1
        db.flush()
        snapshot.row_count = stored
        snapshot.status = "ready"
        snapshot.completed_at = _now()
        snapshot.error_message = None
        counts.stored = stored
        counts.mapped_engineers = len(mapped_engineer_ids)

        current = db.get(PamsCompetenceCurrent, resolved_tenant)
        if current is None:
            db.add(
                PamsCompetenceCurrent(
                    tenant_id=resolved_tenant,
                    snapshot_id=snapshot.id,
                    updated_at=_now(),
                )
            )
        else:
            current.snapshot_id = snapshot.id
            current.updated_at = _now()
        db.commit()
        logger.info(
            "pams_competence_snapshot tenant_id=%s snapshot_id=%s stored=%s mapped=%s",
            resolved_tenant,
            snapshot.id,
            stored,
            counts.mapped_engineers,
        )
        return counts
    except Exception as exc:
        db.rollback()
        failed = db.get(PamsCompetenceSnapshot, snapshot.id)
        if failed is not None:
            failed.status = "failed"
            failed.error_message = str(exc)[:500]
            failed.completed_at = _now()
            try:
                db.commit()
            except Exception:
                db.rollback()
        counts.status = "error"
        logger.exception("PAMS competence snapshot failed tenant_id=%s", resolved_tenant)
        if isinstance(exc, (BadRequestError, ExternalServiceError)):
            raise
        raise ExternalServiceError(
            "PAMS competence snapshot failed",
            details={"cause": type(exc).__name__},
        ) from exc


def snapshot_stale_reason(
    completed_at: datetime | None,
    *,
    now: datetime | None = None,
    horizon: timedelta = STALE_AFTER,
) -> str | None:
    if completed_at is None:
        return "No completed PAMS competence snapshot."
    clock = now or _now()
    completed = completed_at.replace(tzinfo=None) if completed_at.tzinfo else completed_at
    if clock - completed > horizon:
        return "PAMS snapshot is stale — issued skills may be out of date."
    return None


def load_current_snapshot(db: Session, tenant_id: int) -> tuple[PamsCompetenceSnapshot | None, list[PamsCompetenceRow]]:
    pointer = db.get(PamsCompetenceCurrent, tenant_id)
    if pointer is None:
        return None, []
    snapshot = db.get(PamsCompetenceSnapshot, pointer.snapshot_id)
    if snapshot is None or snapshot.tenant_id != tenant_id:
        return None, []
    rows = list(db.scalars(select(PamsCompetenceRow).where(PamsCompetenceRow.snapshot_id == snapshot.id)).all())
    return snapshot, rows


async def load_current_snapshot_async(
    db: Any, tenant_id: int
) -> tuple[PamsCompetenceSnapshot | None, list[PamsCompetenceRow]]:
    pointer = await db.get(PamsCompetenceCurrent, tenant_id)
    if pointer is None:
        return None, []
    snapshot = await db.get(PamsCompetenceSnapshot, pointer.snapshot_id)
    if snapshot is None or snapshot.tenant_id != tenant_id:
        return None, []
    result = await db.scalars(select(PamsCompetenceRow).where(PamsCompetenceRow.snapshot_id == snapshot.id))
    return snapshot, list(result.all())
