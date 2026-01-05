"""Service for recording audit events."""

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from starlette_context import context

from src.domain.models.audit_log import AuditEvent


async def record_audit_event(
    db: AsyncSession,
    event_type: str,
    entity_type: str,
    entity_id: str,
    action: str,
    description: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
    user_id: Optional[int] = None,
    actor_user_id: Optional[int] = None,
    request_id: Optional[str] = None,
    # Legacy parameters for backward compatibility (deprecated)
    resource_type: Optional[str] = None,
    resource_id: Optional[str] = None,
) -> AuditEvent:
    """
    Record a system-wide audit event with canonical schema.

    Args:
        db: Database session
        event_type: Type of event (e.g., "policy.created")
        entity_type: Type of entity (e.g., "policy")
        entity_id: ID of the entity
        action: Action performed (e.g., "create", "update", "delete")
        description: Optional description
        payload: Optional JSON payload with event details
        user_id: Legacy user ID (deprecated, use actor_user_id)
        actor_user_id: ID of the user who performed the action
        request_id: Request ID for traceability (auto-populated from context if not provided)
        resource_type: Legacy resource type (deprecated, use entity_type)
        resource_id: Legacy resource ID (deprecated, use entity_id)

    Returns:
        The created AuditEvent
    """
    # Auto-populate request_id from context if not provided
    if request_id is None:
        request_id = context.get("request_id", None)

    # Use actor_user_id if provided, otherwise fall back to user_id
    final_actor_user_id = actor_user_id if actor_user_id is not None else user_id

    event = AuditEvent(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        action=action,
        description=description,
        payload=payload,
        actor_user_id=final_actor_user_id,
        request_id=request_id,
        # Populate legacy fields for backward compatibility
        resource_type=resource_type or entity_type,
        resource_id=resource_id or str(entity_id),
        user_id=final_actor_user_id,
    )
    db.add(event)
    # We don't commit here to allow the event to be part of the caller's transaction
    return event
