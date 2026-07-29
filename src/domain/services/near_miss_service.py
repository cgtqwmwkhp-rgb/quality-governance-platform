"""Near-miss management domain service.

Extracts business logic from near-miss routes into a testable service class.
Raises domain exceptions instead of HTTPException.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

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
from src.domain.services.case_closure import (
    CASE_TYPE_NEAR_MISS,
    apply_close_stamps,
    assert_case_can_close,
    clear_close_stamps,
    is_closed_status,
    resolve_case_tenant_id,
)
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


NEAR_MISS_TRANSITIONS: dict[str, set[str]] = {
    "REPORTED": {"UNDER_REVIEW", "CLOSED"},
    "UNDER_REVIEW": {"ACTION_REQUIRED", "IN_PROGRESS", "CLOSED"},
    "ACTION_REQUIRED": {"IN_PROGRESS", "CLOSED"},
    "IN_PROGRESS": {"CLOSED", "ACTION_REQUIRED"},
    # Reopen is a single controlled reverse edge, not a free jump back into the lifecycle.
    "CLOSED": {"UNDER_REVIEW"},
}


def validate_near_miss_transition(current: Any, target: Any) -> None:
    """Validate a status transition for a near miss.

    Raises StateTransitionError if the transition is not allowed.
    Same-status updates are a no-op (PATCH edit forms always re-send status).
    Near misses store status as an uppercase VARCHAR, so an unrecognised label
    has no allowed edges at all and is refused — unlike the enum-backed
    registers, which wave legacy labels through.

    Lifted out of ``NearMissService.update_near_miss`` so the closure gate can
    ask the same question the write path asks, instead of holding a second copy
    of this map.
    """
    current_raw = str(getattr(current, "value", current))
    target_raw = str(getattr(target, "value", target))
    if current_raw == target_raw:
        return
    allowed = NEAR_MISS_TRANSITIONS.get(current_raw, set())
    if target_raw not in allowed:
        raise StateTransitionError(
            f"Cannot transition from '{current_raw}' to '{target_raw}'",
            details={"allowed": sorted(allowed)},
        )


class NearMissService:
    """Handles near-miss CRUD, reference number generation, and status transitions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # Kept as a class attribute for callers that still reach for it.
    VALID_TRANSITIONS: dict[str, set[str]] = NEAR_MISS_TRANSITIONS

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
            entity_name=near_miss.reference_number,
            action="create",
            description=f"Near Miss {near_miss.reference_number} reported",
            payload=data.model_dump(mode="json"),
            user_id=user_id,
            request_id=request_id,
            tenant_id=near_miss.tenant_id,
        )

        await self.db.commit()
        await self.db.refresh(near_miss)
        if tenant_id is not None:
            await invalidate_tenant_cache(tenant_id, "near_miss")
        track_metric("near_miss.mutation", 1)

        return near_miss

    async def get_near_miss(
        self, near_miss_id: int, tenant_id: int | None, *, skip_tenant_check: bool = False
    ) -> NearMiss:
        """Fetch a single near miss by ID.

        Args:
            near_miss_id: Primary key.
            tenant_id: Tenant scope (ignored when skip_tenant_check is True).
            skip_tenant_check: If True, bypasses tenant isolation (superuser).

        Raises:
            LookupError: If the near miss is not found.
        """
        query = select(NearMiss).where(NearMiss.id == near_miss_id)
        if not skip_tenant_check:
            query = query.where(NearMiss.tenant_id == tenant_id)
        result = await self.db.execute(query)
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
        skip_tenant_check: bool = False,
    ) -> NearMiss:
        """Partially update a near miss.

        Handles status transition side-effects (closed_at, assigned_at).

        Raises:
            LookupError: If the near miss is not found.
            ValueError: If contract_id is supplied but not owned by the tenant.
        """
        near_miss = await self.get_near_miss(near_miss_id, tenant_id, skip_tenant_check=skip_tenant_check)
        old_status = near_miss.status
        update_dict = data.model_dump(exclude_unset=True)
        new_status = update_dict.get("status")
        was_closed = is_closed_status(CASE_TYPE_NEAR_MISS, old_status)
        closing = False
        if new_status:
            validate_near_miss_transition(old_status, new_status)
            closing = not was_closed and is_closed_status(CASE_TYPE_NEAR_MISS, new_status)

        if closing:
            # Gate before any mutation so a refused close leaves the session clean.
            await assert_case_can_close(
                self.db,
                case_type=CASE_TYPE_NEAR_MISS,
                case=near_miss,
                tenant_id=resolve_case_tenant_id(near_miss),
                lessons_learnt=(
                    update_dict["lessons_learnt"] if "lessons_learnt" in update_dict else near_miss.lessons_learnt
                ),
            )

        # Guard against the near miss's tenant (not the caller's) so a cross-tenant
        # editor with skip_tenant_check cannot attach their own tenant's contract.
        contract_tenant_id = near_miss.tenant_id if near_miss.tenant_id is not None else tenant_id
        resolved_contract_display: Optional[str] = None
        if "contract_id" in update_dict and update_dict["contract_id"] is not None:
            _, resolved_contract_display = await resolve_near_miss_contract(
                self.db,
                tenant_id=contract_tenant_id,
                contract_id=update_dict["contract_id"],
                contract=None,
            )

        update_data = apply_updates(near_miss, data, set_updated_at=False)
        if resolved_contract_display:
            near_miss.contract = resolved_contract_display

        reopening = was_closed and not is_closed_status(CASE_TYPE_NEAR_MISS, near_miss.status)
        if closing:
            update_data.update(apply_close_stamps(near_miss, user_id=user_id))
        elif reopening:
            update_data.update(clear_close_stamps(near_miss))

        if "assigned_to_id" in update_data and near_miss.assigned_at is None:
            near_miss.assigned_at = datetime.now(timezone.utc)

        near_miss.updated_by_id = user_id

        lifecycle = "closed" if closing else "reopened" if reopening else "updated"
        await record_audit_event(
            db=self.db,
            event_type=f"near_miss.{lifecycle}",
            entity_type="near_miss",
            entity_id=str(near_miss.id),
            entity_name=near_miss.reference_number,
            action="update",
            description=f"Near Miss {near_miss.reference_number} {lifecycle}",
            payload={
                "updates": update_data,
                "old_status": old_status,
                "new_status": near_miss.status,
            },
            user_id=user_id,
            request_id=request_id,
            # The record's own tenant, not the tenant_id argument: callers pass
            # None with skip_tenant_check=True, and the row still has an owner.
            tenant_id=near_miss.tenant_id,
        )

        await self.db.commit()
        await self.db.refresh(near_miss)
        # The row's tenant, not the caller's: a cross-tenant edit has to evict the
        # register the record actually appears in.
        cache_tenant_id = near_miss.tenant_id if near_miss.tenant_id is not None else tenant_id
        if cache_tenant_id is not None:
            await invalidate_tenant_cache(cache_tenant_id, "near_miss")
        track_metric("near_miss.mutation", 1)

        return near_miss

    async def delete_near_miss(
        self,
        near_miss_id: int,
        *,
        user_id: int,
        tenant_id: int | None,
        request_id: str | None = None,
        skip_tenant_check: bool = False,
    ) -> None:
        """Delete a near miss.

        Raises:
            LookupError: If the near miss is not found.
        """
        near_miss = await self.get_near_miss(near_miss_id, tenant_id, skip_tenant_check=skip_tenant_check)

        await record_audit_event(
            db=self.db,
            event_type="near_miss.deleted",
            entity_type="near_miss",
            entity_id=str(near_miss.id),
            entity_name=near_miss.reference_number,
            action="delete",
            description=f"Near Miss {near_miss.reference_number} deleted",
            payload={"reference_number": near_miss.reference_number},
            user_id=user_id,
            request_id=request_id,
            tenant_id=near_miss.tenant_id,
        )

        # Capture the owner before delete/commit can expire ORM attributes. A
        # superuser may be deleting a record owned by a different tenant.
        cache_tenant_id = near_miss.tenant_id if near_miss.tenant_id is not None else tenant_id
        await self.db.delete(near_miss)
        await self.db.commit()
        if cache_tenant_id is not None:
            await invalidate_tenant_cache(cache_tenant_id, "near_miss")
        track_metric("near_miss.mutation", 1)

    async def list_investigations(
        self,
        near_miss_id: int,
        *,
        tenant_id: int | None,
        params: PaginationInput,
        skip_tenant_check: bool = False,
    ):
        """List investigations linked to a near miss.

        Raises:
            LookupError: If the near miss is not found.
        """
        from src.domain.models.investigation import AssignedEntityType, InvestigationRun

        await self.get_near_miss(near_miss_id, tenant_id, skip_tenant_check=skip_tenant_check)

        query = (
            select(InvestigationRun)
            .where(
                InvestigationRun.assigned_entity_type == AssignedEntityType.NEAR_MISS,
                InvestigationRun.assigned_entity_id == near_miss_id,
            )
            .order_by(InvestigationRun.created_at.desc(), InvestigationRun.id.asc())
        )
        return await paginate(self.db, query, params)
