"""Near-miss management domain service.

Extracts business logic from near-miss routes into a testable service class.
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
from src.domain.models.near_miss import NearMiss
from src.domain.services.audit_service import record_audit_event
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)


class NearMissService:
    """Handles near-miss CRUD, reference number generation, and status transitions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_near_miss(
        self,
        *,
        data: BaseModel,
        user_id: int,
        tenant_id: int | None,
        request_id: str | None = None,
    ) -> NearMiss:
        """Create a new near-miss report.

        Raises:
            ValueError: If data validation fails.
        """
        reference_number = await ReferenceNumberService.generate(self.db, "near_miss", NearMiss)

        near_miss = NearMiss(
            **data.model_dump(),
            reference_number=reference_number,
            status="REPORTED",
            priority="MEDIUM",
            tenant_id=tenant_id,
            created_by_id=user_id,
            updated_by_id=user_id,
        )

        self.db.add(near_miss)
        await self.db.flush()

        await record_audit_event(
            db=self.db,
            event_type="near_miss.created",
            entity_type="near_miss",
            entity_id=str(near_miss.id),
            action="create",
            description=f"Near Miss {near_miss.reference_number} reported",
            payload=data.model_dump(mode="json"),
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.commit()
        await self.db.refresh(near_miss)
        await invalidate_tenant_cache(tenant_id, "near_miss")
        track_metric("near_miss.mutation", 1)

        return near_miss

    async def get_near_miss(self, near_miss_id: int, tenant_id: int | None) -> NearMiss:
        """Fetch a single near miss by ID.

        Raises:
            LookupError: If the near miss is not found.
        """
        result = await self.db.execute(
            select(NearMiss).where(NearMiss.id == near_miss_id, NearMiss.tenant_id == tenant_id)
        )
        near_miss = result.scalar_one_or_none()
        if near_miss is None:
            raise LookupError(f"Near miss with ID {near_miss_id} not found")
        return near_miss

    async def list_near_misses(
        self,
        *,
        tenant_id: int | None,
        params: PaginationParams,
        reporter_email: Optional[str] = None,
        status_filter: Optional[str] = None,
        priority: Optional[str] = None,
        contract: Optional[str] = None,
    ):
        """List near misses with pagination and optional filters."""
        query = (
            select(NearMiss)
            .where(NearMiss.tenant_id == tenant_id)
            .options(
                selectinload(NearMiss.assigned_to),
                selectinload(NearMiss.created_by),
                selectinload(NearMiss.updated_by),
                selectinload(NearMiss.closed_by),
            )
        )

        if reporter_email:
            query = query.where(NearMiss.reporter_email == reporter_email)
        if status_filter:
            query = query.where(NearMiss.status == status_filter)
        if priority:
            query = query.where(NearMiss.priority == priority)
        if contract:
            query = query.where(NearMiss.contract == contract)

        query = query.order_by(NearMiss.event_date.desc(), NearMiss.id.asc())
        return await paginate(self.db, query, params)

    async def update_near_miss(
        self,
        near_miss_id: int,
        data: BaseModel,
        *,
        user_id: int,
        tenant_id: int | None,
        request_id: str | None = None,
    ) -> NearMiss:
        """Partially update a near miss.

        Handles status transition side-effects (closed_at, assigned_at).

        Raises:
            LookupError: If the near miss is not found.
        """
        near_miss = await self.get_near_miss(near_miss_id, tenant_id)
        old_status = near_miss.status
        update_data = apply_updates(near_miss, data, set_updated_at=False)

        if "status" in update_data:
            if update_data["status"] == "CLOSED" and near_miss.closed_at is None:
                near_miss.closed_at = datetime.now(timezone.utc)
                near_miss.closed_by_id = user_id

        if "assigned_to_id" in update_data and near_miss.assigned_at is None:
            near_miss.assigned_at = datetime.now(timezone.utc)

        near_miss.updated_by_id = user_id

        await record_audit_event(
            db=self.db,
            event_type="near_miss.updated",
            entity_type="near_miss",
            entity_id=str(near_miss.id),
            action="update",
            description=f"Near Miss {near_miss.reference_number} updated",
            payload={"updates": update_data, "old_status": old_status, "new_status": near_miss.status},
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.commit()
        await self.db.refresh(near_miss)
        await invalidate_tenant_cache(tenant_id, "near_miss")
        track_metric("near_miss.mutation", 1)

        return near_miss

    async def delete_near_miss(
        self,
        near_miss_id: int,
        *,
        user_id: int,
        tenant_id: int | None,
        request_id: str | None = None,
    ) -> None:
        """Delete a near miss.

        Raises:
            LookupError: If the near miss is not found.
        """
        near_miss = await self.get_near_miss(near_miss_id, tenant_id)

        await record_audit_event(
            db=self.db,
            event_type="near_miss.deleted",
            entity_type="near_miss",
            entity_id=str(near_miss.id),
            action="delete",
            description=f"Near Miss {near_miss.reference_number} deleted",
            payload={"reference_number": near_miss.reference_number},
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.delete(near_miss)
        await self.db.commit()
        await invalidate_tenant_cache(tenant_id, "near_miss")
        track_metric("near_miss.mutation", 1)

    async def list_investigations(
        self,
        near_miss_id: int,
        *,
        tenant_id: int | None,
        params: PaginationParams,
    ):
        """List investigations linked to a near miss.

        Raises:
            LookupError: If the near miss is not found.
        """
        from src.domain.models.investigation import AssignedEntityType, InvestigationRun

        await self.get_near_miss(near_miss_id, tenant_id)

        query = (
            select(InvestigationRun)
            .where(
                InvestigationRun.assigned_entity_type == AssignedEntityType.NEAR_MISS,
                InvestigationRun.assigned_entity_id == near_miss_id,
            )
            .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())
        )
        return await paginate(self.db, query, params)
