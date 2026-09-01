"""Plant and statutory competence change requests (CB-PR2).

Never writes PAMS. Row first, email second. One open request per cell.
Auto-close when the observed source matches the requested action.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.core.config import settings
from src.domain.exceptions import BadRequestError, ConflictError, NotFoundError
from src.domain.models.competence_change_request import CompetenceChangeRequest
from src.domain.models.engineer import Engineer
from src.domain.models.pams_cache import PamsCompetenceCurrent, PamsCompetenceRow

logger = logging.getLogger(__name__)

Family = Literal["pams", "atlas"]
Action = Literal["issue", "revoke"]
STATUS_OPEN = "open"
STATUS_CLOSED_OBSERVED = "closed_observed"
PLANT_MAILBOX_DEFAULT = "IT-Admin@plantexpand.com"
STATUTORY_MAILBOX_UNSET = "HR Advisor mailbox is not configured."
ONE_OPEN = "An open change request already exists for this cell."


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def mailbox_for(family: Family) -> str:
    if family == "pams":
        mailbox = (settings.competence_plant_change_mailbox or PLANT_MAILBOX_DEFAULT).strip()
        if not mailbox:
            raise BadRequestError("Plant change mailbox is not configured.")
        return mailbox
    mailbox = (settings.competence_statutory_change_mailbox or "").strip()
    if not mailbox:
        raise BadRequestError(STATUTORY_MAILBOX_UNSET)
    return mailbox


def issued_pairs_from_snapshot(db: Session, tenant_id: int) -> set[tuple[int, str]]:
    pointer = db.get(PamsCompetenceCurrent, tenant_id)
    if pointer is None:
        return set()
    rows = db.scalars(
        select(PamsCompetenceRow).where(
            PamsCompetenceRow.snapshot_id == pointer.snapshot_id,
            PamsCompetenceRow.engineer_id.is_not(None),
        )
    ).all()
    return {(int(row.engineer_id), row.characteristic_key) for row in rows if row.engineer_id is not None}


def should_close_against_source(
    *,
    action: str,
    pair: tuple[int, str],
    present: set[tuple[int, str]],
) -> bool:
    """Issue closes when the source has the cell; revoke closes when it does not."""
    if action == "issue":
        return pair in present
    if action == "revoke":
        return pair not in present
    return False


def close_matching_open_requests(
    db: Session,
    *,
    tenant_id: int,
    family: Family,
    present: set[tuple[int, str]],
) -> int:
    open_rows = db.scalars(
        select(CompetenceChangeRequest).where(
            CompetenceChangeRequest.tenant_id == tenant_id,
            CompetenceChangeRequest.family == family,
            CompetenceChangeRequest.status == STATUS_OPEN,
        )
    ).all()
    closed = 0
    now = _now()
    for row in open_rows:
        pair = (row.engineer_id, row.characteristic_key)
        if should_close_against_source(action=row.action, pair=pair, present=present):
            row.status = STATUS_CLOSED_OBSERVED
            row.closed_at = now
            row.close_reason = "source_observed"
            closed += 1
    return closed


def close_pams_requests_from_snapshot(db: Session, tenant_id: int) -> int:
    if db.get(PamsCompetenceCurrent, tenant_id) is None:
        return 0
    present = issued_pairs_from_snapshot(db, tenant_id)
    return close_matching_open_requests(db, tenant_id=tenant_id, family="pams", present=present)


@dataclass
class CreateChangeRequestInput:
    family: Family
    engineer_id: int
    characteristic_key: str
    action: Action
    notes: str | None
    created_by_user_id: int | None


def create_change_request(
    db: Session,
    *,
    tenant_id: int,
    payload: CreateChangeRequestInput,
) -> tuple[CompetenceChangeRequest, bool]:
    """Return (row, created). Existing open cell is returned unchanged."""
    key = payload.characteristic_key.strip()
    if not key:
        raise BadRequestError("characteristic_key is required.")
    engineer = db.get(Engineer, payload.engineer_id)
    if engineer is None or engineer.tenant_id != tenant_id:
        raise NotFoundError("Engineer not found")

    existing = db.scalars(
        select(CompetenceChangeRequest).where(
            CompetenceChangeRequest.tenant_id == tenant_id,
            CompetenceChangeRequest.family == payload.family,
            CompetenceChangeRequest.engineer_id == payload.engineer_id,
            CompetenceChangeRequest.characteristic_key == key,
            CompetenceChangeRequest.status == STATUS_OPEN,
        )
    ).first()
    if existing is not None:
        if existing.action != payload.action:
            raise ConflictError(ONE_OPEN)
        return existing, False

    row = CompetenceChangeRequest(
        tenant_id=tenant_id,
        family=payload.family,
        engineer_id=payload.engineer_id,
        characteristic_key=key[:80],
        action=payload.action,
        status=STATUS_OPEN,
        routed_to_email=mailbox_for(payload.family),
        created_by_user_id=payload.created_by_user_id,
        notes=(payload.notes or "").strip() or None,
        email_sent=False,
        created_at=_now(),
    )
    db.add(row)
    db.flush()
    return row, True


def list_change_requests(db: Session, *, tenant_id: int) -> list[CompetenceChangeRequest]:
    close_pams_requests_from_snapshot(db, tenant_id)
    return list(
        db.scalars(
            select(CompetenceChangeRequest)
            .where(CompetenceChangeRequest.tenant_id == tenant_id)
            .order_by(CompetenceChangeRequest.created_at.desc())
        ).all()
    )


async def _issued_pairs_async(db: Any, tenant_id: int) -> set[tuple[int, str]]:
    pointer = await db.get(PamsCompetenceCurrent, tenant_id)
    if pointer is None:
        return set()
    result = await db.scalars(
        select(PamsCompetenceRow).where(
            PamsCompetenceRow.snapshot_id == pointer.snapshot_id,
            PamsCompetenceRow.engineer_id.is_not(None),
        )
    )
    return {(int(row.engineer_id), row.characteristic_key) for row in result.all() if row.engineer_id is not None}


async def close_pams_requests_from_snapshot_async(db: Any, tenant_id: int) -> int:
    if await db.get(PamsCompetenceCurrent, tenant_id) is None:
        return 0
    present = await _issued_pairs_async(db, tenant_id)
    result = await db.scalars(
        select(CompetenceChangeRequest).where(
            CompetenceChangeRequest.tenant_id == tenant_id,
            CompetenceChangeRequest.family == "pams",
            CompetenceChangeRequest.status == STATUS_OPEN,
        )
    )
    closed = 0
    now = _now()
    for row in result.all():
        pair = (row.engineer_id, row.characteristic_key)
        if should_close_against_source(action=row.action, pair=pair, present=present):
            row.status = STATUS_CLOSED_OBSERVED
            row.closed_at = now
            row.close_reason = "source_observed"
            closed += 1
    return closed


async def create_change_request_async(
    db: Any,
    *,
    tenant_id: int,
    payload: CreateChangeRequestInput,
) -> tuple[CompetenceChangeRequest, bool]:
    key = payload.characteristic_key.strip()
    if not key:
        raise BadRequestError("characteristic_key is required.")
    engineer = await db.get(Engineer, payload.engineer_id)
    if engineer is None or engineer.tenant_id != tenant_id:
        raise NotFoundError("Engineer not found")

    existing = (
        await db.scalars(
            select(CompetenceChangeRequest).where(
                CompetenceChangeRequest.tenant_id == tenant_id,
                CompetenceChangeRequest.family == payload.family,
                CompetenceChangeRequest.engineer_id == payload.engineer_id,
                CompetenceChangeRequest.characteristic_key == key,
                CompetenceChangeRequest.status == STATUS_OPEN,
            )
        )
    ).first()
    if existing is not None:
        if existing.action != payload.action:
            raise ConflictError(ONE_OPEN)
        return existing, False

    row = CompetenceChangeRequest(
        tenant_id=tenant_id,
        family=payload.family,
        engineer_id=payload.engineer_id,
        characteristic_key=key[:80],
        action=payload.action,
        status=STATUS_OPEN,
        routed_to_email=mailbox_for(payload.family),
        created_by_user_id=payload.created_by_user_id,
        notes=(payload.notes or "").strip() or None,
        email_sent=False,
        created_at=_now(),
    )
    db.add(row)
    await db.flush()
    return row, True


async def list_change_requests_async(db: Any, *, tenant_id: int) -> list[CompetenceChangeRequest]:
    await close_pams_requests_from_snapshot_async(db, tenant_id)
    result = await db.scalars(
        select(CompetenceChangeRequest)
        .where(CompetenceChangeRequest.tenant_id == tenant_id)
        .order_by(CompetenceChangeRequest.created_at.desc())
    )
    return list(result.all())


def try_send_change_request_email(row: CompetenceChangeRequest) -> None:
    """Best-effort. SMTP down must not delete the row."""
    subject = (
        f"Competence change request #{row.id}: {row.action} {row.characteristic_key} " f"(engineer {row.engineer_id})"
    )
    body = (
        f"Family: {row.family}\n"
        f"Action: {row.action}\n"
        f"Engineer id: {row.engineer_id}\n"
        f"Characteristic: {row.characteristic_key}\n"
        f"Notes: {row.notes or '(none)'}\n\n"
        "QGP does not write PAMS or Citation. Apply the change in the source system. "
        "This request closes when the next snapshot/import matches."
    )
    try:
        from src.infrastructure.tasks.email_tasks import send_email

        send_email.delay(row.routed_to_email, subject, body, False)
        row.email_sent = True
        row.email_error = None
    except Exception as exc:
        logger.warning("competence_change_request email skipped id=%s: %s", row.id, type(exc).__name__)
        row.email_sent = False
        row.email_error = type(exc).__name__[:80]
