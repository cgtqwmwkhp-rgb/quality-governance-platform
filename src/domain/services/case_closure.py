"""Shared closure gates for the case registers (incident, complaint, near miss, RTA).

Closing a case is the point at which the register stops being a live record and
starts being evidence, so the gates live here rather than in the UI: every close
path — detail page, edit form, API client, script — goes through the same
service update and therefore the same checks.

Investigations keep their own richer gate in
``src.domain.services.investigation_closure_helpers``; this module deliberately
mirrors its shape (isolated probes, ``OPEN_ACTIONS_REMAIN``, payload helpers) so
the two read the same way.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import cast, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.types import String

from src.domain.exceptions import StateTransitionError
from src.domain.models.capa import CAPAAction, CAPASource, CAPAStatus

logger = logging.getLogger(__name__)

CLOSURE_REASON_MISSING_LESSONS_LEARNT = "MISSING_LESSONS_LEARNT"
CLOSURE_REASON_OPEN_ACTIONS_REMAIN = "OPEN_ACTIONS_REMAIN"

CASE_TYPE_INCIDENT = "incident"
CASE_TYPE_COMPLAINT = "complaint"
CASE_TYPE_NEAR_MISS = "near_miss"
CASE_TYPE_RTA = "rta"

# A native case action counts as done once it is completed, cancelled, or
# verified. "pending_verification" and "overdue" are still live work.
NATIVE_ACTION_DONE_STATUSES: frozenset[str] = frozenset({"completed", "cancelled", "verified"})
CAPA_DONE_STATUSES: frozenset[str] = frozenset({CAPAStatus.CLOSED.value})

_UNBLOCK_HINT = "Complete or cancel this action before closing the case."

# Distinguishes "caller said nothing about lessons" from "caller is clearing them".
_UNSET: Any = object()


@dataclass(frozen=True)
class CaseOpenWorkItem:
    """An action or CAPA that blocks case closure."""

    kind: str
    id: int
    reference_number: str
    title: str
    status: str
    action_key: str


@dataclass(frozen=True)
class CaseClosureValidation:
    """Closure readiness for a single case, as served by ``…/closure-validation``."""

    can_close: bool
    reasons: list[str]
    open_work: list[CaseOpenWorkItem]
    lessons_present: bool
    summary: dict[str, Any]


@dataclass(frozen=True)
class _CaseConfig:
    """Per-register wiring for the shared gate."""

    label: str
    capa_source: CAPASource
    assigned_entity_type: str
    closed_status: str
    reopen_status: str
    action_kind: Optional[str] = None
    action_parent_column: Optional[str] = None


def _incident_action_model():
    from src.domain.models.incident import IncidentAction

    return IncidentAction


def _complaint_action_model():
    from src.domain.models.complaint import ComplaintAction

    return ComplaintAction


def _rta_action_model():
    from src.domain.models.rta import RTAAction

    return RTAAction


_ACTION_MODEL_LOADERS = {
    CASE_TYPE_INCIDENT: _incident_action_model,
    CASE_TYPE_COMPLAINT: _complaint_action_model,
    CASE_TYPE_RTA: _rta_action_model,
}

CASE_CONFIGS: dict[str, _CaseConfig] = {
    CASE_TYPE_INCIDENT: _CaseConfig(
        label="incident",
        capa_source=CAPASource.INCIDENT,
        assigned_entity_type="reporting_incident",
        closed_status="closed",
        reopen_status="pending_review",
        action_kind="incident_action",
        action_parent_column="incident_id",
    ),
    CASE_TYPE_COMPLAINT: _CaseConfig(
        label="complaint",
        capa_source=CAPASource.COMPLAINT,
        assigned_entity_type="complaint",
        closed_status="closed",
        reopen_status="under_investigation",
        action_kind="complaint_action",
        action_parent_column="complaint_id",
    ),
    CASE_TYPE_NEAR_MISS: _CaseConfig(
        label="near miss",
        capa_source=CAPASource.NEAR_MISS,
        assigned_entity_type="near_miss",
        # Near misses store status as an uppercase VARCHAR, unlike the enum-backed siblings.
        closed_status="CLOSED",
        reopen_status="UNDER_REVIEW",
    ),
    CASE_TYPE_RTA: _CaseConfig(
        label="road traffic collision",
        capa_source=CAPASource.RTA,
        assigned_entity_type="road_traffic_collision",
        closed_status="closed",
        reopen_status="under_investigation",
        action_kind="rta_action",
        action_parent_column="rta_id",
    ),
}


def status_value(status: Any) -> str:
    """Render a status column value as its raw string, enum member or not."""
    return status.value if hasattr(status, "value") else str(status)


def is_closed_status(case_type: str, status: Any) -> bool:
    """True when ``status`` is the closed terminal state for this register."""
    config = _config(case_type)
    return status_value(status).strip().lower() == config.closed_status.lower()


def reopen_status_for(case_type: str) -> str:
    """The single status a closed case of this type may be reopened into."""
    return _config(case_type).reopen_status


def _config(case_type: str) -> _CaseConfig:
    try:
        return CASE_CONFIGS[case_type]
    except KeyError:  # pragma: no cover — programmer error, not user input
        raise ValueError(f"Unknown case type '{case_type}'") from None


def resolve_case_tenant_id(case: Any, fallback: Optional[int]) -> int:
    """Tenant to scope the closure probes to.

    The case's own tenant wins over the caller's, so a superuser editing across
    tenants still gets that case's real open work. Probing with no tenant would
    silently match nothing and report a clean close, so that is refused.
    """
    tenant_id = getattr(case, "tenant_id", None)
    if tenant_id is None:
        tenant_id = fallback
    if tenant_id is None:
        raise StateTransitionError(
            "Cannot verify closure readiness without a tenant scope",
            code=CLOSURE_REASON_OPEN_ACTIONS_REMAIN,
            details={"reasons": [CLOSURE_REASON_OPEN_ACTIONS_REMAIN]},
        )
    return int(tenant_id)


def lessons_are_present(lessons_learnt: Any) -> bool:
    """Lessons count only when they are actual text, not whitespace."""
    return isinstance(lessons_learnt, str) and bool(lessons_learnt.strip())


@dataclass(frozen=True)
class CaseActionTally:
    """Complete/incomplete split across a case's actions and CAPAs."""

    total: int
    complete: int
    incomplete: int


