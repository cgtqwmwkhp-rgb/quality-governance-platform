"""Unified Actions domain service.

Extracts business logic from actions routes into a testable service class.
Handles CRUD for actions spanning incidents, RTAs, complaints, and investigations.
Raises domain exceptions instead of HTTPException.
"""

import logging
from datetime import datetime
from typing import Any, Optional, Union

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.models.complaint import Complaint, ComplaintAction
from src.domain.models.incident import ActionStatus, Incident, IncidentAction
from src.domain.models.investigation import InvestigationAction, InvestigationActionStatus, InvestigationRun
from src.domain.models.rta import RoadTrafficCollision, RTAAction
from src.domain.models.user import User
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)

VALID_SOURCE_TYPES = {"incident", "rta", "complaint", "investigation"}
VALID_PRIORITIES = {"low", "medium", "high", "critical"}


def action_to_dict(
    action: Union[IncidentAction, RTAAction, ComplaintAction, InvestigationAction],
    source_type: str,
    source_id: int,
    owner_email: Optional[str] = None,
) -> dict[str, Any]:
    """Convert an action model to a serializable dict."""
    action_status = getattr(action, "status", None)
    return {
        "id": action.id,
        "reference_number": getattr(action, "reference_number", None),
        "title": action.title,
        "description": action.description,
        "action_type": getattr(action, "action_type", None) or "corrective",
        "priority": getattr(action, "priority", None) or "medium",
        "status": action_status.value if hasattr(action_status, "value") else str(action_status),
        "due_date": action.due_date.isoformat() if getattr(action, "due_date", None) else None,
        "completed_at": action.completed_at.isoformat() if getattr(action, "completed_at", None) else None,
        "completion_notes": getattr(action, "completion_notes", None),
        "source_type": source_type,
        "source_id": source_id,
        "owner_id": getattr(action, "owner_id", None),
        "owner_email": owner_email,
        "assigned_to_email": owner_email,
        "created_at": action.created_at.isoformat() if getattr(action, "created_at", None) else "",
    }


