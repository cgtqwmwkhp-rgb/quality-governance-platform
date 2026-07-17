"""CAPA (Corrective and Preventive Action) domain service.

Extracts business logic from CAPA routes into a testable service class.
Raises domain exceptions instead of HTTPException.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional, cast

from pydantic import BaseModel
from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.pagination import PaginatedResponse, PaginationInput, paginate
from src.core.update import apply_updates
from src.domain.exceptions import StateTransitionError
from src.domain.models.audit import AuditFinding
from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.incident import Incident
from src.domain.models.investigation import InvestigationRun
from src.domain.models.near_miss import NearMiss
from src.domain.models.risk_register import EnterpriseRisk
from src.domain.models.rta import RoadTrafficCollision
from src.domain.models.user import User
from src.domain.services.audit_service import record_audit_event
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.cache.redis_cache import invalidate_tenant_cache
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)

# Golden-thread CAPA sources that require a resolvable integer source_id (R47).
_GT_SOURCE_MODELS: dict[CAPASource, type[Any]] = {
    CAPASource.AUDIT_FINDING: AuditFinding,
    CAPASource.INVESTIGATION: InvestigationRun,
    CAPASource.NEAR_MISS: NearMiss,
    CAPASource.RTA: RoadTrafficCollision,
    CAPASource.INCIDENT: Incident,
    CAPASource.RISK: EnterpriseRisk,
}


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
        params = PaginationInput(page=page, page_size=page_size)
        return await paginate(self.db, query, params)

    async def validate_capa_source_exists(
        self,
        *,
        source_type: CAPASource | None,
        source_id: int | None,
        tenant_id: int | None,
    ) -> None:
        """Require resolvable source rows for golden-thread CAPA sources (no polymorphic FK)."""
        if source_type is None:
            return
        if source_type not in _GT_SOURCE_MODELS:
            return
        if source_id is None:
            raise ValueError(f"source_id is required when source_type={source_type.value}")

        model = _GT_SOURCE_MODELS[source_type]
        query: Select[Any] = select(model).where(model.id == source_id)
        if tenant_id is not None and hasattr(model, "tenant_id"):
            query = query.where(model.tenant_id == tenant_id)
        result = await self.db.execute(query)
        if result.scalar_one_or_none() is None:
            raise LookupError(f"CAPA source {source_type.value} with ID {source_id} not found")

    async def create_capa_action(
        self,
        *,
        data: BaseModel,
        user_id: int,
        tenant_id: int | None,
    ) -> CAPAAction:
        """Create a new CAPA action with auto-generated reference number."""
        payload = data.model_dump()
        source_type = payload.get("source_type")
        source_id = payload.get("source_id")
        if isinstance(source_type, str):
            try:
                source_type = CAPASource(source_type)
            except ValueError:
                source_type = None
        await self.validate_capa_source_exists(
            source_type=source_type if isinstance(source_type, CAPASource) else None,
            source_id=source_id,
            tenant_id=tenant_id,
        )

        ref = await ReferenceNumberService.generate(self.db, "capa", CAPAAction)
        action = CAPAAction(
            reference_number=ref,
            created_by_id=user_id,
            tenant_id=tenant_id,
            **payload,
        )
        self.db.add(action)
        await self.db.commit()
        await self.db.refresh(action)
        if tenant_id is not None:
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
            tenant_id=tenant_id,
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
        if tenant_id is not None:
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

        allowed = self.VALID_TRANSITIONS.get(current, [])
        if new_status not in allowed:
            raise StateTransitionError(
                f"Cannot transition from '{current.value}' to '{new_status.value}'",
                details={"allowed": [s.value for s in allowed]},
            )

        if new_status == CAPAStatus.CLOSED:
            # Prefer explicit verification_result; allow one-shot close via comment.
            if comment and not (action.verification_result and str(action.verification_result).strip()):
                action.verification_result = comment  # type: ignore[assignment]
            if not (action.verification_result and str(action.verification_result).strip()):
                raise StateTransitionError(
                    "verification_result is required before closing a CAPA",
                    code="MISSING_REQUIRED_FIELD",
                    details={"field": "verification_result"},
                )

        action.status = new_status
        # CAPA timestamp columns are TIMESTAMP WITHOUT TIME ZONE — store UTC-naive.
        now_utc_naive = datetime.now(timezone.utc).replace(tzinfo=None)
        if new_status == CAPAStatus.VERIFICATION:
            action.completed_at = now_utc_naive  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE
        elif new_status == CAPAStatus.CLOSED:
            action.verified_at = now_utc_naive  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE
            action.verified_by_id = user_id  # type: ignore[assignment]  # TYPE-IGNORE: MYPY-OVERRIDE
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
            tenant_id=tenant_id,
        )

        bridge_result: dict[str, Any] | None = None
        if new_status in (CAPAStatus.VERIFICATION, CAPAStatus.CLOSED):
            from src.domain.services.audit_service import AuditService

            bridge_result = await AuditService(self.db).apply_capa_closure_bridge(
                action,
                actor_user_id=user_id,
                tenant_id=tenant_id,
            )

        await self.db.commit()
        await self.db.refresh(action)

        if bridge_result is not None:
            from src.domain.services.audit_service import AuditService

            await AuditService(self.db).notify_capa_closure_bridge(
                bridge_result=bridge_result,
                capa=action,
                actor_user_id=user_id,
            )

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
            tenant_id=tenant_id,
        )

        await self.db.delete(action)
        await self.db.commit()
        if tenant_id is not None:
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

    async def create_capa_for_investigation(
        self,
        investigation_id: int,
        *,
        user_id: int,
        tenant_id: int,
        title: str | None = None,
        description: str | None = None,
        assignee_id: int | None = None,
        assignee_email: str | None = None,
        due_date: str | datetime | None = None,
        priority: str | None = None,
    ) -> CAPAAction:
        """Create a CAPA linked to an investigation (idempotent if already linked)."""
        inv_result = await self.db.execute(
            select(InvestigationRun).where(
                InvestigationRun.id == investigation_id,
                InvestigationRun.tenant_id == tenant_id,
            )
        )
        investigation = inv_result.scalar_one_or_none()
        if investigation is None:
            raise LookupError(f"Investigation with ID {investigation_id} not found")

        # Idempotent only for empty convenience creates (no explicit title).
        # When the user supplies a title, always create a new CAPA so investigators
        # can add multiple corrective actions against one investigation.
        if not (title and title.strip()):
            prior = await self.db.execute(
                select(CAPAAction).where(
                    CAPAAction.tenant_id == tenant_id,
                    CAPAAction.source_type == CAPASource.INVESTIGATION,
                    CAPAAction.source_id == investigation_id,
                )
            )
            existing_capa = prior.scalar_one_or_none()
            if existing_capa is not None:
                return existing_capa

        resolved_assignee = assignee_id
        if resolved_assignee is None and assignee_email:
            user_result = await self.db.execute(select(User).where(User.email == assignee_email))
            user = user_result.scalar_one_or_none()
            if user is None:
                raise LookupError(f"User not found for email: {assignee_email}")
            resolved_assignee = user.id
        if resolved_assignee is None:
            inv_assignee = cast(int | None, investigation.assigned_to_user_id)
            resolved_assignee = inv_assignee if inv_assignee is not None else user_id

        capa_priority = CAPAPriority.MEDIUM
        if priority:
            try:
                capa_priority = CAPAPriority(priority.lower())
            except ValueError as exc:
                raise ValueError(f"Invalid priority: {priority}") from exc

        parsed_due: datetime | None = None
        if due_date is not None:
            if isinstance(due_date, datetime):
                parsed_due = due_date.replace(tzinfo=None) if due_date.tzinfo else due_date
            else:
                raw = due_date.strip()
                if raw:
                    try:
                        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                        parsed_due = parsed.replace(tzinfo=None) if parsed.tzinfo else parsed
                    except ValueError:
                        parsed_due = datetime.strptime(raw[:10], "%Y-%m-%d")

        action_title = (title or f"Action plan: {investigation.title}")[:255]
        action_desc = description if description is not None else investigation.description

        ref = await ReferenceNumberService.generate(self.db, "capa", CAPAAction)
        capa = CAPAAction(
            reference_number=ref,
            title=action_title,
            description=action_desc,
            capa_type=CAPAType.CORRECTIVE,
            status=CAPAStatus.OPEN,
            priority=capa_priority,
            source_type=CAPASource.INVESTIGATION,
            source_id=investigation_id,
            source_reference=f"investigation:{investigation_id}",
            assigned_to_id=resolved_assignee,
            created_by_id=user_id,
            due_date=parsed_due,
            tenant_id=tenant_id,
        )
        self.db.add(capa)
        await self.db.flush()

        await record_audit_event(
            db=self.db,
            event_type="capa.created_from_investigation",
            entity_type="capa",
            entity_id=str(capa.id),
            action="create",
            description=f"CAPA {ref} created from investigation {investigation.reference_number}",
            payload={
                "investigation_id": investigation_id,
                "capa_id": capa.id,
                "reference_number": ref,
            },
            user_id=user_id,
            tenant_id=tenant_id,
        )

        await self.db.commit()
        await self.db.refresh(capa)
        await invalidate_tenant_cache(tenant_id, "capa")
        track_metric("investigations.create_capa")
        return capa
