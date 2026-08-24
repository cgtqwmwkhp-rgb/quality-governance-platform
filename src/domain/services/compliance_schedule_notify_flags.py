"""Feature flags that gate Compliance Schedule assignment and due-reminder notify.

Normal polarity: ``enabled=True`` means send. Missing rows default to **on** so a
fresh environment does not silently drop reminders until an admin seeds the flags;
``ensure_compliance_schedule_notify_flags`` still inserts the rows so Feature Flags
admin / Notification Settings can turn them off without a migration.

These are additive notify levers on top of the module opener
(``compliance_schedule_enabled``) and the kill switch. Closing the module still
closes everything.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.feature_flag import FeatureFlag
from src.domain.services.feature_flag_service import FeatureFlagService

logger = logging.getLogger(__name__)

ASSIGNMENT_NOTIFY_FLAG = "compliance_schedule_assignment_notify"
DUE_REMINDER_NOTIFY_FLAG = "compliance_schedule_due_reminder_notify"
EMAIL_ENABLED_FLAG = "compliance_schedule_email_enabled"

NOTIFY_FLAG_KEYS: tuple[str, ...] = (
    ASSIGNMENT_NOTIFY_FLAG,
    DUE_REMINDER_NOTIFY_FLAG,
    EMAIL_ENABLED_FLAG,
)

_FLAG_SPECS: Sequence[tuple[str, str, str]] = (
    (
        ASSIGNMENT_NOTIFY_FLAG,
        "Compliance Schedule — owner assignment notify",
        "In-app (+ email when email flag/prefs allow) when a schedule owner is allocated.",
    ),
    (
        DUE_REMINDER_NOTIFY_FLAG,
        "Compliance Schedule — due reminder notify",
        "Daily sweep due/overdue reminders (in-app always when this is on; email when email flag/prefs allow).",
    ),
    (
        EMAIL_ENABLED_FLAG,
        "Compliance Schedule — email channel",
        "Master email channel for Compliance Schedule assignment and due-reminder mail. "
        "Requires SMTP and the recipient's NotificationPreference.email_enabled.",
    ),
)


async def ensure_compliance_schedule_notify_flags(db: AsyncSession) -> list[FeatureFlag]:
    """Insert the three notify flags if missing (enabled, 100% rollout). Idempotent."""
    service = FeatureFlagService(db)
    ensured: list[FeatureFlag] = []
    for key, name, description in _FLAG_SPECS:
        existing = await service._get_flag(key)
        if existing is not None:
            ensured.append(existing)
            continue
        flag = await service.create_flag(
            key=key,
            name=name,
            description=description,
            enabled=True,
            rollout_percentage=100,
            created_by="system:compliance_schedule_notify_flags",
        )
        ensured.append(flag)
        logger.info("Seeded Compliance Schedule notify flag %s (enabled=True)", key)
    return ensured


async def is_cs_notify_flag_enabled(
    db: AsyncSession,
    key: str,
    *,
    tenant_id: Optional[int] = None,
) -> bool:
    """Whether a CS notify flag allows sending.

    Missing row → True (default-on). Present row → same rules as
    ``FeatureFlagService.is_enabled`` (global enabled, then tenant_overrides,
    then rollout percentage), including ``tenant_overrides`` when ``tenant_id``
    is provided.
    """
    import hashlib

    result = await db.execute(select(FeatureFlag).where(FeatureFlag.key == key))
    flag = result.scalar_one_or_none()
    if flag is None:
        return True
    if not flag.enabled:
        return False
    if tenant_id is not None and flag.tenant_overrides:
        override = flag.tenant_overrides.get(str(tenant_id))
        if override is not None:
            return bool(override)
    if flag.rollout_percentage >= 100:
        return True
    if flag.rollout_percentage <= 0:
        return False
    bucket = (
        int(
            hashlib.sha256(f"{key}:{tenant_id if tenant_id is not None else 'default'}".encode()).hexdigest(),
            16,
        )
        % 100
    )
    return bool(bucket < flag.rollout_percentage)


async def assignment_notify_enabled(db: AsyncSession, *, tenant_id: Optional[int]) -> bool:
    return await is_cs_notify_flag_enabled(db, ASSIGNMENT_NOTIFY_FLAG, tenant_id=tenant_id)


async def due_reminder_notify_enabled(db: AsyncSession, *, tenant_id: Optional[int]) -> bool:
    return await is_cs_notify_flag_enabled(db, DUE_REMINDER_NOTIFY_FLAG, tenant_id=tenant_id)


async def email_channel_enabled(db: AsyncSession, *, tenant_id: Optional[int]) -> bool:
    return await is_cs_notify_flag_enabled(db, EMAIL_ENABLED_FLAG, tenant_id=tenant_id)