async def _fetch_native_actions(
    db: AsyncSession,
    *,
    config: _CaseConfig,
    case_type: str,
    case_id: int,
    tenant_id: int,
) -> tuple[list[CaseOpenWorkItem], CaseActionTally]:
    """Return incomplete native actions plus the complete/incomplete tally.

    Statuses are compared in Python rather than SQL so a legacy uppercase or
    unmapped label cannot abort the gate — an unrecognised status is treated as
    live work, which fails closed.
    """
    model = _ACTION_MODEL_LOADERS[case_type]()
    parent_column = getattr(model, str(config.action_parent_column))
    query = (
        select(model)
        .where(parent_column == case_id, model.tenant_id == tenant_id)
        .order_by(model.created_at.asc(), model.id.asc())
    )
    result = await db.execute(query)

    items: list[CaseOpenWorkItem] = []
    total = 0
    complete = 0
    for row in result.scalars().all():
        total += 1
        status = status_value(row.status).strip().lower()
        if status in NATIVE_ACTION_DONE_STATUSES:
            complete += 1
            continue
        row_id = int(row.id)
        items.append(
            CaseOpenWorkItem(
                kind=str(config.action_kind),
                id=row_id,
                reference_number=str(row.reference_number or f"ACT-{row_id}"),
                title=str(row.title or ""),
                status=status,
                action_key=f"{config.action_kind}:{row_id}",
            )
        )
    return items, CaseActionTally(total=total, complete=complete, incomplete=total - complete)


async def _fetch_capa_actions(
    db: AsyncSession,
    *,
    config: _CaseConfig,
    case_id: int,
    tenant_id: int,
) -> tuple[list[CaseOpenWorkItem], CaseActionTally]:
    """Return incomplete CAPAs raised from this case plus their tally.

    ``source_type`` is compared as text so a PostgreSQL enum label that has not
    been deployed yet cannot 500 the close path.
    """
    query = (
        select(CAPAAction)
        .where(
            CAPAAction.tenant_id == tenant_id,
            cast(CAPAAction.source_type, String) == config.capa_source.value,
            CAPAAction.source_id == case_id,
        )
        .order_by(CAPAAction.id.asc())
    )
    result = await db.execute(query)

    items: list[CaseOpenWorkItem] = []
    total = 0
    complete = 0
    for row in result.scalars().all():
        total += 1
        status = status_value(row.status).strip().lower()
        if status in CAPA_DONE_STATUSES:
            complete += 1
            continue
        row_id = int(row.id)
        items.append(
            CaseOpenWorkItem(
                kind="capa_action",
                id=row_id,
                reference_number=str(row.reference_number or f"CAPA-{row_id}"),
                title=str(row.title or ""),
                status=status,
                action_key=f"capa:{row_id}",
            )
        )
    return items, CaseActionTally(total=total, complete=complete, incomplete=total - complete)


