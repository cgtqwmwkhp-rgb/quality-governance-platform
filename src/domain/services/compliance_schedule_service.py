"""Compliance Schedule domain service (Wave 1 vertical slice).

Keeps HTTP routes thin: tenancy, catalogue activate, requirement CRUD,
complete-record (atomic with evidence rebind), and stats.
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any, Optional, Sequence, cast

from sqlalchemy import false, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.exceptions import ConflictError, NotFoundError, ValidationError
from src.domain.models.compliance_schedule import (
    ComplianceFilingStatus,
    ComplianceRecord,
    ComplianceRecordOutcome,
    ComplianceRequirement,
    ComplianceRequirementTemplate,
    ComplianceScheduleAnchor,
)
from src.domain.models.evidence_asset import EvidenceAsset, EvidenceSourceModule
from src.domain.models.location import Location, LocationKind
from src.domain.models.standard import Clause, Standard
from src.domain.models.user import User
from src.domain.services.audit_service import record_audit_event
from src.domain.services.capa_auto_service import CAPAAutoService
from src.domain.services.compliance_schedule_assignment_notify import notify_compliance_schedule_owner_assignment
from src.domain.services.compliance_schedule_policy import Anchor, compute_next_due, derive_status
from src.domain.services.reference_number import ReferenceNumberService

logger = logging.getLogger(__name__)


def _as_utc(value: Optional[datetime], *, fallback: Optional[datetime] = None) -> datetime:
    if value is None:
        value = fallback or datetime.now(timezone.utc)
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _anchor_value(anchor: ComplianceScheduleAnchor | str) -> Anchor:
    """Narrow a stored anchor to the literal pair ``compute_next_due`` accepts.

    The column is an enum behind a CHECK constraint, so a third value is already
    unstorable; rejecting it here fails in this service's terms rather than
    several frames deeper in the policy helper.
    """
    raw = anchor.value if isinstance(anchor, ComplianceScheduleAnchor) else str(anchor)
    if raw == "completion":
        return "completion"
    if raw == "schedule":
        return "schedule"
    raise ValueError(f"unknown anchor: {raw}")


def _tenant_filter(query: Any, model: Any, tenant_id: Optional[int]) -> Any:
    """Fail-closed tenant scope (mirrors api.utils.tenant.apply_tenant_filter)."""
    if tenant_id is None:
        return query.where(false())
    return query.where(model.tenant_id == tenant_id)


# ``uq_compliance_records_tenant_requirement_due``, in the two ways the drivers
# report it. PostgreSQL names the constraint; SQLite names the columns instead and
# never the constraint, so matching only the name would make the same lost race a
# 409 on the database CI runs integration tests against and a 500 on the one it
# runs the SQLite suites against. Matched by substring because that is how this
# repository already identifies a violated constraint (see the reference-number
# retry in ``api.routes.assessments``); there is no portable structured field.
_DUPLICATE_OCCURRENCE_SIGNATURES = (
    "uq_compliance_records_tenant_requirement_due",
    "compliance_records.due_date",
)


def _is_duplicate_occurrence(exc: IntegrityError) -> bool:
    """Whether this integrity error is the occurrence-uniqueness constraint.

    Deliberately narrow. Any other integrity error reaching the same handler is
    ours rather than the caller's — a missing tenant row, a null in a NOT NULL
    column — and answering 409 to it would tell the caller their request
    conflicted with someone else's when in fact the service is broken. Those keep
    propagating and stay a 500, which is where a defect belongs.
    """
    text = str(exc)
    return any(signature in text for signature in _DUPLICATE_OCCURRENCE_SIGNATURES)


class ComplianceScheduleService:
    """Tenant-scoped Compliance Schedule operations."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------

    async def get_requirement(
        self,
        requirement_id: int,
        *,
        tenant_id: int,
        include_inactive: bool = True,
    ) -> ComplianceRequirement:
        query = (
            select(ComplianceRequirement)
            .options(selectinload(ComplianceRequirement.template))
            .where(
                ComplianceRequirement.id == requirement_id,
                ComplianceRequirement.deleted_at.is_(None),
            )
        )
        query = _tenant_filter(query, ComplianceRequirement, tenant_id)
        if not include_inactive:
            query = query.where(ComplianceRequirement.is_active.is_(True))
        result = await self.db.execute(query)
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError(
                f"Compliance requirement {requirement_id} not found",
                code="ENTITY_NOT_FOUND",
            )
        return row

    async def get_record(self, record_id: int, *, tenant_id: int) -> ComplianceRecord:
        query = select(ComplianceRecord).where(ComplianceRecord.id == record_id)
        query = _tenant_filter(query, ComplianceRecord, tenant_id)
        result = await self.db.execute(query)
        row = result.scalar_one_or_none()
        if row is None:
            raise NotFoundError(
                f"Compliance record {record_id} not found",
                code="ENTITY_NOT_FOUND",
            )
        return row

    async def _get_template_by_key(self, template_key: str) -> ComplianceRequirementTemplate:
        result = await self.db.execute(
            select(ComplianceRequirementTemplate).where(
                ComplianceRequirementTemplate.template_key == template_key,
                ComplianceRequirementTemplate.is_active.is_(True),
            )
        )
        template = result.scalar_one_or_none()
        if template is None:
            raise NotFoundError(
                f"Catalogue template '{template_key}' not found",
                code="ENTITY_NOT_FOUND",
            )
        return template

    async def _assert_location_in_tenant(
        self,
        location_id: Optional[int],
        *,
        tenant_id: int,
    ) -> None:
        if location_id is None:
            return
        result = await self.db.execute(
            select(Location.id).where(
                Location.id == location_id,
                Location.tenant_id == tenant_id,
            )
        )
        if result.scalar_one_or_none() is None:
            # Fail closed: do not leak whether the location exists elsewhere.
            raise NotFoundError(
                f"Location {location_id} not found",
                code="ENTITY_NOT_FOUND",
            )

    async def _assert_regulatory_link_in_tenant(
        self,
        standard_id: Optional[int],
        clause_id: Optional[int],
        *,
        tenant_id: int,
    ) -> None:
        """Refuse a Standards link that is missing, inactive, or cross-tenant.

        A clause without a standard is unrenderable. Cross-tenant standards are
        treated as not found — same fail-closed pattern as location ownership.
        """
        if standard_id is None and clause_id is None:
            return
        if clause_id is not None and standard_id is None:
            raise ValidationError(
                "regulatory_clause_id requires regulatory_standard_id",
                code="VALIDATION_ERROR",
            )
        result = await self.db.execute(
            select(Standard).where(
                Standard.id == standard_id,
                Standard.is_active.is_(True),
                or_(Standard.tenant_id.is_(None), Standard.tenant_id == tenant_id),
            )
        )
        standard = result.scalar_one_or_none()
        if standard is None:
            raise NotFoundError(
                f"Standard {standard_id} not found",
                code="ENTITY_NOT_FOUND",
            )
        if clause_id is None:
            return
        clause_result = await self.db.execute(
            select(Clause).where(
                Clause.id == clause_id,
                Clause.is_active.is_(True),
                Clause.standard_id == standard_id,
            )
        )
        if clause_result.scalar_one_or_none() is None:
            raise NotFoundError(
                f"Clause {clause_id} not found",
                code="ENTITY_NOT_FOUND",
            )

    async def _assert_owner_in_tenant(
        self,
        owner_id: Optional[int],
        *,
        tenant_id: int,
    ) -> None:
        """Refuse an owner who does not belong to this tenant.

        The owner is a notification recipient, not merely a label. The reminder
        sweep passes ``requirement.owner_id`` through untouched while scoping its
        admin fallback to the tenant, and the notification body carries the
        obligation's reference number and title. Reading notifications is
        filtered by user alone, so an owner id from another tenant delivers one
        customer's obligation into another customer's inbox.

        Location is already guarded this way; the owner never was.
        """
        if owner_id is None:
            return
        result = await self.db.execute(
            select(User.id).where(
                User.id == owner_id,
                User.tenant_id == tenant_id,
                User.is_active.is_(True),
            )
        )
        if result.scalar_one_or_none() is None:
            # Fail closed, matching the location precedent: do not disclose
            # whether the user exists in some other tenant.
            raise NotFoundError(
                f"User {owner_id} not found",
                code="ENTITY_NOT_FOUND",
            )

    async def _assert_template_not_already_active(
        self,
        template_id: int,
        *,
        tenant_id: int,
        location_id: Optional[int],
    ) -> None:
        """Refuse a second live copy of the same template at the same place.

        Activation had no idempotency check, so pressing Activate twice — or
        double-clicking it once — produced two identical obligations, both on the
        register and both notifying their owner on the same schedule.

        Scoped to location because the same template legitimately applies at
        several sites: a fire risk assessment per building is not a duplicate.
        Retired and soft-deleted rows are excluded so that retiring an obligation
        and later activating the template afresh remains a clean cycle rather
        than a permanent block.
        """
        query = select(ComplianceRequirement.id, ComplianceRequirement.reference_number).where(
            ComplianceRequirement.template_id == template_id,
            ComplianceRequirement.is_active.is_(True),
            ComplianceRequirement.deleted_at.is_(None),
        )
        query = _tenant_filter(query, ComplianceRequirement, tenant_id)
        if location_id is None:
            query = query.where(ComplianceRequirement.location_id.is_(None))
        else:
            query = query.where(ComplianceRequirement.location_id == location_id)

        existing = (await self.db.execute(query)).first()
        if existing is None:
            return
        raise ConflictError(
            f"This obligation is already on the register as {existing.reference_number}",
            code="DUPLICATE_ENTITY",
            details={"requirement_id": existing.id, "reference_number": existing.reference_number},
        )

    # ------------------------------------------------------------------
    # Catalogue
    # ------------------------------------------------------------------

    async def list_catalogue(self, *, active_only: bool = True) -> list[ComplianceRequirementTemplate]:
        query = select(ComplianceRequirementTemplate).order_by(
            ComplianceRequirementTemplate.taxonomy_id,
            ComplianceRequirementTemplate.template_key,
        )
        if active_only:
            query = query.where(ComplianceRequirementTemplate.is_active.is_(True))
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def activate_catalogue_template(
        self,
        template_key: str,
        *,
        tenant_id: int,
        user_id: int,
        location_id: Optional[int] = None,
        next_due_date: Optional[date] = None,
        last_completed_at: Optional[datetime] = None,
        owner_id: Optional[int] = None,
        now: Optional[datetime] = None,
    ) -> ComplianceRequirement:
        """Materialise a catalogue template as a tenant requirement."""
        template = await self._get_template_by_key(template_key)
        await self._assert_location_in_tenant(location_id, tenant_id=tenant_id)
        await self._assert_owner_in_tenant(owner_id, tenant_id=tenant_id)
        await self._assert_template_not_already_active(
            template.id,
            tenant_id=tenant_id,
            location_id=location_id,
        )

        clock = _as_utc(now)
        due = next_due_date or clock.date()
        if last_completed_at is not None and next_due_date is None:
            # When only last_completed is supplied, roll forward from it using
            # completion anchor semantics for the first due.
            due = compute_next_due(
                "completion",
                previous_due=due,
                completed_at=last_completed_at,
                frequency_months=template.frequency_months,
                frequency_days=template.frequency_days,
            )

        requirement = await self._create_requirement_row(
            tenant_id=tenant_id,
            user_id=user_id,
            title=template.title,
            taxonomy_id=template.taxonomy_id,
            description=template.description,
            regulatory_basis=template.regulatory_basis,
            frequency_months=template.frequency_months,
            frequency_days=template.frequency_days,
            anchor=_anchor_value(template.anchor),
            statutory=template.statutory,
            next_due_date=due,
            last_completed_at=last_completed_at,
            location_id=location_id,
            owner_id=owner_id,
            template_id=template.id,
        )
        # Avoid lazy-load under asyncio in ``_requirement_response``.
        requirement.template = template
        return requirement

    # ------------------------------------------------------------------
    # Requirements
    # ------------------------------------------------------------------

    async def list_requirements(
        self,
        *,
        tenant_id: int,
        is_active: Optional[bool] = True,
        location_id: Optional[int] = None,
        status: Optional[str] = None,
        statutory: Optional[bool] = None,
        page: int = 1,
        page_size: int = 50,
        now: Optional[datetime] = None,
    ) -> tuple[list[ComplianceRequirement], int]:
        query = (
            select(ComplianceRequirement)
            .options(selectinload(ComplianceRequirement.template))
            .where(ComplianceRequirement.deleted_at.is_(None))
        )
        query = _tenant_filter(query, ComplianceRequirement, tenant_id)
        if is_active is not None:
            query = query.where(ComplianceRequirement.is_active.is_(is_active))
        if location_id is not None:
            query = query.where(ComplianceRequirement.location_id == location_id)
        if statutory is not None:
            query = query.where(ComplianceRequirement.statutory.is_(statutory))

        # Status is derived — filter in Python after fetch for the page window
        # when a status filter is requested, otherwise paginate in SQL.
        if status is None:
            count_q = select(func.count()).select_from(query.subquery())
            total = int((await self.db.execute(count_q)).scalar() or 0)
            query = query.order_by(
                ComplianceRequirement.next_due_date.asc(),
                ComplianceRequirement.id.asc(),
            )
            query = query.offset((page - 1) * page_size).limit(page_size)
            rows = list((await self.db.execute(query)).scalars().all())
            return rows, total

        rows = list(
            (
                await self.db.execute(
                    query.order_by(
                        ComplianceRequirement.next_due_date.asc(),
                        ComplianceRequirement.id.asc(),
                    )
                )
            )
            .scalars()
            .all()
        )
        clock = _as_utc(now)
        filtered = [r for r in rows if derive_status(clock, r.next_due_date) == status]
        total = len(filtered)
        start = (page - 1) * page_size
        return filtered[start : start + page_size], total

    async def create_requirement(
        self,
        *,
        tenant_id: int,
        user_id: int,
        title: str,
        taxonomy_id: str,
        next_due_date: date,
        frequency_months: Optional[int] = None,
        frequency_days: Optional[int] = None,
        anchor: str = "schedule",
        description: Optional[str] = None,
        regulatory_basis: Optional[str] = None,
        regulatory_standard_id: Optional[int] = None,
        regulatory_clause_id: Optional[int] = None,
        statutory: bool = False,
        location_id: Optional[int] = None,
        owner_id: Optional[int] = None,
        template_id: Optional[int] = None,
        last_completed_at: Optional[datetime] = None,
        is_active: bool = True,
    ) -> ComplianceRequirement:
        if frequency_months is None and frequency_days is None:
            raise ValidationError(
                "frequency_months or frequency_days is required",
                code="VALIDATION_ERROR",
            )
        if anchor not in {"completion", "schedule"}:
            raise ValidationError(f"invalid anchor: {anchor}", code="VALIDATION_ERROR")

        await self._assert_location_in_tenant(location_id, tenant_id=tenant_id)
        await self._assert_owner_in_tenant(owner_id, tenant_id=tenant_id)
        await self._assert_regulatory_link_in_tenant(
            regulatory_standard_id,
            regulatory_clause_id,
            tenant_id=tenant_id,
        )

        return await self._create_requirement_row(
            tenant_id=tenant_id,
            user_id=user_id,
            title=title,
            taxonomy_id=taxonomy_id,
            description=description,
            regulatory_basis=regulatory_basis,
            regulatory_standard_id=regulatory_standard_id,
            regulatory_clause_id=regulatory_clause_id,
            frequency_months=frequency_months,
            frequency_days=frequency_days,
            anchor=anchor,
            statutory=statutory,
            next_due_date=next_due_date,
            last_completed_at=last_completed_at,
            location_id=location_id,
            owner_id=owner_id,
            template_id=template_id,
            is_active=is_active,
        )

    async def _create_requirement_row(
        self,
        *,
        tenant_id: int,
        user_id: int,
        title: str,
        taxonomy_id: str,
        description: Optional[str],
        regulatory_basis: Optional[str],
        frequency_months: Optional[int],
        frequency_days: Optional[int],
        anchor: str,
        statutory: bool,
        next_due_date: date,
        last_completed_at: Optional[datetime],
        location_id: Optional[int],
        owner_id: Optional[int],
        template_id: Optional[int],
        is_active: bool = True,
        regulatory_standard_id: Optional[int] = None,
        regulatory_clause_id: Optional[int] = None,
    ) -> ComplianceRequirement:
        ref = await ReferenceNumberService.generate(self.db, "compliance_requirement", ComplianceRequirement)
        requirement = ComplianceRequirement(
            tenant_id=tenant_id,
            reference_number=ref,
            template_id=template_id,
            location_id=location_id,
            title=title,
            taxonomy_id=taxonomy_id,
            description=description,
            regulatory_basis=regulatory_basis,
            regulatory_standard_id=regulatory_standard_id,
            regulatory_clause_id=regulatory_clause_id,
            frequency_months=frequency_months,
            frequency_days=frequency_days,
            anchor=ComplianceScheduleAnchor(anchor),
            statutory=statutory,
            next_due_date=next_due_date,
            last_completed_at=_as_utc(last_completed_at) if last_completed_at else None,
            owner_id=owner_id,
            is_active=is_active,
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        self.db.add(requirement)
        await self.db.flush()

        await record_audit_event(
            db=self.db,
            event_type="compliance_schedule.requirement_created",
            entity_type="compliance_requirement",
            entity_id=str(requirement.id),
            entity_name=requirement.reference_number,
            action="create",
            description=f"Created compliance requirement {requirement.reference_number}",
            payload={
                "title": requirement.title,
                "next_due_date": requirement.next_due_date.isoformat(),
                "template_id": template_id,
                "location_id": location_id,
            },
            user_id=user_id,
            actor_user_id=user_id,
            changed_fields=["title", "next_due_date", "anchor", "frequency_months", "frequency_days"],
            tenant_id=tenant_id,
        )
        await self.db.commit()
        await self.db.refresh(requirement)
        # Eager template for ``fra_ocr_eligible`` (avoids async lazy IO).
        await self.db.refresh(requirement, attribute_names=["template"])
        # Owner allocation notify after commit so a delivery failure cannot roll back
        # the requirement write (incident / action assignment posture).
        if requirement.owner_id is not None:
            await notify_compliance_schedule_owner_assignment(
                self.db,
                tenant_id=tenant_id,
                requirement_id=requirement.id,
                reference_number=requirement.reference_number,
                title=requirement.title,
                new_owner_id=requirement.owner_id,
                previous_owner_id=None,
                assigned_by_user_id=user_id,
                next_due_date=requirement.next_due_date,
            )
        return requirement

    async def update_requirement(
        self,
        requirement_id: int,
        *,
        tenant_id: int,
        user_id: int,
        updates: dict[str, Any],
    ) -> ComplianceRequirement:
        requirement = await self.get_requirement(requirement_id, tenant_id=tenant_id)
        previous_owner_id = requirement.owner_id
        if "location_id" in updates:
            await self._assert_location_in_tenant(updates["location_id"], tenant_id=tenant_id)
        if "owner_id" in updates:
            await self._assert_owner_in_tenant(updates["owner_id"], tenant_id=tenant_id)

        if "regulatory_standard_id" in updates or "regulatory_clause_id" in updates:
            effective_standard = (
                updates["regulatory_standard_id"]
                if "regulatory_standard_id" in updates
                else requirement.regulatory_standard_id
            )
            effective_clause = (
                updates["regulatory_clause_id"]
                if "regulatory_clause_id" in updates
                else requirement.regulatory_clause_id
            )
            await self._assert_regulatory_link_in_tenant(
                effective_standard,
                effective_clause,
                tenant_id=tenant_id,
            )

        if "anchor" in updates and updates["anchor"] is not None:
            anchor = updates["anchor"]
            if anchor not in {"completion", "schedule"}:
                raise ValidationError(f"invalid anchor: {anchor}", code="VALIDATION_ERROR")
            updates["anchor"] = ComplianceScheduleAnchor(anchor)

        changed: list[str] = []
        for key, value in updates.items():
            if value is None and key not in {
                "description",
                "regulatory_basis",
                "regulatory_standard_id",
                "regulatory_clause_id",
                "location_id",
                "owner_id",
                "last_completed_at",
                "frequency_months",
                "frequency_days",
            }:
                continue
            if not hasattr(requirement, key):
                continue
            current = getattr(requirement, key)
            if current != value:
                setattr(requirement, key, value)
                changed.append(key)

        if "frequency_months" in updates or "frequency_days" in updates:
            if requirement.frequency_months is None and requirement.frequency_days is None:
                raise ValidationError(
                    "frequency_months or frequency_days is required",
                    code="VALIDATION_ERROR",
                )

        requirement.updated_by_id = user_id
        await self.db.flush()

        if changed:
            await record_audit_event(
                db=self.db,
                event_type="compliance_schedule.requirement_updated",
                entity_type="compliance_requirement",
                entity_id=str(requirement.id),
                entity_name=requirement.reference_number,
                action="update",
                description=f"Updated compliance requirement {requirement.reference_number}",
                payload={"changed_fields": changed},
                user_id=user_id,
                actor_user_id=user_id,
                changed_fields=changed,
                tenant_id=tenant_id,
            )

        await self.db.commit()
        await self.db.refresh(requirement)
        await self.db.refresh(requirement, attribute_names=["template"])
        if "owner_id" in changed:
            await notify_compliance_schedule_owner_assignment(
                self.db,
                tenant_id=tenant_id,
                requirement_id=requirement.id,
                reference_number=requirement.reference_number,
                title=requirement.title,
                new_owner_id=requirement.owner_id,
                previous_owner_id=previous_owner_id,
                assigned_by_user_id=user_id,
                next_due_date=requirement.next_due_date,
            )
        return requirement

    async def deactivate_requirement(
        self,
        requirement_id: int,
        *,
        tenant_id: int,
        user_id: int,
    ) -> ComplianceRequirement:
        """Retire an obligation, refusing one that is already retired.

        Retirement is a state transition, not a field edit, and this method
        reaches it through ``update_requirement``, which audits only the fields it
        found changed. Setting ``is_active`` false on a row where it is already
        false changes nothing, so the request answered 200 having written no row
        and recorded no audit event — telling the caller a retirement happened at
        a moment the trail can never account for. On a compliance register, which
        exists to be evidence, that is the one outcome worth refusing outright.

        409 rather than a documented idempotent success, for consistency with
        ``_assert_template_not_already_active``: activating what is already active
        conflicts here, and the mirror case should not quietly succeed. The
        precondition is asserted here rather than in ``update_requirement``,
        because a PATCH that changes nothing is legitimately a no-op and other
        callers rely on that.

        Not a guard against concurrency: two simultaneous retirements can both
        pass this check and both write, and the outcome — retired, audited once
        per writer — is the state the caller asked for either way.
        """
        requirement = await self.get_requirement(requirement_id, tenant_id=tenant_id)
        if not requirement.is_active:
            raise ConflictError(
                f"{requirement.reference_number} is already retired",
                code="DUPLICATE_ENTITY",
                details={"requirement_id": requirement.id, "reference_number": requirement.reference_number},
            )

        return await self.update_requirement(
            requirement_id,
            tenant_id=tenant_id,
            user_id=user_id,
            updates={"is_active": False},
        )

    # ------------------------------------------------------------------
    # Records / complete
    # ------------------------------------------------------------------

    async def list_records(
        self,
        requirement_id: int,
        *,
        tenant_id: int,
        page: int = 1,
        page_size: int = 50,
    ) -> tuple[list[ComplianceRecord], int]:
        await self.get_requirement(requirement_id, tenant_id=tenant_id)
        base = select(ComplianceRecord).where(ComplianceRecord.requirement_id == requirement_id)
        base = _tenant_filter(base, ComplianceRecord, tenant_id)
        count_q = select(func.count()).select_from(base.subquery())
        total = int((await self.db.execute(count_q)).scalar() or 0)
        query = base.order_by(ComplianceRecord.due_date.desc(), ComplianceRecord.id.desc())
        query = query.offset((page - 1) * page_size).limit(page_size)
        rows = list((await self.db.execute(query)).scalars().all())
        return rows, total

    async def complete_requirement(
        self,
        requirement_id: int,
        *,
        tenant_id: int,
        user_id: int,
        completed_at: Optional[datetime] = None,
        check_passed: Optional[bool] = None,
        notes: Optional[str] = None,
        evidence_asset_ids: Optional[Sequence[int]] = None,
        due_date_override: Optional[date] = None,
        now: Optional[datetime] = None,
    ) -> ComplianceRecord:
        """Close the current occurrence and roll ``next_due_date`` forward.

        Atomic: record insert, requirement schedule update, evidence rebind and —
        when ``check_passed`` is False — the corrective action share one
        transaction. Unique (tenant, requirement, due_date) prevents
        double-complete of the same occurrence — the check below reports it when
        the earlier record is already visible, and the constraint reports it when
        the two overlap. Both answer 409; see the handler for why.

        The CAPA is not wrapped in a swallow. ``complete_assessment`` takes the
        same line: a notification that fails is logged and the run still closes,
        but a CAPA that fails takes the whole completion down with it. The reason
        holds harder here — a compliance record that says the check failed, with
        no corrective action anywhere, is precisely the hole an auditor looks
        for, and it would be written silently. Failing the request instead leaves
        the register unchanged and the operator able to retry.
        """
        requirement = await self.get_requirement(requirement_id, tenant_id=tenant_id)
        if not requirement.is_active:
            raise ValidationError(
                "Cannot complete an inactive requirement",
                code="VALIDATION_ERROR",
            )

        clock = _as_utc(completed_at, fallback=_as_utc(now))
        occurrence_due = due_date_override or requirement.next_due_date

        existing = await self.db.execute(
            select(ComplianceRecord.id).where(
                ComplianceRecord.tenant_id == tenant_id,
                ComplianceRecord.requirement_id == requirement.id,
                ComplianceRecord.due_date == occurrence_due,
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError(
                f"Occurrence for due date {occurrence_due.isoformat()} already recorded",
                code="DUPLICATE_ENTITY",
                details={"requirement_id": requirement_id, "due_date": occurrence_due.isoformat()},
            )

        next_due = compute_next_due(
            _anchor_value(requirement.anchor),
            previous_due=occurrence_due,
            completed_at=clock,
            frequency_months=requirement.frequency_months,
            frequency_days=requirement.frequency_days,
        )

        # Read off the instance before the write, because the rollback in the
        # handler below expires every object in the session: an attribute touched
        # after it would re-load lazily from a sync context and raise
        # MissingGreenlet, losing the conflict behind an unrelated error.
        requirement_ref = requirement.reference_number

        ref = await ReferenceNumberService.generate(self.db, "compliance_record", ComplianceRecord)
        record = ComplianceRecord(
            tenant_id=tenant_id,
            reference_number=ref,
            requirement_id=requirement.id,
            due_date=occurrence_due,
            outcome=ComplianceRecordOutcome.COMPLETED,
            completed_at=clock,
            check_passed=check_passed,
            notes=notes,
            filing_status=ComplianceFilingStatus.NOT_FILED,
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        self.db.add(record)
        capa_reference: Optional[str] = None

        try:
            await self.db.flush()

            requirement.last_completed_at = clock
            requirement.next_due_date = next_due
            requirement.updated_by_id = user_id

            if evidence_asset_ids:
                await self._attach_evidence_assets(
                    record,
                    evidence_asset_ids=evidence_asset_ids,
                    tenant_id=tenant_id,
                )

            # ``is False`` and not falsiness: the column is nullable and None
            # means the obligation has no pass/fail dimension at all (a drill was
            # held, a certificate was renewed). Raising a corrective action for
            # "not applicable" would fill the board with work nobody owes.
            if check_passed is False:
                capa = await CAPAAutoService.create_from_compliance_record(
                    self.db,
                    record=record,
                    requirement=requirement,
                    created_by_id=user_id,
                )
                capa_reference = cast(Optional[str], capa.reference_number)

            await record_audit_event(
                db=self.db,
                event_type="compliance_schedule.requirement_completed",
                entity_type="compliance_record",
                entity_id=str(record.id),
                entity_name=record.reference_number,
                action="create",
                description=(
                    f"Completed {requirement_ref} occurrence "
                    f"due {occurrence_due.isoformat()}; next due {next_due.isoformat()}"
                ),
                payload={
                    "requirement_id": requirement_id,
                    "requirement_ref": requirement_ref,
                    "due_date": occurrence_due.isoformat(),
                    "next_due_date": next_due.isoformat(),
                    "check_passed": check_passed,
                    "evidence_asset_ids": list(evidence_asset_ids or []),
                    "capa_reference": capa_reference,
                },
                user_id=user_id,
                actor_user_id=user_id,
                changed_fields=["outcome", "completed_at", "next_due_date", "last_completed_at"],
                tenant_id=tenant_id,
            )

            await self.db.commit()
        except IntegrityError as exc:
            # The duplicate check above is a read with no lock held after it, so
            # two requests closing the same occurrence both pass it and both
            # insert. This is the constraint refusing the second one, and it is
            # the same outcome the check reports — reported the same way, because
            # which of the two noticed is an implementation detail and the caller
            # is owed one answer for one situation.
            await self.db.rollback()
            if not _is_duplicate_occurrence(exc):
                raise
            logger.info(
                "compliance completion lost a race for requirement=%s due=%s",
                requirement_id,
                occurrence_due.isoformat(),
            )
            raise ConflictError(
                f"Occurrence for due date {occurrence_due.isoformat()} already recorded",
                code="DUPLICATE_ENTITY",
                details={"requirement_id": requirement_id, "due_date": occurrence_due.isoformat()},
            ) from exc

        await self.db.refresh(record)
        await self.db.refresh(requirement)
        return record

    async def _attach_evidence_assets(
        self,
        record: ComplianceRecord,
        *,
        evidence_asset_ids: Sequence[int],
        tenant_id: int,
    ) -> None:
        """Rebind existing evidence assets onto this compliance record.

        Validates each asset exists for the tenant. Missing or cross-tenant IDs
        raise NotFoundError (fail closed, no IDOR distinction).
        """
        if not evidence_asset_ids:
            return
        unique_ids = list(dict.fromkeys(int(i) for i in evidence_asset_ids))
        result = await self.db.execute(
            select(EvidenceAsset).where(
                EvidenceAsset.id.in_(unique_ids),
                EvidenceAsset.tenant_id == tenant_id,
                EvidenceAsset.deleted_at.is_(None),
            )
        )
        found = {asset.id: asset for asset in result.scalars().all()}
        missing = [i for i in unique_ids if i not in found]
        if missing:
            raise NotFoundError(
                f"Evidence asset(s) not found: {missing}",
                code="ENTITY_NOT_FOUND",
                details={"evidence_asset_ids": missing},
            )
        for asset in found.values():
            asset.source_module = EvidenceSourceModule.COMPLIANCE_RECORD
            asset.source_id = str(record.id)

    async def attach_evidence_to_record(
        self,
        record_id: int,
        *,
        tenant_id: int,
        evidence_asset_ids: Sequence[int],
    ) -> ComplianceRecord:
        record = await self.get_record(record_id, tenant_id=tenant_id)
        await self._attach_evidence_assets(
            record,
            evidence_asset_ids=evidence_asset_ids,
            tenant_id=tenant_id,
        )
        await self.db.commit()
        await self.db.refresh(record)
        return record

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    async def get_stats(
        self,
        *,
        tenant_id: int,
        now: Optional[datetime] = None,
    ) -> dict[str, int]:
        query = select(ComplianceRequirement).where(
            ComplianceRequirement.deleted_at.is_(None),
            ComplianceRequirement.is_active.is_(True),
        )
        query = _tenant_filter(query, ComplianceRequirement, tenant_id)
        rows = list((await self.db.execute(query)).scalars().all())
        clock = _as_utc(now)
        current = due_soon = overdue = 0
        for row in rows:
            status = derive_status(clock, row.next_due_date)
            if status == "current":
                current += 1
            elif status == "due_soon":
                due_soon += 1
            elif status == "overdue":
                overdue += 1
        return {
            "total_active": len(rows),
            "current": current,
            "due_soon": due_soon,
            "overdue": overdue,
        }

    # ------------------------------------------------------------------
    # Wave 3 — location FRA / fire-drill coverage gaps
    # ------------------------------------------------------------------

    FRA_TEMPLATE_KEY = "fire_risk_assessment"
    DRILL_TEMPLATE_KEY = "fire_drill_evacuation"
    # Catalogue FRA / drill copy is "per premises"; W1 premises + office are the
    # statutory denominator. site/workshop stay out so CES plant sites do not
    # inflate false gaps.
    COVERAGE_LOCATION_KINDS = (LocationKind.PREMISES, LocationKind.OFFICE)

    async def get_location_coverage_gaps(
        self,
        *,
        tenant_id: int,
    ) -> dict[str, Any]:
        """Report active premises/offices missing an active FRA or fire-drill obligation.

        A gap means there is no **active, non-deleted** requirement for this tenant
        whose ``location_id`` equals the location and whose catalogue
        ``template_key`` is ``fire_risk_assessment`` or ``fire_drill_evacuation``.
        Organisation-wide rows (``location_id IS NULL``) do not cover a site —
        they are omitted from the match set on purpose. Only ``premises`` and
        ``office`` kinds enter the denominator.
        """
        loc_query = select(Location).where(
            Location.is_active.is_(True),
            Location.kind.in_(self.COVERAGE_LOCATION_KINDS),
        )
        loc_query = _tenant_filter(loc_query, Location, tenant_id)
        locations = list((await self.db.execute(loc_query)).scalars().all())

        req_query = (
            select(ComplianceRequirement, ComplianceRequirementTemplate.template_key)
            .outerjoin(
                ComplianceRequirementTemplate,
                ComplianceRequirement.template_id == ComplianceRequirementTemplate.id,
            )
            .where(
                ComplianceRequirement.deleted_at.is_(None),
                ComplianceRequirement.is_active.is_(True),
                ComplianceRequirement.location_id.is_not(None),
            )
        )
        req_query = _tenant_filter(req_query, ComplianceRequirement, tenant_id)
        covered_rows = list((await self.db.execute(req_query)).all())

        fra_by_location: dict[int, int] = {}
        drill_by_location: dict[int, int] = {}
        for requirement, template_key in covered_rows:
            loc_id = requirement.location_id
            if loc_id is None:
                continue
            if template_key == self.FRA_TEMPLATE_KEY:
                fra_by_location.setdefault(loc_id, requirement.id)
            elif template_key == self.DRILL_TEMPLATE_KEY:
                drill_by_location.setdefault(loc_id, requirement.id)

        items: list[dict[str, Any]] = []
        missing_fra = missing_drill = missing_both = 0
        for loc in sorted(locations, key=lambda row: (row.name or "").lower()):
            fra_id = fra_by_location.get(loc.id)
            drill_id = drill_by_location.get(loc.id)
            has_fra = fra_id is not None
            has_drill = drill_id is not None
            if not has_fra:
                missing_fra += 1
            if not has_drill:
                missing_drill += 1
            if not has_fra and not has_drill:
                missing_both += 1
            items.append(
                {
                    "location_id": loc.id,
                    "location_name": loc.name,
                    "location_kind": loc.kind.value if hasattr(loc.kind, "value") else str(loc.kind),
                    "has_fra": has_fra,
                    "has_fire_drill": has_drill,
                    "fra_requirement_id": fra_id,
                    "fire_drill_requirement_id": drill_id,
                    "missing_fra": not has_fra,
                    "missing_fire_drill": not has_drill,
                }
            )

        return {
            "total_locations": len(items),
            "missing_fra": missing_fra,
            "missing_fire_drill": missing_drill,
            "missing_both": missing_both,
            "items": items,
        }


__all__ = ["ComplianceScheduleService"]
