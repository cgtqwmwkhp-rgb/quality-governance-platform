"""Service for recording audit events.

This module provides a lightweight audit event recording mechanism.
Events are logged for observability but not persisted to the database
until proper schema migration is implemented.

For full immutable audit trail with blockchain-style hashing,
see AuditLogEntry in src/domain/models/audit_log.py.
"""

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit_log import AuditEvent
from src.infrastructure.monitoring.azure_monitor import track_business_event


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

    Note: Currently logs the event for observability but does not persist
    to the database. Full persistence requires schema migration.

    Args:
        db: Database session (currently unused, kept for API compatibility)
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
        The created AuditEvent (in-memory only, not persisted)
    """
    # Use actor_user_id if provided, otherwise fall back to user_id
    final_actor_user_id = actor_user_id if actor_user_id is not None else user_id

    # Create the event (logs automatically in AuditEvent.__init__)
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

    track_business_event("audit_completed", {"event_type": event_type, "entity_type": entity_type})

    return event
