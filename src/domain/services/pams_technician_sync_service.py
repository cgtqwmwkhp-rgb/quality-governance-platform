"""Sync PAMS technicians_store rows into QGP engineers (read-only from PAMS).

Pure mapping helpers are unit-testable without a live MySQL connection.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator, Mapping, Sequence

from sqlalchemy import MetaData, create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from src.core.config import settings
from src.domain.exceptions import BadRequestError, ExternalServiceError
from src.domain.models.engineer import Engineer
from src.domain.models.user import User

logger = logging.getLogger(__name__)

PAMS_TECHNICIANS_TABLE = "technicians_store"


@dataclass(frozen=True)
class MappedTechnician:
    """Normalised PAMS technician row for upsert."""

    pams_id: int
    display_name: str
    job_title: str | None
    site: str | None
    employee_number: str | None
    is_active: bool
    email: str | None
    notes: str | None
    external_id: str


@dataclass
class SyncCounts:
    created: int = 0
    updated: int = 0
    deactivated: int = 0
    skipped: int = 0
    errors: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "created": self.created,
            "updated": self.updated,
            "deactivated": self.deactivated,
            "skipped": self.skipped,
            "errors": self.errors,
        }


def pams_technician_external_id(pams_id: int) -> str:
    return f"pams-tech-{pams_id}"


def _clean_str(value: object | None, *, max_len: int | None = None) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if max_len is not None:
        return text[:max_len]
    return text


def _coerce_bool(value: object | None) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return int(value) != 0
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _resolve_display_name(row: Mapping[str, Any]) -> str:
    display = _clean_str(row.get("display_name"), max_len=200)
    if display:
        return display
    first = _clean_str(row.get("firstname"))
    surname = _clean_str(row.get("surname"))
    parts = [part for part in (first, surname) if part]
    if parts:
        return " ".join(parts)[:200]
    short_name = _clean_str(row.get("short_name"), max_len=200)
    if short_name:
        return short_name
    pams_id = row.get("id")
    return f"Technician #{pams_id}" if pams_id is not None else "Unknown technician"


def map_pams_technician_row(row: Mapping[str, Any]) -> MappedTechnician | None:
    """Map a PAMS technicians_store row to engineer fields. Returns None when id missing."""
    raw_id = row.get("id")
    if raw_id is None:
        return None
    try:
        pams_id = int(raw_id)
    except (TypeError, ValueError):
        return None

    email = _clean_str(row.get("email"))
    notes_parts: list[str] = []
    if email:
        notes_parts.append(f"PAMS email: {email}")
    phone = _clean_str(row.get("phone"))
    if phone:
        notes_parts.append(f"PAMS phone: {phone}")

    short_name = _clean_str(row.get("short_name"))
    employee_number = str(pams_id)
    if short_name:
        employee_number = short_name[:50]

    return MappedTechnician(
        pams_id=pams_id,
        display_name=_resolve_display_name(row),
        job_title=_clean_str(row.get("role"), max_len=100),
        site=_clean_str(row.get("postcode"), max_len=200),
        employee_number=employee_number,
        is_active=_coerce_bool(row.get("active_technician")),
        email=email,
        notes="; ".join(notes_parts) if notes_parts else None,
        external_id=pams_technician_external_id(pams_id),
    )


def resolve_user_id_for_email(
    email: str | None,
    *,
    tenant_id: int,
    users_by_email: Mapping[str, User],
    user_ids_taken: set[int],
) -> int | None:
    """Link user_id when email matches same-tenant user and no other engineer owns it."""
    if not email:
        return None
    user = users_by_email.get(email.strip().lower())
    if user is None:
        return None
    if user.tenant_id != tenant_id or not user.is_active:
        return None
    if user.id in user_ids_taken:
        return None
    return user.id


def apply_mapped_technician_to_engineer(
    engineer: Engineer,
    mapped: MappedTechnician,
    *,
    user_id: int | None,
    preserve_existing_user: bool = True,
) -> None:
    """Apply mapped PAMS fields onto an Engineer ORM instance."""
    engineer.display_name = mapped.display_name
    engineer.job_title = mapped.job_title
    engineer.site = mapped.site
    engineer.employee_number = mapped.employee_number
    engineer.is_active = mapped.is_active
    engineer.pams_technician_id = mapped.pams_id
    engineer.external_id = mapped.external_id
    if mapped.notes:
        engineer.notes = mapped.notes
    if user_id is not None:
        engineer.user_id = user_id
    elif not preserve_existing_user:
        engineer.user_id = None


def resolve_tenant_id(explicit_tenant_id: int | None = None) -> int:
    tenant_id = explicit_tenant_id if explicit_tenant_id is not None else settings.default_tenant_id
    if tenant_id is None:
        raise BadRequestError(
            "tenant_id is required for PAMS technician sync — set DEFAULT_TENANT_ID or pass tenant_id"
        )
    return int(tenant_id)


def apply_tenant_guc_sync(db: Session, tenant_id: int) -> None:
    """Bind ``app.current_tenant_id`` on a sync Session (FORCE RLS on ``users``).

    The HTTP sync path uses ``SessionLocal()`` outside ``get_db``'s async
    after_begin listener, so without this bind the ``users`` query is empty
    under FORCE RLS and any later RLS-protected writes fail closed / 500.
    No-ops on non-PostgreSQL so unit tests keep working.
    """
    try:
        bind = db.get_bind()
        dialect_name = getattr(getattr(bind, "dialect", None), "name", None)
        if dialect_name is not None and dialect_name != "postgresql":
            return
    except Exception:
        pass
    try:
        db.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": str(int(tenant_id))},
        )
    except Exception:
        logger.debug(
            "apply_tenant_guc_sync skipped (non-PostgreSQL or set_config unavailable)",
            exc_info=True,
        )


@contextmanager
def _row_savepoint(db: Session) -> Iterator[None]:
    """Isolate a single upsert so a flush/integrity failure cannot poison the session."""
    if hasattr(db, "begin_nested"):
        try:
            with db.begin_nested():
                yield
            return
        except NotImplementedError:
            # Some test doubles / dialects lack SAVEPOINT support.
            pass
    yield


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


def fetch_pams_technicians() -> list[dict[str, Any]]:
    """Read all rows from PAMS technicians_store (read-only)."""
    engine = _build_pams_engine()
    try:
        meta = MetaData()
        meta.reflect(bind=engine, only=[PAMS_TECHNICIANS_TABLE])
        if PAMS_TECHNICIANS_TABLE not in meta.tables:
            logger.warning("PAMS table %s not found", PAMS_TECHNICIANS_TABLE)
            return []
        tbl = meta.tables[PAMS_TECHNICIANS_TABLE]
        with engine.connect() as conn:
            result = conn.execute(tbl.select())
            return [dict(row._mapping) for row in result]
    except BadRequestError:
        raise
    except Exception as exc:
        logger.exception("PAMS technicians_store read failed")
        raise ExternalServiceError(
            "Unable to read PAMS technicians_store — check PAMS_DATABASE_URL / PAMS_SSL_CA connectivity",
            details={"cause": type(exc).__name__},
        ) from exc
    finally:
        engine.dispose()


def _load_pams_rows(rows: Sequence[Mapping[str, Any]] | None) -> list[Mapping[str, Any]]:
    try:
        return list(rows) if rows is not None else fetch_pams_technicians()
    except (BadRequestError, ExternalServiceError):
        raise
    except Exception as exc:
        logger.exception("PAMS technician fetch failed before upsert")
        raise ExternalServiceError(
            "PAMS technician sync failed while fetching source rows",
            details={"cause": type(exc).__name__},
        ) from exc


def _upsert_mapped_technician(
    db: Session,
    *,
    mapped: MappedTechnician,
    tenant_id: int,
    by_pams_id: dict[int, Engineer],
    by_external_id: dict[str, Engineer],
    users_by_email: dict[str, User],
    user_ids_taken: set[int],
    counts: SyncCounts,
) -> None:
    created_this_row = False
    on_create_path = False
    linked_user_id: int | None = None
    try:
        with _row_savepoint(db):
            engineer = by_pams_id.get(mapped.pams_id) or by_external_id.get(mapped.external_id)
            linked_user_id = resolve_user_id_for_email(
                mapped.email,
                tenant_id=tenant_id,
                users_by_email=users_by_email,
                user_ids_taken=user_ids_taken,
            )

            if engineer is None:
                on_create_path = True
                if linked_user_id is not None:
                    user_ids_taken.add(linked_user_id)
                engineer = Engineer(
                    tenant_id=tenant_id,
                    user_id=linked_user_id,
                    display_name=mapped.display_name,
                    job_title=mapped.job_title,
                    site=mapped.site,
                    employee_number=mapped.employee_number,
                    is_active=mapped.is_active,
                    notes=mapped.notes,
                    pams_technician_id=mapped.pams_id,
                    external_id=mapped.external_id,
                )
                db.add(engineer)
                by_pams_id[mapped.pams_id] = engineer
                by_external_id[mapped.external_id] = engineer
                created_this_row = True
                counts.created += 1
                return

            had_user = engineer.user_id is not None
            apply_mapped_technician_to_engineer(
                engineer,
                mapped,
                user_id=linked_user_id,
                preserve_existing_user=had_user and linked_user_id is None,
            )
            if linked_user_id is not None and engineer.user_id == linked_user_id:
                user_ids_taken.add(linked_user_id)
            counts.updated += 1
    except Exception:
        logger.exception("Failed to upsert PAMS technician id=%s", mapped.pams_id)
        counts.errors += 1
        if on_create_path:
            if created_this_row:
                by_pams_id.pop(mapped.pams_id, None)
                by_external_id.pop(mapped.external_id, None)
                counts.created = max(0, counts.created - 1)
            if linked_user_id is not None:
                user_ids_taken.discard(linked_user_id)


def _deactivate_missing_engineers(
    existing_engineers: Sequence[Engineer],
    seen_pams_ids: set[int],
    counts: SyncCounts,
) -> None:
    for engineer in existing_engineers:
        if engineer.pams_technician_id is None:
            continue
        if engineer.pams_technician_id in seen_pams_ids:
            continue
        if engineer.is_active:
            engineer.is_active = False
            counts.deactivated += 1


def _commit_sync(db: Session, *, tenant_id: int) -> None:
    try:
        db.commit()
    except SQLAlchemyError as exc:
        logger.exception("PAMS technician sync commit failed tenant_id=%s", tenant_id)
        try:
            db.rollback()
        except Exception:
            logger.debug("rollback after sync commit failure also failed", exc_info=True)
        raise BadRequestError(
            "PAMS technician sync could not be saved — check schema (pams_technician_id migration) and tenant_id",
            details={"cause": type(exc).__name__, "tenant_id": tenant_id},
        ) from exc


def sync_pams_technicians(
    db: Session,
    *,
    tenant_id: int | None = None,
    rows: Sequence[Mapping[str, Any]] | None = None,
) -> SyncCounts:
    """Upsert PAMS technicians into engineers for the given tenant."""
    resolved_tenant_id = resolve_tenant_id(tenant_id)
    apply_tenant_guc_sync(db, resolved_tenant_id)
    counts = SyncCounts()
    pams_rows = _load_pams_rows(rows)

    users = db.query(User).filter(User.tenant_id == resolved_tenant_id, User.is_active.is_(True)).all()
    users_by_email = {email: user for user in users if (email := (user.email or "").strip().lower())}

    existing_engineers = db.query(Engineer).filter(Engineer.tenant_id == resolved_tenant_id).all()
    by_pams_id = {eng.pams_technician_id: eng for eng in existing_engineers if eng.pams_technician_id is not None}
    by_external_id = {eng.external_id: eng for eng in existing_engineers if eng.external_id}
    user_ids_taken = {eng.user_id for eng in existing_engineers if eng.user_id is not None}
    seen_pams_ids: set[int] = set()

    for raw_row in pams_rows:
        mapped = map_pams_technician_row(raw_row)
        if mapped is None:
            counts.skipped += 1
            continue
        seen_pams_ids.add(mapped.pams_id)
        _upsert_mapped_technician(
            db,
            mapped=mapped,
            tenant_id=resolved_tenant_id,
            by_pams_id=by_pams_id,
            by_external_id=by_external_id,
            users_by_email=users_by_email,
            user_ids_taken=user_ids_taken,
            counts=counts,
        )

    _deactivate_missing_engineers(existing_engineers, seen_pams_ids, counts)
    _commit_sync(db, tenant_id=resolved_tenant_id)
    return counts
