"""Road Traffic Collision domain service.

Extracts business logic from RTA routes into a testable service class.
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
from src.domain.models.rta import RoadTrafficCollision, RTAAction
from src.domain.services.audit_service import record_audit_event
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)


class RTAService:
    """Handles CRUD for Road Traffic Collisions and their actions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ---- RTA CRUD ----

    async def create_rta(
        self,
        *,
        rta_data: BaseModel,
        user_id: int,
        tenant_id: int | None,
        request_id: str | None = None,
    ) -> RoadTrafficCollision:
        """Create a new RTA with auto-generated reference number."""
        ref_number = await ReferenceNumberService.generate(self.db, "rta", RoadTrafficCollision)
        rta = RoadTrafficCollision(
            **rta_data.model_dump(),
            reference_number=ref_number,
            tenant_id=tenant_id,
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        self.db.add(rta)
        await self.db.flush()

        await record_audit_event(
            db=self.db,
            event_type="rta.created",
            entity_type="rta",
            entity_id=str(rta.id),
            action="create",
            description=f"RTA {rta.reference_number} created",
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.commit()
        await self.db.refresh(rta)
        await invalidate_tenant_cache(tenant_id, "rtas")
        track_metric("rta.mutation", 1)
        track_metric("rta.created", 1)
        return rta

    async def get_rta(self, rta_id: int, tenant_id: int | None) -> RoadTrafficCollision:
        """Fetch a single RTA by ID.

        Raises:
            LookupError: If not found.
        """
        result = await self.db.execute(
            select(RoadTrafficCollision).where(
                RoadTrafficCollision.id == rta_id,
                RoadTrafficCollision.tenant_id == tenant_id,
            )
        )
        rta = result.scalar_one_or_none()
        if rta is None:
            raise LookupError(f"RTA with ID {rta_id} not found")
        return rta

    async def list_rtas(
        self,
        *,
        tenant_id: int | None,
        params: PaginationParams,
        severity: Optional[str] = None,
        status_filter: Optional[str] = None,
        reporter_email: Optional[str] = None,
    ):
        """List RTAs with pagination and optional filters."""
        query = (
            select(RoadTrafficCollision)
            .options(selectinload(RoadTrafficCollision.actions))
            .where(RoadTrafficCollision.tenant_id == tenant_id)
        )

        if severity:
            query = query.where(RoadTrafficCollision.severity == severity)
        if status_filter:
            query = query.where(RoadTrafficCollision.status == status_filter)
        if reporter_email:
            query = query.where(RoadTrafficCollision.reporter_email == reporter_email)

        query = query.order_by(
            RoadTrafficCollision.created_at.desc(),
            RoadTrafficCollision.id.asc(),
        )
        return await paginate(self.db, query, params)

    async def update_rta(
        self,
        rta_id: int,
        rta_data: BaseModel,
        *,
        user_id: int,
        tenant_id: int | None,
        request_id: str | None = None,
    ) -> RoadTrafficCollision:
        """Partially update an RTA.

        Raises:
            LookupError: If not found.
        """
        rta = await self.get_rta(rta_id, tenant_id)
        update_data = apply_updates(rta, rta_data)
        rta.updated_by_id = user_id

        await record_audit_event(
            db=self.db,
            event_type="rta.updated",
            entity_type="rta",
            entity_id=str(rta.id),
            action="update",
            description=f"RTA {rta.reference_number} updated",
            payload=update_data,
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.commit()
        await self.db.refresh(rta)
        await invalidate_tenant_cache(tenant_id, "rtas")
        track_metric("rta.mutation", 1)
        return rta

    async def delete_rta(
        self,
        rta_id: int,
        *,
        user_id: int,
        tenant_id: int | None,
        request_id: str | None = None,
    ) -> None:
        """Delete an RTA.

        Raises:
            LookupError: If not found.
        """
        rta = await self.get_rta(rta_id, tenant_id)

        await record_audit_event(
            db=self.db,
            event_type="rta.deleted",
            entity_type="rta",
            entity_id=str(rta.id),
            action="delete",
            description=f"RTA {rta.reference_number} deleted",
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.delete(rta)
        await self.db.commit()
        await invalidate_tenant_cache(tenant_id, "rtas")
        track_metric("rta.mutation", 1)

    # ---- Email access check ----

    def check_reporter_email_access(
        self,
        reporter_email: str,
        current_user_email: str | None,
        has_view_all: bool,
        is_superuser: bool,
    ) -> bool:
        """Check whether a user may filter RTAs by a given reporter email."""
        if has_view_all or is_superuser:
            return True
        if current_user_email and reporter_email.lower() == current_user_email.lower():
            return True
        return False

    # ---- RTA Actions ----

    async def create_rta_action(
        self,
        rta_id: int,
        action_data: BaseModel,
        *,
        user_id: int,
        tenant_id: int | None,
        request_id: str | None = None,
    ) -> RTAAction:
        """Create a new action for an RTA.

        Raises:
            LookupError: If the parent RTA is not found.
        """
        rta = await self.get_rta(rta_id, tenant_id)
        ref_number = await ReferenceNumberService.generate(self.db, "rta_action", RTAAction)

        action = RTAAction(
            **action_data.model_dump(),
            rta_id=rta_id,
            reference_number=ref_number,
            tenant_id=tenant_id,
            created_by_id=user_id,
            updated_by_id=user_id,
        )
        self.db.add(action)
        await self.db.flush()

        await record_audit_event(
            db=self.db,
            event_type="rta_action.created",
            entity_type="rta_action",
            entity_id=str(action.id),
            action="create",
            description=f"RTA Action {action.reference_number} created for RTA {rta.reference_number}",
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.commit()
        await self.db.refresh(action)
        return action

    async def list_rta_actions(
        self,
        rta_id: int,
        tenant_id: int | None,
        params: PaginationParams,
    ):
        """List actions for an RTA with pagination.

        Raises:
            LookupError: If the parent RTA is not found.
        """
        await self.get_rta(rta_id, tenant_id)

        query = (
            select(RTAAction)
            .where(RTAAction.rta_id == rta_id)
            .order_by(RTAAction.created_at.desc(), RTAAction.id.asc())
        )
        return await paginate(self.db, query, params)

    async def update_rta_action(
        self,
        rta_id: int,
        action_id: int,
        action_data: BaseModel,
        *,
        user_id: int,
        tenant_id: int | None,
        request_id: str | None = None,
    ) -> RTAAction:
        """Update an RTA action.

        Raises:
            LookupError: If the RTA or action is not found, or action doesn't belong to RTA.
        """
        await self.get_rta(rta_id, tenant_id)
        action = await self._get_rta_action_or_raise(action_id, tenant_id)
        if action.rta_id != rta_id:
            raise LookupError(f"RTAAction {action_id} does not belong to RTA {rta_id}")

        update_data = apply_updates(action, action_data)
        action.updated_by_id = user_id

        await record_audit_event(
            db=self.db,
            event_type="rta_action.updated",
            entity_type="rta_action",
            entity_id=str(action.id),
            action="update",
            description=f"RTA Action {action.reference_number} updated",
            payload=update_data,
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.commit()
        await self.db.refresh(action)
        return action

    async def delete_rta_action(
        self,
        rta_id: int,
        action_id: int,
        *,
        user_id: int,
        tenant_id: int | None,
        request_id: str | None = None,
    ) -> None:
        """Delete an RTA action.

        Raises:
            LookupError: If the RTA or action is not found, or action doesn't belong to RTA.
        """
        await self.get_rta(rta_id, tenant_id)
        action = await self._get_rta_action_or_raise(action_id, tenant_id)
        if action.rta_id != rta_id:
            raise LookupError(f"RTAAction {action_id} does not belong to RTA {rta_id}")

        await record_audit_event(
            db=self.db,
            event_type="rta_action.deleted",
            entity_type="rta_action",
            entity_id=str(action.id),
            action="delete",
            description=f"RTA Action {action.reference_number} deleted",
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.delete(action)
        await self.db.commit()

    async def list_rta_investigations(
        self,
        rta_id: int,
        tenant_id: int | None,
        params: PaginationParams,
    ):
        """List investigations for a specific RTA (paginated).

        Raises:
            LookupError: If the parent RTA is not found.
        """
        from src.domain.models.investigation import AssignedEntityType, InvestigationRun

        await self.get_rta(rta_id, tenant_id)

        query = (
            select(InvestigationRun)
            .where(
                InvestigationRun.assigned_entity_type == AssignedEntityType.ROAD_TRAFFIC_COLLISION,
                InvestigationRun.assigned_entity_id == rta_id,
            )
            .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())
        )
        return await paginate(self.db, query, params)

    # ---- Helpers ----

    async def _get_rta_action_or_raise(self, action_id: int, tenant_id: int | None) -> RTAAction:
        result = await self.db.execute(
            select(RTAAction).where(
                RTAAction.id == action_id,
                RTAAction.tenant_id == tenant_id,
            )
        )
        action = result.scalar_one_or_none()
        if action is None:
            raise LookupError(f"RTAAction with ID {action_id} not found")
        return action
