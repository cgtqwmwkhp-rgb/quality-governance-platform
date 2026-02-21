"""Incident management domain service.

Extracts business logic from incident routes into a testable service class.
Raises domain exceptions instead of HTTPException.
"""

import logging
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.incident import Incident
from src.domain.services.audit_service import record_audit_event
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_business_event

logger = logging.getLogger(__name__)


class IncidentService:
    """Handles incident CRUD, reference number generation, and status transitions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_incident(
        self,
        *,
        incident_data: BaseModel,
        user_id: int,
        tenant_id: int | None,
        has_set_ref_permission: bool,
        request_id: str | None = None,
    ) -> Incident:
        """Create a new incident.

        Args:
            incident_data: Validated incident creation schema.
            user_id: ID of the creating user.
            tenant_id: Tenant scope.
            has_set_ref_permission: Whether the user can set explicit reference numbers.
            request_id: Correlation ID for audit trail.

        Raises:
            PermissionError: If user tries to set a reference number without permission.
            ValueError: If the supplied reference number already exists.
        """
        data = incident_data.model_dump()

        reference_number = data.get("reference_number")
        if reference_number:
            if not has_set_ref_permission:
                raise PermissionError("Not authorized to set explicit reference numbers")

            existing = await self.db.execute(select(Incident).where(Incident.reference_number == reference_number))
            if existing.scalar_one_or_none():
                raise ValueError("Duplicate reference number")
        else:
            reference_number = await ReferenceNumberService.generate(self.db, "incident", Incident)

        incident = Incident(
            title=data["title"],
            description=data["description"],
            incident_type=data.get("incident_type"),
            severity=data.get("severity"),
            status=data.get("status"),
            incident_date=data["incident_date"],
            reported_date=datetime.now(timezone.utc),
            location=data.get("location"),
            department=data.get("department"),
            reference_number=reference_number,
            reporter_id=user_id,
            reporter_email=data.get("reporter_email"),
            reporter_name=data.get("reporter_name"),
            created_by_id=user_id,
            updated_by_id=user_id,
            tenant_id=tenant_id,
        )

        self.db.add(incident)
        await self.db.flush()

        await record_audit_event(
            db=self.db,
            event_type="incident.created",
            entity_type="incident",
            entity_id=str(incident.id),
            action="create",
            description=f"Incident {incident.reference_number} created",
            payload=incident_data.model_dump(mode="json"),
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.commit()
        await self.db.refresh(incident)
        await invalidate_tenant_cache(tenant_id, "incidents")

        track_business_event("incident_created", {"severity": data.get("severity", "unknown")})

        return incident

    async def get_incident(self, incident_id: int, tenant_id: int | None) -> Incident:
        """Fetch a single incident by ID.

        Raises:
            LookupError: If the incident is not found.
        """
        result = await self.db.execute(
            select(Incident).where(Incident.id == incident_id, Incident.tenant_id == tenant_id)
        )
        incident = result.scalar_one_or_none()
        if incident is None:
            raise LookupError(f"Incident with ID {incident_id} not found")
        return incident

    async def list_incidents(
        self,
        *,
        tenant_id: int | None,
        params: PaginationParams,
        reporter_email: Optional[str] = None,
    ):
        """List incidents with pagination and optional filters."""
        query = (
            select(Incident)
            .options(
                selectinload(Incident.actions),
                selectinload(Incident.reporter),
            )
            .where(Incident.tenant_id == tenant_id)
        )

        if reporter_email:
            query = query.where(Incident.reporter_email == reporter_email)

        query = query.order_by(Incident.reported_date.desc(), Incident.id.asc())
        return await paginate(self.db, query, params)

    async def update_incident(
        self,
        incident_id: int,
        incident_data: BaseModel,
        *,
        user_id: int,
        tenant_id: int | None,
        request_id: str | None = None,
    ) -> Incident:
        """Partially update an incident.

        Raises:
            LookupError: If the incident is not found.
        """
        result = await self.db.execute(
            select(Incident).where(Incident.id == incident_id, Incident.tenant_id == tenant_id)
        )
        incident = result.scalar_one_or_none()
        if incident is None:
            raise LookupError(f"Incident with ID {incident_id} not found")

        update_dict = apply_updates(incident, incident_data, set_updated_at=False)

        incident.updated_by_id = user_id
        incident.updated_at = datetime.now(timezone.utc)

        await record_audit_event(
            db=self.db,
            event_type="incident.updated",
            entity_type="incident",
            entity_id=str(incident.id),
            action="update",
            description=f"Incident {incident.reference_number} updated",
            payload=update_dict,
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.commit()
        await self.db.refresh(incident)
        await invalidate_tenant_cache(tenant_id, "incidents")

        return incident

    async def delete_incident(
        self,
        incident_id: int,
        *,
        user_id: int,
        tenant_id: int | None,
        request_id: str | None = None,
    ) -> None:
        """Delete an incident.

        Raises:
            LookupError: If the incident is not found.
        """
        result = await self.db.execute(
            select(Incident).where(Incident.id == incident_id, Incident.tenant_id == tenant_id)
        )
        incident = result.scalar_one_or_none()
        if incident is None:
            raise LookupError(f"Incident with ID {incident_id} not found")

        await record_audit_event(
            db=self.db,
            event_type="incident.deleted",
            entity_type="incident",
            entity_id=str(incident.id),
            action="delete",
            description=f"Incident {incident.reference_number} deleted",
            payload={"incident_id": incident_id, "reference_number": incident.reference_number},
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.delete(incident)
        await self.db.commit()
        await invalidate_tenant_cache(tenant_id, "incidents")

    async def check_reporter_email_access(
        self,
        reporter_email: str,
        current_user_email: str | None,
        has_view_all: bool,
        is_superuser: bool,
    ) -> bool:
        """Check whether a user may filter incidents by a given reporter email.

        Returns True if access is allowed, False otherwise.
        """
        if has_view_all or is_superuser:
            return True
        if current_user_email and reporter_email.lower() == current_user_email.lower():
            return True
        return False
