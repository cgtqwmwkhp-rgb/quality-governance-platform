"""Service for recording audit events."""

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit_log import AuditEvent


async def record_audit_event(
    db: AsyncSession,
    event_type: str,
    resource_type: str,
    resource_id: str,
    action: str,
    description: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
    user_id: Optional[int] = None,
) -> AuditEvent:
    """Record a system-wide audit event."""
    event = AuditEvent(
        event_type=event_type,
        resource_type=resource_type,
        resource_id=str(resource_id),
        action=action,
        description=description,
        payload=payload,
        user_id=user_id,
    )
    db.add(event)
    # We don't commit here to allow the event to be part of the caller's transaction
    return event