class ActionService:
    """Handles unified CRUD for actions across all entity types."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_actions(
        self,
        *,
        tenant_id: int | None,
        page: int = 1,
        page_size: int = 20,
        status_filter: Optional[str] = None,
        source_type: Optional[str] = None,
        source_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """List all actions across entity types with in-memory pagination."""
        actions_list: list[dict[str, Any]] = []

        if not source_type or source_type == "incident":
            actions_list.extend(await self._list_incident_actions(tenant_id, status_filter, source_type, source_id))
        if not source_type or source_type == "rta":
            actions_list.extend(await self._list_rta_actions(tenant_id, status_filter, source_type, source_id))
        if not source_type or source_type == "complaint":
            actions_list.extend(await self._list_complaint_actions(tenant_id, status_filter, source_type, source_id))
        if not source_type or source_type == "investigation":
            actions_list.extend(
                await self._list_investigation_actions(tenant_id, status_filter, source_type, source_id)
            )

        actions_list.sort(key=lambda x: x["created_at"], reverse=True)

        total = len(actions_list)
        start = (page - 1) * page_size
        paginated = actions_list[start : start + page_size]

        return {
            "items": paginated,
            "total": total,
            "page": page,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if total > 0 else 0,
        }

    async def create_action(
        self,
        *,
        source_type: str,
        source_id: int,
        title: str,
        description: str,
        action_type: str = "corrective",
        priority: str = "medium",
        due_date_str: Optional[str] = None,
        assigned_to_email: Optional[str] = None,
        user_id: int,
        tenant_id: int | None,
    ) -> dict[str, Any]:
        """Create a new action for any entity type.

        Raises:
            ValueError: For invalid source_type or data.
            LookupError: If the source entity is not found.
        """
        src_type = source_type.lower()
        if src_type not in VALID_SOURCE_TYPES:
            raise ValueError(f"Invalid source_type: {src_type}")

        await self._validate_source_entity(src_type, source_id, tenant_id)

        owner_id = await self._resolve_owner(assigned_to_email)
        ref_number = await self._generate_ref_number(src_type)
        parsed_due_date = self._parse_due_date(due_date_str)

        action = self._build_action_model(
            src_type=src_type,
            source_id=source_id,
            title=title,
            description=description,
            action_type=action_type,
            priority=priority,
            due_date=parsed_due_date,
            owner_id=owner_id,
            ref_number=ref_number,
        )

        try:
            self.db.add(action)
            await self.db.commit()
            await self.db.refresh(action)
            track_metric("actions.created", 1)
        except IntegrityError as e:
            await self.db.rollback()
            error_msg = str(e.orig) if hasattr(e, "orig") else str(e)
            if "foreign key" in error_msg.lower():
                raise LookupError("Referenced entity not found")
            elif "unique" in error_msg.lower() or "duplicate" in error_msg.lower():
                raise ValueError("Duplicate action")
            raise
        except SQLAlchemyError:
            await self.db.rollback()
            raise

        return action_to_dict(action, src_type, source_id, assigned_to_email)

    async def get_action(
        self,
        action_id: int,
        source_type: str,
        tenant_id: int | None,
    ) -> dict[str, Any]:
        """Get a specific action by ID and source type.

        Raises:
            ValueError: If source_type is invalid.
            LookupError: If the action is not found.
        """
        src_type = source_type.lower()
        if src_type not in VALID_SOURCE_TYPES:
            raise ValueError(f"Invalid source_type: {src_type}")

        if src_type == "incident":
            action = await self._get_model_or_raise(IncidentAction, action_id)
            await self._validate_source_entity("incident", action.incident_id, tenant_id)
            return action_to_dict(action, "incident", action.incident_id)
        elif src_type == "rta":
            action = await self._get_model_or_raise(RTAAction, action_id, tenant_id=tenant_id)
            return action_to_dict(action, "rta", action.rta_id)
        elif src_type == "complaint":
            action = await self._get_model_or_raise(ComplaintAction, action_id)
            await self._validate_source_entity("complaint", action.complaint_id, tenant_id)
            return action_to_dict(action, "complaint", action.complaint_id)
        else:  # investigation
            action = await self._get_model_or_raise(InvestigationAction, action_id)
            await self._validate_source_entity("investigation", action.investigation_id, tenant_id)
            return action_to_dict(action, "investigation", action.investigation_id)

    async def update_action(  # noqa: C901
        self,
        action_id: int,
        source_type: str,
        *,
        tenant_id: int | None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        action_type: Optional[str] = None,
        priority: Optional[str] = None,
        status_value: Optional[str] = None,
        due_date_str: Optional[str] = None,
        assigned_to_email: Optional[str] = None,
        completion_notes: Optional[str] = None,
    ) -> dict[str, Any]:
        """Update an existing action.

        Raises:
            ValueError: If source_type, status, or priority is invalid.
            LookupError: If the action is not found.
        """
        src_type = source_type.lower()
        if src_type not in VALID_SOURCE_TYPES:
            raise ValueError(f"Invalid source_type: {src_type}")

        incident_statuses = {s.value for s in ActionStatus}
        investigation_statuses = {s.value for s in InvestigationActionStatus}
        valid_statuses = incident_statuses | investigation_statuses
        if status_value and status_value.lower() not in valid_statuses:
            raise ValueError(f"Invalid status: {status_value}")
        if priority and priority.lower() not in VALID_PRIORITIES:
            raise ValueError(f"Invalid priority: {priority}")

        action, source_id = await self._resolve_action_for_update(action_id, src_type, tenant_id)

        if title is not None:
            action.title = title
        if description is not None:
            action.description = description
        if action_type is not None:
            action.action_type = action_type
        if priority is not None:
            action.priority = priority.lower()
        if status_value is not None:
            sv = status_value.lower()
            if src_type == "investigation":
                action.status = InvestigationActionStatus(sv)
            else:
                action.status = ActionStatus(sv)
            if sv == "completed" and not action.completed_at:
                action.completed_at = datetime.utcnow()
            elif sv != "completed":
                action.completed_at = None

        if due_date_str is not None:
            action.due_date = self._parse_due_date(due_date_str)

        if assigned_to_email is not None:
            result = await self.db.execute(select(User).where(User.email == assigned_to_email))
            user = result.scalar_one_or_none()
            if user:
                action.owner_id = user.id

        if completion_notes is not None:
            action.completion_notes = completion_notes

        await self.db.commit()
        await self.db.refresh(action)

        return action_to_dict(action, src_type, source_id)

    # ---- Private helpers ----

    async def _validate_source_entity(self, src_type: str, source_id: int, tenant_id: int | None) -> None:
        """Validate the source entity exists. Raises LookupError if not."""
        model_map = {
            "incident": Incident,
            "rta": RoadTrafficCollision,
            "complaint": Complaint,
            "investigation": InvestigationRun,
        }
        model = model_map[src_type]
        stmt = select(model).where(model.id == source_id)
        if tenant_id is not None and hasattr(model, "tenant_id"):
            stmt = stmt.where(model.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        if result.scalar_one_or_none() is None:
            raise LookupError(f"{src_type} with ID {source_id} not found")

    async def _resolve_owner(self, email: Optional[str]) -> Optional[int]:
        if not email:
            return None
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        return user.id if user else None

    async def _generate_ref_number(self, src_type: str) -> str:
        prefix_map = {
            "incident": ("INA", IncidentAction),
            "rta": ("RTAACT", RTAAction),
            "complaint": ("CMA", ComplaintAction),
            "investigation": ("INVACT", InvestigationAction),
        }
        prefix, model = prefix_map[src_type]
        year = datetime.now().year
        count_result = await self.db.execute(select(func.count()).select_from(model))
        count = count_result.scalar() or 0
        return f"{prefix}-{year}-{count + 1:04d}"

    @staticmethod
    def _parse_due_date(due_date_str: Optional[str]) -> Optional[datetime]:
        if not due_date_str:
            return None
        try:
            return datetime.fromisoformat(due_date_str.replace("Z", "+00:00"))
        except ValueError:
            for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"]:
                try:
                    return datetime.strptime(due_date_str, fmt)
                except ValueError:
                    continue
        return None

    @staticmethod
    def _build_action_model(
        *,
        src_type: str,
        source_id: int,
        title: str,
        description: str,
        action_type: str,
        priority: str,
        due_date: Optional[datetime],
        owner_id: Optional[int],
        ref_number: str,
    ) -> Union[IncidentAction, RTAAction, ComplaintAction, InvestigationAction]:
        common = {
            "title": title,
            "description": description,
            "action_type": action_type,
            "priority": priority,
            "due_date": due_date,
            "owner_id": owner_id,
            "reference_number": ref_number,
        }
        if src_type == "incident":
            return IncidentAction(incident_id=source_id, status=ActionStatus.OPEN, **common)
        elif src_type == "rta":
            return RTAAction(rta_id=source_id, status=ActionStatus.OPEN, **common)
        elif src_type == "complaint":
            return ComplaintAction(complaint_id=source_id, status=ActionStatus.OPEN, **common)
        else:
            return InvestigationAction(
                investigation_id=source_id,
                status=InvestigationActionStatus.OPEN,
                **common,
            )

    async def _resolve_action_for_update(self, action_id: int, src_type: str, tenant_id: int | None) -> tuple[Any, int]:
        """Fetch the action model and its source_id for update."""
        if src_type == "incident":
            action = await self._get_model_or_raise(IncidentAction, action_id)
            await self._validate_source_entity("incident", action.incident_id, tenant_id)
            return action, action.incident_id
        elif src_type == "rta":
            action = await self._get_model_or_raise(RTAAction, action_id, tenant_id=tenant_id)
            return action, action.rta_id
        elif src_type == "complaint":
            action = await self._get_model_or_raise(ComplaintAction, action_id)
            await self._validate_source_entity("complaint", action.complaint_id, tenant_id)
            return action, action.complaint_id
        else:
            action = await self._get_model_or_raise(InvestigationAction, action_id)
            await self._validate_source_entity("investigation", action.investigation_id, tenant_id)
            return action, action.investigation_id

    async def _get_model_or_raise(self, model: type, entity_id: int, tenant_id: int | None = None) -> Any:
        stmt = select(model).where(model.id == entity_id)
        if tenant_id is not None and hasattr(model, "tenant_id"):
            stmt = stmt.where(model.tenant_id == tenant_id)
        result = await self.db.execute(stmt)
        entity = result.scalar_one_or_none()
        if entity is None:
            raise LookupError(f"{model.__name__} with ID {entity_id} not found")
        return entity

    async def _list_incident_actions(self, tenant_id, status_filter, source_type, source_id) -> list[dict[str, Any]]:
        query = (
            select(IncidentAction)
            .join(Incident)
            .where(Incident.tenant_id == tenant_id)
            .options(selectinload(IncidentAction.incident))
        )
        if status_filter:
            query = query.where(IncidentAction.status == status_filter)
        if source_type == "incident" and source_id:
            query = query.where(IncidentAction.incident_id == source_id)
        result = await self.db.execute(query)
        return [action_to_dict(a, "incident", a.incident_id) for a in result.scalars().all()]

    async def _list_rta_actions(self, tenant_id, status_filter, source_type, source_id) -> list[dict[str, Any]]:
        query = select(RTAAction).where(RTAAction.tenant_id == tenant_id).options(selectinload(RTAAction.rta))
        if status_filter:
            query = query.where(RTAAction.status == status_filter)
        if source_type == "rta" and source_id:
            query = query.where(RTAAction.rta_id == source_id)
        result = await self.db.execute(query)
        return [action_to_dict(a, "rta", a.rta_id) for a in result.scalars().all()]

    async def _list_complaint_actions(self, tenant_id, status_filter, source_type, source_id) -> list[dict[str, Any]]:
        query = (
            select(ComplaintAction)
            .join(Complaint)
            .where(Complaint.tenant_id == tenant_id)
            .options(selectinload(ComplaintAction.complaint))
        )
        if status_filter:
            query = query.where(ComplaintAction.status == status_filter)
        if source_type == "complaint" and source_id:
            query = query.where(ComplaintAction.complaint_id == source_id)
        result = await self.db.execute(query)
        return [action_to_dict(a, "complaint", a.complaint_id) for a in result.scalars().all()]

    async def _list_investigation_actions(
        self, tenant_id, status_filter, source_type, source_id
    ) -> list[dict[str, Any]]:
        query = (
            select(InvestigationAction)
            .join(InvestigationRun)
            .where(InvestigationRun.tenant_id == tenant_id)
            .options(selectinload(InvestigationAction.investigation))
        )
        if status_filter:
            query = query.where(InvestigationAction.status == status_filter)
        if source_type == "investigation" and source_id:
            query = query.where(InvestigationAction.investigation_id == source_id)
        result = await self.db.execute(query)
        return [action_to_dict(a, "investigation", a.investigation_id) for a in result.scalars().all()]
