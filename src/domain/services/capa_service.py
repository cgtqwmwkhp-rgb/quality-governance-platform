"""CAPA (Corrective and Preventive Action) domain service.

Extracts business logic from CAPA routes into a testable service class.
Raises domain exceptions instead of HTTPException.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.utils.pagination import PaginationParams, paginate
from src.api.utils.update import apply_updates
from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.services.audit_service import record_audit_event
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)


class CAPAService:
    """Handles CRUD and status transitions for CAPA actions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    VALID_TRANSITIONS: dict[CAPAStatus, list[CAPAStatus]] = {
        CAPAStatus.OPEN: [CAPAStatus.IN_PROGRESS],
        CAPAStatus.IN_PROGRESS: [CAPAStatus.VERIFICATION, CAPAStatus.OPEN],
        CAPAStatus.VERIFICATION: [CAPAStatus.CLOSED, CAPAStatus.IN_PROGRESS],
        CAPAStatus.OVERDUE: [CAPAStatus.IN_PROGRESS, CAPAStatus.CLOSED],
    }

    async def list_capa_actions(
        self,
        *,
        tenant_id: int | None,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[CAPAStatus] = None,
        capa_type: Optional[CAPAType] = None,
        priority: Optional[CAPAPriority] = None,
        source_type: Optional[CAPASource] = None,
        overdue_only: bool = False,
    ):
        """List CAPA actions with pagination and filters."""
        query = select(CAPAAction).where(CAPAAction.tenant_id == tenant_id)

        if status_filter:
            query = query.where(CAPAAction.status == status_filter)
        if capa_type:
            query = query.where(CAPAAction.capa_type == capa_type)
        if priority:
            query = query.where(CAPAAction.priority == priority)
        if source_type:
            query = query.where(CAPAAction.source_type == source_type)
        if overdue_only:
            query = query.where(
                CAPAAction.due_date < datetime.now(timezone.utc),
                CAPAAction.status.notin_([CAPAStatus.CLOSED.value]),
            )

        query = query.order_by(CAPAAction.created_at.desc())
        params = PaginationParams(page=page, page_size=page_size)  # type: ignore[call-arg]  # TYPE-IGNORE: MYPY-OVERRIDE
        return await paginate(self.db, query, params)

    async def create_capa_action(
        self,
        *,
        data: BaseModel,
        user_id: int,
        tenant_id: int | None,
    ) -> CAPAAction:
        """Create a new CAPA action with auto-generated reference number."""
        ref = await ReferenceNumberService.generate(self.db, "capa", CAPAAction)
        action = CAPAAction(
            reference_number=ref,
            created_by_id=user_id,
            tenant_id=tenant_id,
            **data.model_dump(),
        )
        self.db.add(action)
        await self.db.commit()
        await self.db.refresh(action)
        await invalidate_tenant_cache(tenant_id, "capa")
        track_metric("capa.created")

        await record_audit_event(
            db=self.db,
            event_type="capa.created",
            entity_type="capa",
            entity_id=str(action.id),
            action="create",
            description=f"CAPA {action.reference_number} created",
            payload=data.model_dump(mode="json"),
            user_id=user_id,
        )

        return action

    async def get_capa_action(self, capa_id: int, tenant_id: int | None) -> CAPAAction:
        """Fetch a single CAPA by ID.

        Raises:
            LookupError: If not found.
        """
        result = await self.db.execute(
            select(CAPAAction).where(
                CAPAAction.id == capa_id,
                CAPAAction.tenant_id == tenant_id,
            )
        )
        action = result.scalar_one_or_none()
        if action is None:
            raise LookupError(f"CAPA with ID {capa_id} not found")
        return action

    async def update_capa_action(
        self,
        capa_id: int,
        data: BaseModel,
        *,
        tenant_id: int | None,
    ) -> CAPAAction:
        """Partially update a CAPA action.

        Raises:
            LookupError: If not found.
        """
        action = await self.get_capa_action(capa_id, tenant_id)
        apply_updates(action, data)
        await self.db.commit()
        await self.db.refresh(action)
        await invalidate_tenant_cache(tenant_id, "capa")
        return action

    async def transition_status(
        self,
        capa_id: int,
        new_status: CAPAStatus,
        *,
        user_id: int,
        tenant_id: int | None,
        comment: str | None = None,
    ) -> CAPAAction:
        """Transition a CAPA action to a new status.

        Raises:
            LookupError: If not found.
            ValueError: If the transition is invalid.
        """
        action = await self.get_capa_action(capa_id, tenant_id)
        current = action.status

        if new_status not in self.VALID_TRANSITIONS.get(current, []):
            raise ValueError(f"Invalid status transition from {current} to {new_status}")

        action.status = new_status
        if new_status == CAPAStatus.VERIFICATION:
            action.completed_at = datetime.now(timezone.utc)
        elif new_status == CAPAStatus.CLOSED:
            action.verified_at = datetime.now(timezone.utc)
            action.verified_by_id = user_id
            track_metric("capa.closed")

        await record_audit_event(
            db=self.db,
            event_type="capa.status_changed",
            entity_type="capa",
            entity_id=str(action.id),
            action="update",
            description=f"CAPA {action.reference_number} transitioned from {current} to {new_status}",
            payload={
                "from_status": str(current),
                "to_status": str(new_status),
                "comment": comment,
            },
            user_id=user_id,
        )

        await self.db.commit()
        await self.db.refresh(action)
        return action

    async def delete_capa_action(
        self,
        capa_id: int,
        *,
        user_id: int,
        tenant_id: int | None,
    ) -> None:
        """Delete a CAPA action.

        Raises:
            LookupError: If not found.
        """
        action = await self.get_capa_action(capa_id, tenant_id)

        await record_audit_event(
            db=self.db,
            event_type="capa.deleted",
            entity_type="capa",
            entity_id=str(action.id),
            action="delete",
            description=f"CAPA {action.reference_number} deleted",
            payload={
                "capa_id": capa_id,
                "reference_number": action.reference_number,
            },
            user_id=user_id,
        )

        await self.db.delete(action)
        await self.db.commit()
        await invalidate_tenant_cache(tenant_id, "capa")

    async def get_stats(self, tenant_id: int | None) -> dict[str, int]:
        """Get aggregate CAPA statistics for a tenant."""
        tenant_filter = CAPAAction.tenant_id == tenant_id

        total = await self.db.execute(select(func.count(CAPAAction.id)).where(tenant_filter))
        open_count = await self.db.execute(
            select(func.count(CAPAAction.id)).where(tenant_filter, CAPAAction.status == CAPAStatus.OPEN)
        )
        in_progress = await self.db.execute(
            select(func.count(CAPAAction.id)).where(tenant_filter, CAPAAction.status == CAPAStatus.IN_PROGRESS)
        )
        overdue = await self.db.execute(
            select(func.count(CAPAAction.id)).where(
                tenant_filter,
                CAPAAction.due_date < datetime.now(timezone.utc),
                CAPAAction.status.notin_([CAPAStatus.CLOSED.value]),
            )
        )
        return {
            "total": total.scalar_one(),
            "open": open_count.scalar_one(),
            "in_progress": in_progress.scalar_one(),
            "overdue": overdue.scalar_one(),
        }
