"""Sync PAMS technicians_store rows into QGP engineers (read-only from PAMS).

Pure mapping helpers are unit-testable without a live MySQL connection.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import Session

from src.core.config import settings
from src.domain.exceptions import BadRequestError
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
    finally:
        engine.dispose()


def sync_pams_technicians(
    db: Session,
    *,
    tenant_id: int | None = None,
    rows: Sequence[Mapping[str, Any]] | None = None,
) -> SyncCounts:
    """Upsert PAMS technicians into engineers for the given tenant."""
    resolved_tenant_id = resolve_tenant_id(tenant_id)
    counts = SyncCounts()
    pams_rows = list(rows) if rows is not None else fetch_pams_technicians()

    users = db.query(User).filter(User.tenant_id == resolved_tenant_id, User.is_active.is_(True)).all()
    users_by_email = {user.email.strip().lower(): user for user in users if user.email}

    existing_engineers = db.query(Engineer).filter(Engineer.tenant_id == resolved_tenant_id).all()
    by_pams_id = {
        eng.pams_technician_id: eng for eng in existing_engineers if eng.pams_technician_id is not None
    }
    by_external_id = {eng.external_id: eng for eng in existing_engineers}
    user_ids_taken = {eng.user_id for eng in existing_engineers if eng.user_id is not None}
    seen_pams_ids: set[int] = set()

    for raw_row in pams_rows:
        mapped = map_pams_technician_row(raw_row)
        if mapped is None:
            counts.skipped += 1
            continue
        seen_pams_ids.add(mapped.pams_id)

        try:
            engineer = by_pams_id.get(mapped.pams_id) or by_external_id.get(mapped.external_id)
            linked_user_id = resolve_user_id_for_email(
                mapped.email,
                tenant_id=resolved_tenant_id,
                users_by_email=users_by_email,
                user_ids_taken=user_ids_taken,
            )

            if engineer is None:
                if linked_user_id is not None:
                    user_ids_taken.add(linked_user_id)
                engineer = Engineer(
                    tenant_id=resolved_tenant_id,
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
                counts.created += 1
            else:
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

    for engineer in existing_engineers:
        if engineer.pams_technician_id is None:
            continue
        if engineer.pams_technician_id in seen_pams_ids:
            continue
        if engineer.is_active:
            engineer.is_active = False
            counts.deactivated += 1

    db.commit()
    return counts
