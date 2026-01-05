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
    actor_user_id: Optional[int] = None,
    before_value: Optional[dict[str, Any]] = None,
    after_value: Optional[dict[str, Any]] = None,
) -> AuditEvent:
    """Record a system-wide audit event."""
    request_id = context.get("request_id", "N/A")
    event = AuditEvent(
        event_type=event_type,
        entity_type=entity_type,
        entity_id=str(entity_id),
        actor_user_id=actor_user_id,
        request_id=request_id,
        before_value=before_value,
        after_value=after_value,
    )
    db.add(event)
    # We don't commit here to allow the event to be part of the caller's transaction
    return event
