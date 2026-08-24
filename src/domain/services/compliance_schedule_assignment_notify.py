"""Best-effort owner-allocation notify for Compliance Schedule.

Never raises into the caller: a failed notify must not undo a committed owner write
(same posture as incident case-owner assign and unified action assignment).
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.domain.models.notification import Notification, NotificationChannel, NotificationPreference
from src.domain.services.compliance_schedule_notifications import (
    build_assignment_notification_kwargs,
    should_notify_owner_change,
)
from src.domain.services.compliance_schedule_notify_flags import assignment_notify_enabled, email_channel_enabled
from src.domain.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


async def _user_email_pref_enabled(db: AsyncSession, user_id: int) -> bool:
    result = await db.execute(select(NotificationPreference).where(NotificationPreference.user_id == user_id))
    prefs = result.scalar_one_or_none()
    if prefs is None:
        return True
    return bool(prefs.email_enabled)


async def _kill_switch_engaged(db: AsyncSession) -> bool:
    from src.domain.models.feature_flag import FeatureFlag
    from src.domain.services.compliance_schedule_kill_switch import KILL_SWITCH_FLAG_KEY

    result = await db.execute(select(FeatureFlag.enabled).where(FeatureFlag.key == KILL_SWITCH_FLAG_KEY))
    return bool(result.scalar_one_or_none())


async def notify_compliance_schedule_owner_assignment(
    db: AsyncSession,
    *,
    tenant_id: int,
    requirement_id: int,
    reference_number: str,
    title: str,
    new_owner_id: Optional[int],
    previous_owner_id: Optional[int],
    assigned_by_user_id: int,
    next_due_date: Optional[date] = None,
) -> Optional[Notification]:
    """Notify the new owner after a successful owner write. Best-effort; never raises."""
    try:
        if not should_notify_owner_change(previous_owner_id=previous_owner_id, new_owner_id=new_owner_id):
            return None
        assert new_owner_id is not None

        if not settings.compliance_schedule_enabled:
            return None
        if await _kill_switch_engaged(db):
            return None
        if not await assignment_notify_enabled(db, tenant_id=tenant_id):
            return None

        kwargs = build_assignment_notification_kwargs(
            user_id=new_owner_id,
            tenant_id=tenant_id,
            requirement_id=requirement_id,
            reference_number=reference_number,
            title=title,
            assigned_by_user_id=assigned_by_user_id,
            previous_owner_id=previous_owner_id,
            next_due_date=next_due_date,
        )

        channels = [NotificationChannel.IN_APP]
        if await email_channel_enabled(db, tenant_id=tenant_id) and await _user_email_pref_enabled(db, new_owner_id):
            channels.append(NotificationChannel.EMAIL)

        service = NotificationService(db)
        notification = await service.create_notification(
            user_id=kwargs["user_id"],
            notification_type=kwargs["type"],
            title=kwargs["title"],
            message=kwargs["message"],
            priority=kwargs["priority"],
            entity_type=kwargs["entity_type"],
            entity_id=kwargs["entity_id"],
            action_url=kwargs["action_url"],
            sender_id=kwargs["sender_id"],
            metadata=kwargs["extra_data"],
            channels=channels,
        )
        # Sweep rows always stamp tenant_id; assignment path must match for ops queries.
        if notification.tenant_id is None:
            notification.tenant_id = tenant_id
            await db.commit()
        return notification
    except Exception as exc:
        logger.warning(
            "compliance_schedule_assignment_notification_failed",
            extra={
                "requirement_id": requirement_id,
                "new_owner_id": new_owner_id,
                "previous_owner_id": previous_owner_id,
                "assigned_by_user_id": assigned_by_user_id,
                "exception_type": type(exc).__name__,
            },
            exc_info=True,
        )
        return None
