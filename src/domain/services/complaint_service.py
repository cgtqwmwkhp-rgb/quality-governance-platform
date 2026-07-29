"""Complaint management domain service.

Extracts business logic from complaint routes into a testable service class.
Raises domain exceptions instead of HTTPException.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.pagination import PaginationInput, paginate
from src.core.update import apply_updates
from src.domain.exceptions import StateTransitionError
from src.domain.models.complaint import Complaint, ComplaintStatus
from src.domain.models.form_config import Contract
from src.domain.models.user import User
from src.domain.services.audit_service import record_audit_event
from src.domain.services.case_closure import (
    CASE_TYPE_COMPLAINT,
    apply_close_stamps,
    assert_case_can_close,
    clear_close_stamps,
    is_closed_status,
    resolve_case_tenant_id,
)
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)

COMPLAINT_TRANSITIONS: dict[ComplaintStatus, set[ComplaintStatus]] = {
    ComplaintStatus.RECEIVED: {ComplaintStatus.ACKNOWLEDGED, ComplaintStatus.ESCALATED},
    ComplaintStatus.ACKNOWLEDGED: {ComplaintStatus.UNDER_INVESTIGATION, ComplaintStatus.ESCALATED},
    ComplaintStatus.UNDER_INVESTIGATION: {ComplaintStatus.PENDING_RESPONSE, ComplaintStatus.ESCALATED},
    ComplaintStatus.PENDING_RESPONSE: {
        ComplaintStatus.AWAITING_CUSTOMER,
        ComplaintStatus.RESOLVED,
        ComplaintStatus.ESCALATED,
    },
    ComplaintStatus.AWAITING_CUSTOMER: {
        ComplaintStatus.UNDER_INVESTIGATION,
        ComplaintStatus.RESOLVED,
        ComplaintStatus.CLOSED,
    },
    ComplaintStatus.RESOLVED: {ComplaintStatus.CLOSED, ComplaintStatus.UNDER_INVESTIGATION},
    ComplaintStatus.ESCALATED: {ComplaintStatus.UNDER_INVESTIGATION, ComplaintStatus.CLOSED},
    # Reopen is a single controlled reverse edge, not a free jump back into the lifecycle.
    ComplaintStatus.CLOSED: {ComplaintStatus.UNDER_INVESTIGATION},
}


# PX-210: statuses that can only be reached after the complainant has actually
# been responded to, so entering one for the first time stamps first_response_at.
# "pending_response" is deliberately absent — it means a response is still owed.
RESPONDED_STATUSES: frozenset[ComplaintStatus] = frozenset(
    {
        ComplaintStatus.AWAITING_CUSTOMER,
        ComplaintStatus.RESOLVED,
        ComplaintStatus.CLOSED,
    }
)


def _as_status(value) -> Optional[ComplaintStatus]:
    """Coerce a status column value to its enum member, tolerating raw strings."""
    if isinstance(value, ComplaintStatus):
        return value
    try:
        return ComplaintStatus(getattr(value, "value", value))
    except (ValueError, TypeError):
        return None


def resolve_response_due_at(
    received_date: Optional[datetime],
    response_sla_hours: Optional[int],
    explicit_due_at: Optional[datetime],
) -> Optional[datetime]:
    """Work out the response deadline for a complaint.

    An explicitly supplied date always wins; otherwise the deadline is the agreed
    SLA measured from when the complaint was received. With no SLA and no explicit
    date there is no deadline — the caller must keep saying so rather than
    inventing one.
    """
    if explicit_due_at is not None:
        return explicit_due_at
    if response_sla_hours is None or received_date is None:
        return None
    if response_sla_hours <= 0:
        return None
    return received_date + timedelta(hours=response_sla_hours)


def validate_complaint_transition(current: str, target: str) -> None:
    """Validate a status transition for a complaint.

    Raises StateTransitionError if the transition is not allowed.

    Callers pass either the raw string or the enum member; the message must carry the
    value either way, because an f-string on a str-mixin enum renders its repr
    ("ComplaintStatus.ACKNOWLEDGED") from Python 3.11 onwards.
    """
    current_raw = getattr(current, "value", current)
    target_raw = getattr(target, "value", target)
    try:
        current_status = ComplaintStatus(current_raw)
        target_status = ComplaintStatus(target_raw)
    except ValueError:
        return
    allowed = COMPLAINT_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise StateTransitionError(
            f"Cannot transition from '{current_status.value}' to '{target_status.value}'",
            details={"allowed": sorted(s.value for s in allowed)},
        )


class ComplaintService:
    """Handles CRUD for complaints."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _assert_tenant_contract(self, contract_id: int, tenant_id: int) -> None:
        result = await self.db.execute(
            select(Contract.id).where(Contract.id == contract_id, Contract.tenant_id == tenant_id)
        )
        if result.scalar_one_or_none() is None:
            raise ValueError(f"Contract with ID {contract_id} not found")

    async def _assert_tenant_subject_user(self, subject_user_id: int, tenant_id: int) -> None:
        result = await self.db.execute(select(User).where(User.id == subject_user_id))
        user = result.scalar_one_or_none()
        if user is None or not user.is_active or user.tenant_id != tenant_id:
            raise ValueError(f"User with ID {subject_user_id} not found")

    @staticmethod
    def _apply_response_sla(complaint: Complaint, *, old_status, raw_update: dict) -> None:
        """Keep the response deadline and first-response stamp consistent (PX-210).

        Changing the agreed SLA re-derives the deadline from ``received_date``
        unless the same request also supplies an explicit ``response_due_at`` —
        including when the SLA is cleared, because a deadline derived from an SLA
        that no longer exists is a deadline nobody agreed to.

        ``first_response_at`` is stamped once, the first time the complaint reaches
        a status that cannot be reached without having answered the complainant.
        An explicit value in the request always wins.
        """
        if "response_sla_hours" in raw_update and "response_due_at" not in raw_update:
            complaint.response_due_at = resolve_response_due_at(
                complaint.received_date, complaint.response_sla_hours, None
            )

        if complaint.first_response_at is not None or "first_response_at" in raw_update:
            return
        if _as_status(complaint.status) in RESPONDED_STATUSES and _as_status(old_status) not in RESPONDED_STATUSES:
            complaint.first_response_at = datetime.now(timezone.utc)

    async def create_complaint(
        self,
        *,
        complaint_data: BaseModel,
        user_id: int,
        tenant_id: int | None,
        request_id: str | None = None,
    ) -> Complaint:
        """Create a new complaint.

        Raises:
            ValueError: If a duplicate external_ref is found (409 semantics).
        """
        data = complaint_data.model_dump()
        external_ref = data.get("external_ref")

        if external_ref:
            existing_result = await self.db.execute(select(Complaint).where(Complaint.external_ref == external_ref))
            existing = existing_result.scalar_one_or_none()
            if existing:
                raise ValueError(f"DUPLICATE_EXTERNAL_REF:{existing.id}:{existing.reference_number}")

        if tenant_id is not None:
            contract_id = data.get("contract_id")
            if contract_id is not None:
                await self._assert_tenant_contract(int(contract_id), tenant_id)
            subject_user_id = data.get("subject_user_id")
            if subject_user_id is not None:
                await self._assert_tenant_subject_user(int(subject_user_id), tenant_id)

        data["response_due_at"] = resolve_response_due_at(
            data.get("received_date"),
            data.get("response_sla_hours"),
            data.get("response_due_at"),
        )

        ref_num = await ReferenceNumberService.generate(self.db, "complaint", Complaint)

        complaint = Complaint(
            **data,
            reference_number=ref_num,
            tenant_id=tenant_id,
            created_by_id=user_id,
        )

        self.db.add(complaint)
        await self.db.flush()
        await self.db.refresh(complaint)

        await record_audit_event(
            db=self.db,
            event_type="complaint.created",
            entity_type="complaint",
            entity_id=str(complaint.id),
            entity_name=complaint.reference_number,
            action="create",
            payload=complaint_data.model_dump(mode="json"),
            user_id=user_id,
            request_id=request_id,
            tenant_id=tenant_id,
        )

        await self.db.flush()
        if tenant_id is not None:
            await invalidate_tenant_cache(tenant_id, "complaints")
        track_metric("complaints.created")

        return complaint

    async def get_complaint(
        self, complaint_id: int, tenant_id: int | None, *, skip_tenant_check: bool = False
    ) -> Complaint:
        """Fetch a single complaint by ID.

        Raises:
            LookupError: If not found.
        """
        query = select(Complaint).where(Complaint.id == complaint_id)
        if not skip_tenant_check:
            query = query.where(Complaint.tenant_id == tenant_id)
        result = await self.db.execute(query)
        complaint = result.scalar_one_or_none()
        if complaint is None:
            raise LookupError(f"Complaint with ID {complaint_id} not found")
        return complaint

    async def list_complaints(
        self,
        *,
        tenant_id: int | None,
        params: PaginationInput,
        status_filter: Optional[str] = None,
        complainant_email: Optional[str] = None,
    ):
        """List complaints with pagination and optional filters."""
        query = select(Complaint).options(selectinload(Complaint.actions)).where(Complaint.tenant_id == tenant_id)

        if complainant_email:
            query = query.where(Complaint.complainant_email == complainant_email)
        if status_filter:
            query = query.where(Complaint.status == status_filter)

        query = query.order_by(Complaint.received_date.desc(), Complaint.id.asc())
        return await paginate(self.db, query, params)

    async def update_complaint(
        self,
        complaint_id: int,
        complaint_data: BaseModel,
        *,
        user_id: int,
        tenant_id: int | None,
        request_id: str | None = None,
        skip_tenant_check: bool = False,
    ) -> Complaint:
        """Partially update a complaint.

        Raises:
            LookupError: If not found.
            StateTransitionError: If a status transition is invalid.
        """
        complaint = await self.get_complaint(complaint_id, tenant_id, skip_tenant_check=skip_tenant_check)
        old_status = complaint.status

        raw_update = complaint_data.model_dump(exclude_unset=True)
        was_closed = is_closed_status(CASE_TYPE_COMPLAINT, old_status)
        closing = False
        if "status" in raw_update:
            validate_complaint_transition(old_status, raw_update["status"])
            closing = not was_closed and is_closed_status(CASE_TYPE_COMPLAINT, raw_update["status"])

        if closing:
            # Gate before any mutation so a refused close leaves the session clean.
            # "resolved" stays ungated — it is a pre-close state, not closure.
            await assert_case_can_close(
                self.db,
                case_type=CASE_TYPE_COMPLAINT,
                case=complaint,
                tenant_id=resolve_case_tenant_id(complaint),
                lessons_learnt=(
                    raw_update["lessons_learnt"] if "lessons_learnt" in raw_update else complaint.lessons_learnt
                ),
            )

        apply_updates(complaint, complaint_data, set_updated_at=False)
        self._apply_response_sla(complaint, old_status=old_status, raw_update=raw_update)

        reopening = was_closed and not is_closed_status(CASE_TYPE_COMPLAINT, complaint.status)
        if closing:
            apply_close_stamps(complaint, user_id=user_id)
        elif reopening:
            clear_close_stamps(complaint)

        # The audit entry lands in a JSON column, so the payload has to be
        # JSON-native. apply_updates returns Python objects, which meant patching
        # any date field on a complaint blew up on insert; create_complaint has
        # always dumped in json mode for the same reason.
        update_data = complaint_data.model_dump(exclude_unset=True, mode="json")

        await self.db.flush()
        await self.db.refresh(complaint)

        lifecycle = "closed" if closing else "reopened" if reopening else "updated"
        await record_audit_event(
            db=self.db,
            event_type=f"complaint.{lifecycle}",
            entity_type="complaint",
            entity_id=str(complaint.id),
            entity_name=complaint.reference_number,
            action="update",
            payload={
                "updates": update_data,
                "old_status": old_status,
                "new_status": complaint.status,
            },
            user_id=user_id,
            request_id=request_id,
            # The record's own tenant, not the tenant_id argument: callers pass
            # None with skip_tenant_check=True, and the row still has an owner.
            tenant_id=complaint.tenant_id,
        )

        await self.db.flush()
        # The row's tenant, not the caller's: a cross-tenant edit has to evict the
        # register the record actually appears in.
        cache_tenant_id = complaint.tenant_id if complaint.tenant_id is not None else tenant_id
        if cache_tenant_id is not None:
            await invalidate_tenant_cache(cache_tenant_id, "complaints")

        return complaint

    def check_complainant_email_access(
        self,
        complainant_email: str,
        current_user_email: str | None,
        has_view_all: bool,
        is_superuser: bool,
    ) -> bool:
        """Check whether a user may filter complaints by a given email."""
        if has_view_all or is_superuser:
            return True
        if current_user_email and complainant_email.lower() == current_user_email.lower():
            return True
        return False

    async def list_complaint_investigations(
        self,
        complaint_id: int,
        tenant_id: int | None,
        params: PaginationInput,
    ):
        """List investigations for a specific complaint (paginated).

        Raises:
            LookupError: If the complaint is not found.
        """
        from src.domain.models.investigation import AssignedEntityType, InvestigationRun

        await self.get_complaint(complaint_id, tenant_id)

        query = (
            select(InvestigationRun)
            .where(
                InvestigationRun.assigned_entity_type == AssignedEntityType.COMPLAINT,
                InvestigationRun.assigned_entity_id == complaint_id,
            )
            .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())
        )
        return await paginate(self.db, query, params)
