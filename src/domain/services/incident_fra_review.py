"""Incident → FRA significant-change review (Wave 3).

When a closed (or closing) incident signals a premises-level significant change,
operators can activate or open a site-scoped Fire Risk Assessment obligation.

Organisation-wide FRA rows (``location_id IS NULL``) do **not** count as site
cover — same honesty rule as the location coverage gap report.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import BadRequestError, ConflictError, NotFoundError, ValidationError
from src.domain.models.asset import Asset
from src.domain.models.compliance_schedule import ComplianceRequirement, ComplianceRequirementTemplate
from src.domain.models.incident import Incident
from src.domain.models.location import Location, LocationKind
from src.domain.services.compliance_schedule_service import ComplianceScheduleService

FRA_TEMPLATE_KEY = ComplianceScheduleService.FRA_TEMPLATE_KEY
ELIGIBLE_LOCATION_KINDS = ComplianceScheduleService.COVERAGE_LOCATION_KINDS

SIGNIFICANT_INCIDENT_TYPES = frozenset({"property_damage", "hazard"})
SIGNIFICANT_SEVERITIES = frozenset({"high", "critical"})
FIRE_EMERGENCY_CODE = "fire"


def _norm(value: Any) -> str:
    if value is None:
        return ""
    raw = value.value if hasattr(value, "value") else value
    return str(raw).strip().lower()


def _emergency_codes(raw: Any) -> Sequence[str]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        return (raw,)
    if isinstance(raw, (list, tuple, set)):
        return tuple(str(item) for item in raw if item is not None)
    return ()


def _location_kind_allowed(kind: Any) -> bool:
    if isinstance(kind, LocationKind):
        return kind in ELIGIBLE_LOCATION_KINDS
    return _norm(kind) in {k.value for k in ELIGIBLE_LOCATION_KINDS}


def incident_suggests_fra_significant_change(incident: Any) -> bool:
    """Whether this incident warrants an FRA significant-change prompt.

    True when any of:
    - ``emergency_services`` includes ``fire``
    - ``incident_type`` in {property_damage, hazard} and severity high/critical
    - ``is_sif`` or ``is_psif`` is true
    """
    codes = {_norm(code) for code in _emergency_codes(getattr(incident, "emergency_services", None))}
    if FIRE_EMERGENCY_CODE in codes:
        return True

    incident_type = _norm(getattr(incident, "incident_type", None))
    severity = _norm(getattr(incident, "severity", None))
    if incident_type in SIGNIFICANT_INCIDENT_TYPES and severity in SIGNIFICANT_SEVERITIES:
        return True

    if bool(getattr(incident, "is_sif", None)) or bool(getattr(incident, "is_psif", None)):
        return True

    return False


@dataclass(frozen=True)
class FraSignificantChangeResult:
    """Outcome of activate-or-link for a site FRA."""

    created: bool
    requirement: ComplianceRequirement


async def resolve_suggested_location_id(
    db: AsyncSession,
    incident: Incident,
    *,
    tenant_id: int,
) -> Optional[int]:
    """Prefill premises/office from the linked asset when present and eligible."""
    asset_id = getattr(incident, "asset_id", None)
    if asset_id is None:
        return None

    result = await db.execute(select(Asset.location_id).where(Asset.id == asset_id))
    location_id = result.scalar_one_or_none()
    if location_id is None:
        return None

    loc = await db.execute(
        select(Location.id, Location.kind).where(
            Location.id == location_id,
            Location.tenant_id == tenant_id,
            Location.is_active.is_(True),
        )
    )
    row = loc.first()
    if row is None or not _location_kind_allowed(row.kind):
        return None
    return int(row.id)


async def find_active_site_fra(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
) -> Optional[ComplianceRequirement]:
    """Return the active location-scoped FRA for this site, if any.

    Org-wide rows (``location_id IS NULL``) are excluded on purpose.
    """
    query = (
        select(ComplianceRequirement)
        .join(
            ComplianceRequirementTemplate,
            ComplianceRequirement.template_id == ComplianceRequirementTemplate.id,
        )
        .where(
            ComplianceRequirement.tenant_id == tenant_id,
            ComplianceRequirement.deleted_at.is_(None),
            ComplianceRequirement.is_active.is_(True),
            ComplianceRequirement.location_id == location_id,
            ComplianceRequirementTemplate.template_key == FRA_TEMPLATE_KEY,
        )
        .order_by(ComplianceRequirement.id.asc())
        .limit(1)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


async def _require_eligible_location(
    db: AsyncSession,
    *,
    tenant_id: int,
    location_id: int,
) -> Location:
    result = await db.execute(
        select(Location).where(
            Location.id == location_id,
            Location.tenant_id == tenant_id,
        )
    )
    location = result.scalar_one_or_none()
    if location is None:
        raise NotFoundError(
            f"Location {location_id} not found",
            code="ENTITY_NOT_FOUND",
        )
    if not _location_kind_allowed(location.kind):
        raise ValidationError(
            "FRA significant-change requires a premises or office location",
            code="VALIDATION_ERROR",
        )
    return location


async def activate_or_link_fra_significant_change(
    db: AsyncSession,
    *,
    incident: Incident,
    tenant_id: int,
    user_id: int,
    location_id: int,
    now: Optional[datetime] = None,
) -> FraSignificantChangeResult:
    """Activate a site FRA for the incident location, or return the existing one."""
    if not incident_suggests_fra_significant_change(incident):
        raise BadRequestError(
            "Incident does not indicate an FRA significant change",
        )
    if location_id is None:
        raise ValidationError(
            "location_id is required for FRA significant-change",
            code="VALIDATION_ERROR",
        )

    await _require_eligible_location(db, tenant_id=tenant_id, location_id=location_id)

    existing = await find_active_site_fra(db, tenant_id=tenant_id, location_id=location_id)
    if existing is not None:
        return FraSignificantChangeResult(created=False, requirement=existing)

    clock = now or datetime.now(timezone.utc)
    due = clock.date() if hasattr(clock, "date") else date.today()
    service = ComplianceScheduleService(db)
    try:
        requirement = await service.activate_catalogue_template(
            FRA_TEMPLATE_KEY,
            tenant_id=tenant_id,
            user_id=user_id,
            location_id=location_id,
            next_due_date=due,
            now=clock,
        )
    except ConflictError:
        # Race: another activate won. Treat as link-existing.
        raced = await find_active_site_fra(db, tenant_id=tenant_id, location_id=location_id)
        if raced is not None:
            return FraSignificantChangeResult(created=False, requirement=raced)
        raise

    return FraSignificantChangeResult(created=True, requirement=requirement)


__all__ = [
    "ELIGIBLE_LOCATION_KINDS",
    "FIRE_EMERGENCY_CODE",
    "FRA_TEMPLATE_KEY",
    "FraSignificantChangeResult",
    "SIGNIFICANT_INCIDENT_TYPES",
    "SIGNIFICANT_SEVERITIES",
    "activate_or_link_fra_significant_change",
    "find_active_site_fra",
    "incident_suggests_fra_significant_change",
    "resolve_suggested_location_id",
]
