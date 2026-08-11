"""Feature flags that gate Incident case-owner assignment notify.

Inverted polarity vs Compliance Schedule: ``enabled=True`` means send, but a
**missing** row defaults to **off**. Fresh environments must not start emailing /
notifying incident owners until an admin explicitly turns the toggle on.
``ensure_incident_notify_flags`` still inserts the rows (``enabled=False``) so
Feature Flags admin / Notification Settings can turn them on without a migration.
"""

from __future__ import annotations

import logging
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.feature_flag import FeatureFlag
from src.domain.services.feature_flag_service import FeatureFlagService

logger = logging.getLogger(__name__)

ASSIGNMENT_NOTIFY_FLAG = "incident_owner_assignment_notify"

NOTIFY_FLAG_KEYS: tuple[str, ...] = (ASSIGNMENT_NOTIFY_FLAG,)

#: Keys whose absent row means *off* (inverse of CS notify flags).
DEFAULT_OFF_FLAG_KEYS: frozenset[str] = frozenset(NOTIFY_FLAG_KEYS)

_FLAG_SPECS: Sequence[tuple[str, str, str]] = (
    (
        ASSIGNMENT_NOTIFY_FLAG,
        "Incident — case owner assignment notify",
        "In-app notify when an incident is allocated to a case owner (first assign or reassignment). "
        "Default off until an admin enables it.",
    ),
)


async def ensure_incident_notify_flags(db: AsyncSession) -> list[FeatureFlag]:
    """Insert incident notify flags if missing (disabled, 100% rollout). Idempotent."""
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
            enabled=False,
            rollout_percentage=100,
            created_by="system:incident_notify_flags",
        )
        ensured.append(flag)
        logger.info("Seeded Incident notify flag %s (enabled=False)", key)
    return ensured


async def is_incident_notify_flag_enabled(
    db: AsyncSession,
    key: str,
    *,
    tenant_id: Optional[int] = None,
) -> bool:
    """Whether an Incident notify flag allows sending.

    Missing row → False (default-off). Present row → same rules as
    ``FeatureFlagService.is_enabled`` (global enabled, then tenant_overrides,
    then rollout percentage), including ``tenant_overrides`` when ``tenant_id``
    is provided.
    """
    import hashlib

    result = await db.execute(select(FeatureFlag).where(FeatureFlag.key == key))
    flag = result.scalar_one_or_none()
    if flag is None:
        return False
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
    return await is_incident_notify_flag_enabled(db, ASSIGNMENT_NOTIFY_FLAG, tenant_id=tenant_id)
