"""Complaint management domain service.

Extracts business logic from complaint routes into a testable service class.
Raises domain exceptions instead of HTTPException.
"""

import logging
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.pagination import PaginationParams, paginate
from src.core.update import apply_updates
from src.domain.exceptions import StateTransitionError
from src.domain.models.complaint import Complaint, ComplaintStatus
from src.domain.services.audit_service import record_audit_event
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
    ComplaintStatus.CLOSED: set(),
}


def validate_complaint_transition(current: str, target: str) -> None:
    """Validate a status transition for a complaint.

    Raises StateTransitionError if the transition is not allowed.
    """
    try:
        current_status = ComplaintStatus(current)
        target_status = ComplaintStatus(target)
    except ValueError:
        return
    allowed = COMPLAINT_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise StateTransitionError(
            f"Cannot transition from '{current}' to '{target}'",
            details={"allowed": sorted(s.value for s in allowed)},
        )


class ComplaintService:
    """Handles CRUD for complaints."""

    def __init__(self, db: AsyncSession):
        self.db = db

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

        ref_num = await ReferenceNumberService.generate(self.db, "complaint", Complaint)

        complaint = Complaint(
            **data,
            reference_number=ref_num,
            tenant_id=tenant_id,
        )

        self.db.add(complaint)
        await self.db.flush()
        await self.db.refresh(complaint)

        await record_audit_event(
            db=self.db,
            event_type="complaint.created",
            entity_type="complaint",
            entity_id=str(complaint.id),
            action="create",
            payload=complaint_data.model_dump(mode="json"),
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.flush()
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
        params: PaginationParams,
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
        if "status" in raw_update:
            validate_complaint_transition(old_status, raw_update["status"])

        update_data = apply_updates(complaint, complaint_data, set_updated_at=False)

        await self.db.flush()
        await self.db.refresh(complaint)

        await record_audit_event(
            db=self.db,
            event_type="complaint.updated",
            entity_type="complaint",
            entity_id=str(complaint.id),
            action="update",
            payload={
                "updates": update_data,
                "old_status": old_status,
                "new_status": complaint.status,
            },
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.flush()
        await invalidate_tenant_cache(tenant_id, "complaints")

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
        params: PaginationParams,
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
