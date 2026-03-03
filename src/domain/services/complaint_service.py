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

from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.complaint import Complaint
from src.domain.services.audit_service import record_audit_event
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)


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
        await self.db.commit()
        await self.db.refresh(complaint)
        await invalidate_tenant_cache(tenant_id, "complaints")
        track_metric("complaints.created")

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

        return complaint

    async def get_complaint(self, complaint_id: int, tenant_id: int | None) -> Complaint:
        """Fetch a single complaint by ID.

        Raises:
            LookupError: If not found.
        """
        result = await self.db.execute(
            select(Complaint).where(
                Complaint.id == complaint_id,
                Complaint.tenant_id == tenant_id,
            )
        )
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
    ) -> Complaint:
        """Partially update a complaint.

        Raises:
            LookupError: If not found.
        """
        complaint = await self.get_complaint(complaint_id, tenant_id)
        old_status = complaint.status
        update_data = apply_updates(complaint, complaint_data, set_updated_at=False)

        await self.db.commit()
        await self.db.refresh(complaint)
        await invalidate_tenant_cache(tenant_id, "complaints")

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