async def fetch_open_work_for_case(
    db: AsyncSession,
    *,
    case_type: str,
    case_id: int,
    tenant_id: int,
) -> tuple[list[CaseOpenWorkItem], CaseActionTally]:
    """Return the work that still blocks closure, plus a complete/incomplete tally.

    Each probe is isolated so one schema drift cannot hard-500 the close path.
    If every probe fails we raise instead of reporting "nothing open", because a
    silent pass here would let a case close over work nobody can see.
    """
    config = _config(case_type)
    items: list[CaseOpenWorkItem] = []
    total = 0
    complete = 0
    probes = 0
    probe_failures = 0

    if config.action_parent_column is not None:
        probes += 1
        try:
            native_items, native_tally = await _fetch_native_actions(
                db,
                config=config,
                case_type=case_type,
                case_id=case_id,
                tenant_id=tenant_id,
            )
            items.extend(native_items)
            total += native_tally.total
            complete += native_tally.complete
        except Exception:  # noqa: BLE001 — never hard-500 a single probe
            probe_failures += 1
            logger.exception(
                "fetch_open_work_native_actions_failed",
                extra={"case_type": case_type, "case_id": case_id, "tenant_id": tenant_id},
            )

    probes += 1
    try:
        capa_items, capa_tally = await _fetch_capa_actions(
            db,
            config=config,
            case_id=case_id,
            tenant_id=tenant_id,
        )
        items.extend(capa_items)
        total += capa_tally.total
        complete += capa_tally.complete
    except Exception:  # noqa: BLE001
        probe_failures += 1
        logger.exception(
            "fetch_open_work_capa_actions_failed",
            extra={"case_type": case_type, "case_id": case_id, "tenant_id": tenant_id},
        )

    if probe_failures == probes:
        raise RuntimeError(f"All open-work probes failed for {case_type} id={case_id}")

    return items, CaseActionTally(total=total, complete=complete, incomplete=total - complete)


def open_work_to_payload(items: list[CaseOpenWorkItem]) -> list[dict[str, Any]]:
    """Serialize open-work items for API responses."""
    return [
        {
            "kind": item.kind,
            "id": item.id,
            "reference_number": item.reference_number,
            "title": item.title,
            "status": item.status,
            "action_key": item.action_key,
            "unblock_hint": _UNBLOCK_HINT,
        }
        for item in items
    ]


async def _linked_investigation_summary(
    db: AsyncSession,
    *,
    config: _CaseConfig,
    case_id: int,
    tenant_id: int,
) -> Optional[dict[str, Any]]:
    """Latest linked investigation, shown for context only — it never blocks close."""
    from src.domain.models.investigation import AssignedEntityType, InvestigationRun

    try:
        result = await db.execute(
            select(InvestigationRun)
            .where(
                InvestigationRun.assigned_entity_type == AssignedEntityType(config.assigned_entity_type),
                InvestigationRun.assigned_entity_id == case_id,
                InvestigationRun.tenant_id == tenant_id,
            )
            .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.desc())
        )
        run = result.scalars().first()
    except Exception:  # noqa: BLE001 — informational only
        logger.exception(
            "closure_linked_investigation_probe_failed",
            extra={"case_id": case_id, "tenant_id": tenant_id},
        )
        return None

    if run is None:
        return None
    return {
        "id": int(run.id),
        "reference_number": run.reference_number,
        "title": run.title,
        "status": status_value(run.status),
    }


def _isoformat(value: Any) -> Optional[str]:
    return value.isoformat() if isinstance(value, datetime) else None


def _first_attr(case: Any, *names: str) -> Any:
    for name in names:
        value = getattr(case, name, None)
        if value is not None:
            return value
    return None


