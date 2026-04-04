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

from src.core.pagination import PaginationInput, paginate
from src.core.update import apply_updates
from src.domain.exceptions import StateTransitionError
from src.domain.models.incident import Incident, IncidentStatus
from src.domain.services.audit_service import record_audit_event
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_business_event

logger = logging.getLogger(__name__)

INCIDENT_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.REPORTED: {IncidentStatus.UNDER_INVESTIGATION, IncidentStatus.CLOSED},
    IncidentStatus.UNDER_INVESTIGATION: {IncidentStatus.PENDING_ACTIONS, IncidentStatus.CLOSED},
    IncidentStatus.PENDING_ACTIONS: {IncidentStatus.ACTIONS_IN_PROGRESS, IncidentStatus.CLOSED},
    IncidentStatus.ACTIONS_IN_PROGRESS: {IncidentStatus.PENDING_REVIEW, IncidentStatus.PENDING_ACTIONS},
    IncidentStatus.PENDING_REVIEW: {IncidentStatus.CLOSED, IncidentStatus.ACTIONS_IN_PROGRESS},
    IncidentStatus.CLOSED: set(),
}


def validate_incident_transition(current: str, target: str) -> None:
    """Validate a status transition for an incident.

    Raises StateTransitionError if the transition is not allowed.
    """
    try:
        current_status = IncidentStatus(current)
        target_status = IncidentStatus(target)
    except ValueError:
        return
    allowed = INCIDENT_TRANSITIONS.get(current_status, set())
    if target_status not in allowed:
        raise StateTransitionError(
            f"Cannot transition from '{current}' to '{target}'",
            details={"allowed": sorted(s.value for s in allowed)},
        )


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

        await self.db.flush()
        await self.db.refresh(incident)
        await invalidate_tenant_cache(tenant_id, "incidents")

        track_business_event("incident_created", {"severity": data.get("severity", "unknown")})
        from src.infrastructure.monitoring.azure_monitor import record_incident_created

        record_incident_created()

        return incident

    async def get_incident(
        self, incident_id: int, tenant_id: int | None, *, skip_tenant_check: bool = False
    ) -> Incident:
        """Fetch a single incident by ID.

        Args:
            incident_id: Primary key.
            tenant_id: Tenant scope (ignored when skip_tenant_check is True).
            skip_tenant_check: If True, bypasses tenant isolation (superuser).

        Raises:
            LookupError: If the incident is not found.
        """
        query = select(Incident).where(Incident.id == incident_id)
        if not skip_tenant_check:
            query = query.where(Incident.tenant_id == tenant_id)
        result = await self.db.execute(query)
        incident = result.scalar_one_or_none()
        if incident is None:
            raise LookupError(f"Incident with ID {incident_id} not found")
        return incident

    async def list_incidents(
        self,
        *,
        tenant_id: int | None,
        params: PaginationInput,
        reporter_email: Optional[str] = None,
        skip_tenant_check: bool = False,
    ):
        """List incidents with pagination and optional filters."""
        query = select(Incident).options(
            selectinload(Incident.actions),
        )

        if not skip_tenant_check:
            query = query.where(Incident.tenant_id == tenant_id)

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
        skip_tenant_check: bool = False,
    ) -> Incident:
        """Partially update an incident.

        Raises:
            LookupError: If the incident is not found.
            StateTransitionError: If a status transition is invalid.
        """
        incident = await self.get_incident(incident_id, tenant_id, skip_tenant_check=skip_tenant_check)

        raw_update = incident_data.model_dump(exclude_unset=True)
        if "status" in raw_update:
            validate_incident_transition(incident.status, raw_update["status"])

        update_dict = apply_updates(incident, incident_data, set_updated_at=False)

        incident.updated_by_id = user_id
        incident.updated_at = datetime.now(timezone.utc)

        await self.db.flush()

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

        await self.db.flush()
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
        skip_tenant_check: bool = False,
    ) -> None:
        """Delete an incident.

        Raises:
            LookupError: If the incident is not found.
        """
        incident = await self.get_incident(incident_id, tenant_id, skip_tenant_check=skip_tenant_check)

        await record_audit_event(
            db=self.db,
            event_type="incident.deleted",
            entity_type="incident",
            entity_id=str(incident.id),
            action="delete",
            description=f"Incident {incident.reference_number} deleted",
            payload={
                "incident_id": incident_id,
                "reference_number": incident.reference_number,
            },
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.delete(incident)
        await self.db.flush()
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
