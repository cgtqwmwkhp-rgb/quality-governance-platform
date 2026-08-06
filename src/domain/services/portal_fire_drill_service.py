"""Portal fire-drill capture — owner-scoped list + complete (Wave 3).

Allowlists ``fire_drill_evacuation`` only. Completions go through
:meth:`ComplianceScheduleService.complete_requirement` so schedule roll-forward,
duplicate-occurrence checks, and CAPA-on-fail stay shared with the staff path.

v1 scopes list/complete to ``owner_id == user_id``. Broader site-role complete
is deferred; document here if that changes.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import NotFoundError, ValidationError
from src.domain.models.compliance_schedule import ComplianceRecord, ComplianceRequirement, ComplianceRequirementTemplate
from src.domain.models.location import Location
from src.domain.services.compliance_schedule_policy import derive_status
from src.domain.services.compliance_schedule_service import ComplianceScheduleService

logger = logging.getLogger(__name__)

ALLOWED_TEMPLATE_KEY = "fire_drill_evacuation"

# Portal has no CS evidence upload path yet; complete is notes + check_passed.
# Flip when a portal evidence upload can mint asset IDs for rebind on complete.
EVIDENCE_CAPTURE_SUPPORTED = False


class PortalFireDrillService:
    """Person-scoped fire-drill obligations for the employee portal."""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._schedule = ComplianceScheduleService(db)

    async def list_my_fire_drills(
        self,
        *,
        user_id: int,
        tenant_id: int,
        now: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Active fire-drill requirements owned by the caller in this tenant."""
        query = (
            select(ComplianceRequirement, Location.name)
            .join(
                ComplianceRequirementTemplate,
                ComplianceRequirement.template_id == ComplianceRequirementTemplate.id,
            )
            .outerjoin(Location, ComplianceRequirement.location_id == Location.id)
            .where(
                ComplianceRequirement.tenant_id == tenant_id,
                ComplianceRequirement.deleted_at.is_(None),
                ComplianceRequirement.is_active.is_(True),
                ComplianceRequirement.owner_id == user_id,
                ComplianceRequirementTemplate.template_key == ALLOWED_TEMPLATE_KEY,
            )
            .order_by(
                ComplianceRequirement.next_due_date.asc(),
                ComplianceRequirement.id.asc(),
            )
        )
        rows = list((await self.db.execute(query)).all())
        clock = now or datetime.now(timezone.utc)
        items: list[dict[str, Any]] = []
        for requirement, location_name in rows:
            items.append(
                {
                    "id": requirement.id,
                    "title": requirement.title,
                    "reference_number": requirement.reference_number,
                    "next_due_date": requirement.next_due_date,
                    "status": derive_status(clock, requirement.next_due_date),
                    "location_id": requirement.location_id,
                    "location_name": location_name,
                    "owner_id": requirement.owner_id,
                    "last_completed_at": requirement.last_completed_at,
                }
            )
        return {
            "items": items,
            "total": len(items),
            "evidence_capture_supported": EVIDENCE_CAPTURE_SUPPORTED,
        }

    async def complete_my_fire_drill(
        self,
        requirement_id: int,
        *,
        user_id: int,
        tenant_id: int,
        notes: Optional[str] = None,
        check_passed: Optional[bool] = None,
        evidence_asset_ids: Optional[Sequence[int]] = None,
        completed_at: Optional[datetime] = None,
        due_date_override: Optional[date] = None,
    ) -> ComplianceRecord:
        """Complete an owned fire-drill occurrence via the shared schedule service.

        Fail closed (404) for wrong tenant, inactive, non-allowlisted template,
        or non-owner — same posture as evidence rebind IDOR handling.
        """
        if evidence_asset_ids and not EVIDENCE_CAPTURE_SUPPORTED:
            raise ValidationError(
                "Portal fire-drill evidence capture is not enabled",
                code="VALIDATION_ERROR",
            )

        requirement = await self._get_owned_fire_drill(
            requirement_id,
            user_id=user_id,
            tenant_id=tenant_id,
        )
        record = await self._schedule.complete_requirement(
            requirement.id,
            tenant_id=tenant_id,
            user_id=user_id,
            completed_at=completed_at,
            check_passed=check_passed,
            notes=notes,
            evidence_asset_ids=evidence_asset_ids,
            due_date_override=due_date_override,
        )
        logger.info(
            "portal_fire_drill_completed user_id=%s requirement_id=%s record_id=%s",
            user_id,
            requirement.id,
            record.id,
        )
        return record

    async def _get_owned_fire_drill(
        self,
        requirement_id: int,
        *,
        user_id: int,
        tenant_id: int,
    ) -> ComplianceRequirement:
        result = await self.db.execute(
            select(ComplianceRequirement, ComplianceRequirementTemplate.template_key)
            .outerjoin(
                ComplianceRequirementTemplate,
                ComplianceRequirement.template_id == ComplianceRequirementTemplate.id,
            )
            .where(
                ComplianceRequirement.id == requirement_id,
                ComplianceRequirement.tenant_id == tenant_id,
                ComplianceRequirement.deleted_at.is_(None),
                ComplianceRequirement.is_active.is_(True),
            )
        )
        row = result.one_or_none()
        if row is None:
            raise NotFoundError(
                f"Fire drill requirement {requirement_id} not found",
                code="ENTITY_NOT_FOUND",
            )
        requirement, template_key = row
        if template_key != ALLOWED_TEMPLATE_KEY:
            raise NotFoundError(
                f"Fire drill requirement {requirement_id} not found",
                code="ENTITY_NOT_FOUND",
            )
        if requirement.owner_id != user_id:
            raise NotFoundError(
                f"Fire drill requirement {requirement_id} not found",
                code="ENTITY_NOT_FOUND",
            )
        return requirement