async def evaluate_case_closure(
    db: AsyncSession,
    *,
    case_type: str,
    case: Any,
    tenant_id: int,
    lessons_learnt: Any = _UNSET,
) -> CaseClosureValidation:
    """Assess whether ``case`` can move into its closed state.

    ``lessons_learnt`` defaults to the value already on the case; callers that
    are mid-update pass the value the update will land — including an explicit
    ``None`` — so the gate judges the outcome of the request rather than the row
    as it stands.
    """
    config = _config(case_type)
    effective_lessons = getattr(case, "lessons_learnt", None) if lessons_learnt is _UNSET else lessons_learnt
    lessons_present = lessons_are_present(effective_lessons)

    open_work, tally = await fetch_open_work_for_case(
        db,
        case_type=case_type,
        case_id=int(case.id),
        tenant_id=tenant_id,
    )

    reasons: list[str] = []
    if not lessons_present:
        reasons.append(CLOSURE_REASON_MISSING_LESSONS_LEARNT)
    if open_work:
        reasons.append(CLOSURE_REASON_OPEN_ACTIONS_REMAIN)

    linked_investigation = await _linked_investigation_summary(
        db,
        config=config,
        case_id=int(case.id),
        tenant_id=tenant_id,
    )

    lessons_text = effective_lessons if isinstance(effective_lessons, str) else None
    summary = {
        "case_type": case_type,
        "case_label": config.label,
        "id": int(case.id),
        "reference_number": getattr(case, "reference_number", None),
        "title": getattr(case, "title", None) or getattr(case, "description", None),
        "status": status_value(getattr(case, "status", "")),
        "target_status": config.closed_status,
        "severity": _severity_label(case),
        "category": _category_label(case),
        "occurred_at": _isoformat(_first_attr(case, "incident_date", "collision_date", "event_date", "received_date")),
        "reported_at": _isoformat(_first_attr(case, "reported_date", "received_date", "event_date")),
        "created_at": _isoformat(getattr(case, "created_at", None)),
        "closed_at": _isoformat(getattr(case, "closed_at", None)),
        "lessons_learnt": lessons_text,
        "lessons_present": lessons_present,
        "actions_total": tally.total,
        "actions_complete": tally.complete,
        "actions_incomplete": tally.incomplete,
        "linked_investigation": linked_investigation,
    }

    return CaseClosureValidation(
        can_close=not reasons,
        reasons=reasons,
        open_work=open_work,
        lessons_present=lessons_present,
        summary=summary,
    )


def _severity_label(case: Any) -> Optional[str]:
    value = _first_attr(case, "severity", "priority")
    return status_value(value) if value is not None else None


def _category_label(case: Any) -> Optional[str]:
    value = _first_attr(case, "incident_type", "complaint_type", "collision_type", "near_miss_type", "category")
    return status_value(value) if value is not None else None


def validation_to_payload(validation: CaseClosureValidation) -> dict[str, Any]:
    """Serialize a closure validation for the ``…/closure-validation`` endpoints."""
    return {
        "can_close": validation.can_close,
        "reasons": validation.reasons,
        "open_work": open_work_to_payload(validation.open_work),
        "open_work_count": len(validation.open_work),
        "lessons_present": validation.lessons_present,
        "summary": validation.summary,
    }


async def assert_case_can_close(
    db: AsyncSession,
    *,
    case_type: str,
    case: Any,
    tenant_id: int,
    lessons_learnt: Any = _UNSET,
) -> None:
    """Raise ``StateTransitionError`` unless the case may move into closed.

    The first blocking reason becomes the error ``code`` so clients can branch
    on it; every reason is carried in ``details.reasons``.
    """
    validation = await evaluate_case_closure(
        db,
        case_type=case_type,
        case=case,
        tenant_id=tenant_id,
        lessons_learnt=lessons_learnt,
    )
    if validation.can_close:
        return

    config = _config(case_type)
    if CLOSURE_REASON_MISSING_LESSONS_LEARNT in validation.reasons:
        message = f"Cannot close {config.label} without lessons learnt"
        code = CLOSURE_REASON_MISSING_LESSONS_LEARNT
    else:
        message = f"Cannot close {config.label} while incomplete actions remain"
        code = CLOSURE_REASON_OPEN_ACTIONS_REMAIN

    raise StateTransitionError(
        message,
        code=code,
        details={
            "reasons": validation.reasons,
            "lessons_present": validation.lessons_present,
            "open_work": open_work_to_payload(validation.open_work),
            "open_work_count": len(validation.open_work),
        },
    )


def apply_close_stamps(case: Any, *, user_id: Optional[int]) -> dict[str, Any]:
    """Stamp closed_at / closed_by_id, preserving an existing closed_at."""
    changed: dict[str, Any] = {}
    if getattr(case, "closed_at", None) is None:
        case.closed_at = datetime.now(timezone.utc)
        changed["closed_at"] = case.closed_at.isoformat()
    if hasattr(case, "closed_by_id") and getattr(case, "closed_by_id", None) is None:
        case.closed_by_id = user_id
        changed["closed_by_id"] = user_id
    return changed


def clear_close_stamps(case: Any) -> dict[str, Any]:
    """Clear closed_at / closed_by_id when a case is reopened."""
    changed: dict[str, Any] = {}
    if getattr(case, "closed_at", None) is not None:
        case.closed_at = None
        changed["closed_at"] = None
    if hasattr(case, "closed_by_id") and getattr(case, "closed_by_id", None) is not None:
        case.closed_by_id = None
        changed["closed_by_id"] = None
    return changed
