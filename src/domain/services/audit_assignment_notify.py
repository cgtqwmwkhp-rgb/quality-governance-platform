"""Best-effort AUDIT_SCHEDULED notify + honesty rules for the device queue.

Assignment is already committed (or flushed) before this runs. A failed notify
must not undo the assignee write — same posture as unified-action assignment.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import ValidationError
from src.domain.models.notification import NotificationChannel, NotificationPriority, NotificationType
from src.domain.models.tenant import TenantUser
from src.domain.models.user import User
from src.domain.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

PORTAL_AUDITS_ACTION_URL = "/portal/audits"
FALLBACK_REFERENCE = "???"
FALLBACK_STATUS = "unknown"
DEVICE_QUEUE_EXCLUDED_STATUSES = frozenset({"completed", "cancelled"})


def portal_audit_action_url() -> str:
    """In-app / email CTA must land on the portal, not the staff execute shell."""
    return PORTAL_AUDITS_ACTION_URL


def should_notify_assignee_change(*, previous_id: Optional[int], new_id: Optional[int]) -> bool:
    """Notify only when a person is newly responsible."""
    return new_id is not None and new_id != previous_id


def _status_value(run: Any) -> str:
    raw = getattr(run, "status", None)
    if raw is None:
        return ""
    if hasattr(raw, "value"):
        return str(raw.value).strip().lower()
    return str(raw).strip().lower()


def is_device_queue_run(run: Any) -> bool:
    """Whether a run may appear on the portal Audits tile / list.

    Serializer fallbacks (reference ``???``, status ``unknown``) are excluded so
    a broken row cannot become a fake work item. Completed and cancelled runs
    are not open work.
    """
    ref = (getattr(run, "reference_number", None) or "").strip()
    if not ref or ref == FALLBACK_REFERENCE:
        return False
    status_val = _status_value(run)
    if not status_val or status_val == FALLBACK_STATUS:
        return False
    if status_val in DEVICE_QUEUE_EXCLUDED_STATUSES:
        return False
    return True


async def require_assignee_in_tenant(
    db: AsyncSession,
    *,
    assignee_id: Optional[int],
    tenant_id: int,
) -> None:
    """Refuse a cross-tenant or unknown assignee. ``None`` is unassigned."""
    if assignee_id is None:
        return
    result = await db.execute(select(User).where(User.id == assignee_id))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise ValidationError("Assignee not found in this organisation")
    if user.tenant_id == tenant_id:
        return
    membership = (
        await db.execute(
            select(TenantUser.id).where(
                TenantUser.user_id == assignee_id,
                TenantUser.tenant_id == tenant_id,
                TenantUser.is_active.is_(True),
            )
        )
    ).scalar_one_or_none()
    if membership is None:
        raise ValidationError("Assignee is not in this organisation")


async def notify_audit_scheduled(
    db: AsyncSession,
    *,
    run_id: int,
    reference_number: str,
    title: Optional[str],
    assigned_to_id: int,
    assigned_by_id: int,
    tenant_id: Optional[int],
) -> None:
    """Create in-app + email AUDIT_SCHEDULED. Never raises into the caller."""
    try:
        label = (title or "").strip() or reference_number
        message = f"You have been assigned audit {reference_number}: {label}. " "Open it from Employee Portal → Audits."
        service = NotificationService(db)
        await service.create_notification(
            user_id=assigned_to_id,
            notification_type=NotificationType.AUDIT_SCHEDULED,
            title=f"Audit assigned: {reference_number}",
            message=message,
            priority=NotificationPriority.MEDIUM,
            entity_type="audit_run",
            entity_id=str(run_id),
            action_url=portal_audit_action_url(),
            sender_id=assigned_by_id,
            metadata={"run_id": run_id, "reference_number": reference_number},
            channels=[NotificationChannel.IN_APP, NotificationChannel.EMAIL],
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.warning(
            "audit_scheduled_notification_failed",
            extra={
                "run_id": run_id,
                "assigned_to_id": assigned_to_id,
                "assigned_by_id": assigned_by_id,
                "exception_type": type(exc).__name__,
            },
            exc_info=True,
        )
