"""Assignment notify + audit helpers for the unified action fabric."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Optional

from src.domain.services.audit_service import record_audit_event
from src.domain.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


async def notify_action_assignment(
    db: Any,
    *,
    action_id: int,
    assigned_to_user_id: int,
    assigned_by_user_id: int,
    title: str,
    priority: str = "medium",
    due_date: Optional[datetime] = None,
) -> None:
    """Create in-app assignment notification for a unified action assignee."""
    try:
        service = NotificationService(db)
        await service.create_assignment(
            entity_type="action",
            entity_id=str(action_id),
            assigned_to_user_id=assigned_to_user_id,
            assigned_by_user_id=assigned_by_user_id,
            due_date=due_date,
            priority=priority if priority in ("low", "medium", "high", "critical") else "medium",
            notes=f"You have been assigned action: {title}",
        )
    except Exception as exc:
        # Assignment is already committed; notification delivery must not undo it.
        # Keep the failure queryable in structured logs for operational follow-up.
        logger.warning(
            "action_assignment_notification_failed",
            extra={
                "action_id": action_id,
                "assigned_to_user_id": assigned_to_user_id,
                "assigned_by_user_id": assigned_by_user_id,
                "exception_type": type(exc).__name__,
            },
            exc_info=True,
        )


async def record_action_assigned_audit(
    db: Any,
    *,
    action_key: str,
    assigned_to_user_id: int,
    previous_owner_id: Optional[int],
    assigned_by_user_id: int,
    request_id: str,
    source_type: str,
    reference_number: Optional[str] = None,
) -> None:
    """Record an explicit assignment audit event when an action owner changes."""
    await record_audit_event(
        db=db,
        event_type="unified_action.assigned",
        entity_type="unified_action",
        entity_id=action_key,
        action="assign",
        description=f"Assigned unified action {reference_number or action_key}",
        payload={
            "source_type": source_type,
            "assigned_to_user_id": assigned_to_user_id,
            "previous_owner_id": previous_owner_id,
        },
        user_id=assigned_by_user_id,
        request_id=request_id,
    )
