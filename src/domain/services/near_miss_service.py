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

from src.core.pagination import PaginationInput, paginate
from src.core.update import apply_updates
from src.domain.exceptions import StateTransitionError
from src.domain.models.form_config import Contract
from src.domain.models.near_miss import NearMiss
from src.domain.services.audit_service import record_audit_event
from src.domain.services.contract_resolve import assert_tenant_contract, resolve_contract_id_by_code
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)


async def resolve_near_miss_contract(
    db: AsyncSession,
    *,
    tenant_id: int | None,
    contract_id: Optional[int],
    contract: Optional[str],
) -> tuple[Optional[int], Optional[str]]:
    """Validate/resolve the contract_id <-> legacy `contract` code pair.

    Customer/contract SSOT for near misses, mirroring Incident.contract_id /
    Complaint.contract_id:

    - ``contract_id`` supplied: validate it belongs to the tenant (raises
      ``ValueError`` otherwise), and backfill a blank ``contract`` display
      string from the resolved Contract.code for legacy read compatibility.
    - ``contract_id`` absent but a legacy ``contract`` code string is
      supplied: best-effort resolve it to ``contracts.id`` via the
      customers-lookup bridge. Silently leaves ``contract_id`` unset (None)
      when no match exists — never blocks the write.

    Raises:
        ValueError: If ``contract_id`` is supplied but not owned by the tenant.
    """
    resolved_contract_id = contract_id
    resolved_contract = contract

    if contract_id is not None:
        if tenant_id is not None:
            await assert_tenant_contract(db, contract_id=contract_id, tenant_id=tenant_id)
        if not (resolved_contract or "").strip():
            result = await db.execute(select(Contract).where(Contract.id == contract_id))
            contract_row = result.scalar_one_or_none()
            if contract_row is not None:
                resolved_contract = contract_row.code or contract_row.name
    elif tenant_id is not None and (contract or "").strip():
        resolved_contract_id = await resolve_contract_id_by_code(db, tenant_id=tenant_id, code=contract)

    return resolved_contract_id, resolved_contract


class NearMissService:
    """Handles near-miss CRUD, reference number generation, and status transitions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    VALID_TRANSITIONS: dict[str, set[str]] = {
        "REPORTED": {"UNDER_REVIEW", "CLOSED"},
        "UNDER_REVIEW": {"ACTION_REQUIRED", "IN_PROGRESS", "CLOSED"},
        "ACTION_REQUIRED": {"IN_PROGRESS", "CLOSED"},
        "IN_PROGRESS": {"CLOSED", "ACTION_REQUIRED"},
        "CLOSED": set(),
    }

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
            ValueError: If data validation fails, or contract_id is not owned
                by the tenant.
        """
        reference_number = await ReferenceNumberService.generate(self.db, "near_miss", NearMiss)

        payload = data.model_dump()
        resolved_contract_id, resolved_contract = await resolve_near_miss_contract(
            self.db,
            tenant_id=tenant_id,
            contract_id=payload.get("contract_id"),
            contract=payload.get("contract"),
        )
        payload["contract_id"] = resolved_contract_id
        payload["contract"] = resolved_contract or "Not specified"

        near_miss = NearMiss(
            **payload,
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
        if tenant_id is not None:
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
        params: PaginationInput,
        reporter_email: Optional[str] = None,
        status_filter: Optional[str] = None,
        priority: Optional[str] = None,
        contract: Optional[str] = None,
        asset_id: Optional[int] = None,
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
        if asset_id is not None:
            query = query.where(NearMiss.asset_id == asset_id)

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
            ValueError: If contract_id is supplied but not owned by the tenant.
        """
        near_miss = await self.get_near_miss(near_miss_id, tenant_id)
        old_status = near_miss.status
        update_dict = data.model_dump(exclude_unset=True)
        new_status = update_dict.get("status")
        if new_status and new_status != old_status:
            allowed = self.VALID_TRANSITIONS.get(old_status, set())
            if new_status not in allowed:
                raise StateTransitionError(
                    f"Cannot transition from '{old_status}' to '{new_status}'",
                    details={"allowed": sorted(allowed)},
                )

        resolved_contract_display: Optional[str] = None
        if "contract_id" in update_dict:
            if update_dict["contract_id"] is not None:
                _, resolved_contract_display = await resolve_near_miss_contract(
                    self.db,
                    tenant_id=tenant_id,
                    contract_id=update_dict["contract_id"],
                    contract=None,
                )
            else:
                resolved_contract_display = ""

        update_data = apply_updates(near_miss, data, set_updated_at=False)
        if resolved_contract_display is not None:
            near_miss.contract = resolved_contract_display

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
            payload={
                "updates": update_data,
                "old_status": old_status,
                "new_status": near_miss.status,
            },
            user_id=user_id,
            request_id=request_id,
        )

        await self.db.commit()
        await self.db.refresh(near_miss)
        if tenant_id is not None:
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
        if tenant_id is not None:
            await invalidate_tenant_cache(tenant_id, "near_miss")
        track_metric("near_miss.mutation", 1)

    async def list_investigations(
        self,
        near_miss_id: int,
        *,
        tenant_id: int | None,
        params: PaginationInput,
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
