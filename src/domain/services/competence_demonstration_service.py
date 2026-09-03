"""Assessment → PAMS characteristic demonstration overlay (CB-PR4 / CB-UI-2).

A bind is explicit: an IT-Admin points one audit template at one PAMS
characteristic. Nothing is joined by name, so a QGP asset type called
"Compressor" and the PAMS characteristic "Compressor" stay unrelated until a
bind row exists.

CB-UI-2 makes the pair 1:1 per mode. One published template may be bound to a
characteristic as the *field* assessment and a different published template as
the *induction*; a second template for the same characteristic in the same mode
is refused. A characteristic nobody has bound stays unbound — that is a
statement about QGP's mapping, not about the person's competence, and it must
never be rendered as a failure.

Completing a bound assessment writes a QGP demonstration row. It never writes
PAMS: a pass records the demonstration, a fail records it as FAILED and opens a
plant change request for the IT-Admin mailbox. Issuance stays in PAMS either
way.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import select

from src.domain.exceptions import BadRequestError, ConflictError, NotFoundError
from src.domain.models.audit import AuditTemplate
from src.domain.models.competence_assessment_bind import (
    BIND_MODES,
    FIELD_MODE,
    CompetenceAssessmentBind,
)
from src.domain.models.competence_change_request import CompetenceChangeRequest
from src.domain.models.competence_demonstration import CompetenceDemonstration
from src.domain.models.engineer import CompetencyLifecycleState
from src.domain.services.workforce_spine import resolve_reassessment_interval_days

logger = logging.getLogger(__name__)

PASS_OUTCOME = "pass"
TEMPLATE_ALREADY_BOUND = "This template is already bound to a different PAMS characteristic."
CHARACTERISTIC_ALREADY_BOUND = (
    "This PAMS characteristic already has a different template bound for that mode. "
    "Remove the existing bind first — field and induction are separate binds."
)
TEMPLATE_NOT_PUBLISHED = (
    "Only a published template can be bound. Publish it first: an unpublished template's "
    "questions can still change under the bind."
)
MAX_INTERVAL_DAYS = 3650


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass
class OverlayResult:
    """What the assessment hook wrote. ``change_request`` is None on a pass."""

    demonstration: CompetenceDemonstration
    characteristic_key: str
    change_request: Optional[CompetenceChangeRequest] = None
    change_request_created: bool = False


def _clean_characteristic_key(value: str | None) -> str:
    key = (value or "").strip()
    if not key:
        raise BadRequestError("characteristic_key is required.")
    return key[:80]


def _clean_mode(value: str | None) -> str:
    """Default to field so CB-PR4 callers that predate the split keep working."""
    mode = (value or FIELD_MODE).strip().lower()
    if mode not in BIND_MODES:
        raise BadRequestError(f"mode must be one of {', '.join(BIND_MODES)}.")
    return mode


def _clean_interval_days(value: int | None) -> int | None:
    """None stays None. It means "this bind declares no interval", not "never expires"."""
    if value is None:
        return None
    interval = int(value)
    if interval < 1 or interval > MAX_INTERVAL_DAYS:
        raise BadRequestError(f"interval_days must be between 1 and {MAX_INTERVAL_DAYS}.")
    return interval


def _is_bindable_template(template: AuditTemplate) -> bool:
    """The repo's own "may be run" predicate: published and active.

    Checked when the bind is created, not when an assessment completes. Editing
    a published template flips ``is_published`` back to False and bumps the
    version; re-checking at completion would silently stop recording
    demonstrations for runs already in flight.
    """
    return bool(getattr(template, "is_published", False)) and bool(getattr(template, "is_active", False))


async def get_bind_for_template_async(
    db: Any,
    *,
    tenant_id: int,
    template_id: int,
) -> CompetenceAssessmentBind | None:
    """Look a bind up by template id only — never by asset type or name."""
    result = await db.scalars(
        select(CompetenceAssessmentBind).where(
            CompetenceAssessmentBind.tenant_id == tenant_id,
            CompetenceAssessmentBind.template_id == template_id,
        )
    )
    return result.first()


async def list_binds_async(db: Any, *, tenant_id: int) -> list[CompetenceAssessmentBind]:
    result = await db.scalars(
        select(CompetenceAssessmentBind)
        .where(CompetenceAssessmentBind.tenant_id == tenant_id)
        .order_by(CompetenceAssessmentBind.characteristic_key, CompetenceAssessmentBind.mode)
    )
    return list(result.all())


async def create_bind_async(
    db: Any,
    *,
    tenant_id: int,
    template_id: int,
    characteristic_key: str,
    mode: str | None = None,
    interval_days: int | None = None,
) -> tuple[CompetenceAssessmentBind, bool]:
    """Return (row, created).

    The pair ``(characteristic, mode)`` is the identity; the interval is a
    property of it. Posting the same pair again is idempotent and reconciles the
    interval to what was asked for rather than silently keeping the old one —
    an admin who resubmits with a new interval must not be told "already exists"
    and left looking at the previous number.
    """
    key = _clean_characteristic_key(characteristic_key)
    bind_mode = _clean_mode(mode)
    interval = _clean_interval_days(interval_days)

    template_result = await db.scalars(
        select(AuditTemplate).where(
            AuditTemplate.id == template_id,
            AuditTemplate.tenant_id == tenant_id,
        )
    )
    template = template_result.first()
    if template is None:
        raise NotFoundError("Template not found")
    if not _is_bindable_template(template):
        raise BadRequestError(TEMPLATE_NOT_PUBLISHED)

    by_template = await get_bind_for_template_async(db, tenant_id=tenant_id, template_id=template_id)
    if by_template is not None:
        if by_template.characteristic_key == key and (by_template.mode or FIELD_MODE) == bind_mode:
            by_template.interval_days = interval
            await db.flush()
            return by_template, False
        raise ConflictError(TEMPLATE_ALREADY_BOUND)

    by_characteristic = await db.scalars(
        select(CompetenceAssessmentBind).where(
            CompetenceAssessmentBind.tenant_id == tenant_id,
            CompetenceAssessmentBind.characteristic_key == key,
            CompetenceAssessmentBind.mode == bind_mode,
        )
    )
    if by_characteristic.first() is not None:
        raise ConflictError(CHARACTERISTIC_ALREADY_BOUND)

    row = CompetenceAssessmentBind(
        tenant_id=tenant_id,
        template_id=template_id,
        characteristic_key=key,
        mode=bind_mode,
        interval_days=interval,
        created_at=_now(),
    )
    db.add(row)
    await db.flush()
    return row, True


async def delete_bind_async(db: Any, *, tenant_id: int, bind_id: int) -> None:
    """Revert the bind. Demonstrations already written stay as history."""
    row = await db.get(CompetenceAssessmentBind, bind_id)
    if row is None or row.tenant_id != tenant_id:
        raise NotFoundError("Assessment bind not found")
    await db.delete(row)
    await db.flush()


async def _existing_demonstration_async(
    db: Any,
    *,
    tenant_id: int,
    source_run_id: str,
) -> CompetenceDemonstration | None:
    result = await db.scalars(
        select(CompetenceDemonstration).where(
            CompetenceDemonstration.tenant_id == tenant_id,
            CompetenceDemonstration.source_run_id == source_run_id,
        )
    )
    return result.first()


async def record_assessment_demonstration_async(
    db: Any,
    *,
    tenant_id: int,
    engineer_id: int,
    template_id: int,
    source_run_id: str,
    outcome: str,
    assessed_by_id: int | None = None,
    asset_type_id: int | None = None,
) -> OverlayResult | None:
    """Write the overlay for one completed run. None when the template is unbound.

    Re-running the same ``source_run_id`` updates that row rather than adding a
    second demonstration, so the write is idempotent.
    """
    bind = await get_bind_for_template_async(db, tenant_id=tenant_id, template_id=template_id)
    if bind is None:
        return None

    passed = outcome == PASS_OUTCOME
    expires_at: datetime | None = None
    if passed:
        # CB-UI-2: the interval declared on the bind wins, because it is the
        # one an IT-Admin can see and change on the bind screen. Without one,
        # fall back to the CompetencyRequirement resolution CB-PR4 used.
        interval_days = bind.interval_days or await resolve_reassessment_interval_days(
            db,
            asset_type_id=asset_type_id,
            template_id=template_id,
            tenant_id=tenant_id,
        )
        expires_at = _now() + timedelta(days=interval_days)

    demonstration = await _existing_demonstration_async(db, tenant_id=tenant_id, source_run_id=source_run_id)
    if demonstration is None:
        demonstration = CompetenceDemonstration(
            tenant_id=tenant_id,
            engineer_id=engineer_id,
            characteristic_key=bind.characteristic_key,
            template_id=template_id,
            source_run_id=source_run_id,
        )
        db.add(demonstration)
    demonstration.engineer_id = engineer_id
    demonstration.characteristic_key = bind.characteristic_key
    demonstration.template_id = template_id
    demonstration.outcome = outcome
    demonstration.state = CompetencyLifecycleState.ACTIVE.value if passed else CompetencyLifecycleState.FAILED.value
    demonstration.assessed_at = _now()
    demonstration.assessed_by_id = assessed_by_id
    demonstration.expires_at = expires_at
    await db.flush()

    result = OverlayResult(demonstration=demonstration, characteristic_key=bind.characteristic_key)
    if passed:
        return result

    from src.domain.services.competence_change_request_service import (
        CreateChangeRequestInput,
        create_change_request_async,
    )

    notes = (
        f"Assessment run {source_run_id} scored {outcome} against bound PAMS characteristic "
        f"{bind.characteristic_key}. QGP does not write PAMS — review the issuance in PAMS."
    )
    try:
        row, created = await create_change_request_async(
            db,
            tenant_id=tenant_id,
            payload=CreateChangeRequestInput(
                family="pams",
                engineer_id=engineer_id,
                characteristic_key=bind.characteristic_key,
                action="revoke",
                notes=notes,
                created_by_user_id=assessed_by_id,
            ),
        )
    except ConflictError:
        # An open request of the other action already owns this cell. The failed
        # demonstration is still recorded; do not turn that into a 409.
        logger.warning(
            "competence revoke request not opened for run=%s cell=(%s,%s): open request has a different action",
            source_run_id,
            engineer_id,
            bind.characteristic_key,
        )
        return result

    result.change_request = row
    result.change_request_created = created
    return result


def _recency(row: CompetenceDemonstration) -> tuple[datetime, int]:
    return (row.assessed_at or datetime.min, row.id or 0)


async def load_demonstration_overlay_async(
    db: Any,
    *,
    tenant_id: int,
    engineer_ids: set[int],
) -> dict[tuple[int, str], CompetenceDemonstration]:
    """Latest demonstration per (engineer, characteristic), for binds that still exist.

    A demonstration is only a claim QGP stands behind while the bind that
    produced it is in place. Removing the bind therefore empties the overlay for
    that column and the cell falls back to what PAMS says — issued, not
    demonstrated — rather than to an invented "not assessed" grey. The
    demonstration rows themselves are kept as history and are not deleted.
    """
    if not engineer_ids:
        return {}
    binds = await db.scalars(select(CompetenceAssessmentBind).where(CompetenceAssessmentBind.tenant_id == tenant_id))
    bound_pairs = {(bind.template_id, bind.characteristic_key) for bind in binds.all()}
    if not bound_pairs:
        return {}
    result = await db.scalars(
        select(CompetenceDemonstration).where(
            CompetenceDemonstration.tenant_id == tenant_id,
            CompetenceDemonstration.engineer_id.in_(sorted(engineer_ids)),
        )
    )
    latest: dict[tuple[int, str], CompetenceDemonstration] = {}
    for row in result.all():
        if (row.template_id, row.characteristic_key) not in bound_pairs:
            continue
        cell = (row.engineer_id, row.characteristic_key)
        current = latest.get(cell)
        if current is None or _recency(row) >= _recency(current):
            latest[cell] = row
    return latest
