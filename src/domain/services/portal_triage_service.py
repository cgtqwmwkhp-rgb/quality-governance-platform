"""Portal intake triage — auto-assign case owner and notify on submit (Journey C)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.domain.models.user import User
from src.domain.services.notification_service import NotificationService

logger = logging.getLogger(__name__)

_TRIAGE_ROLE_NAMES = frozenset({"admin", "manager", "supervisor", "superadmin"})
_UPDATE_PERMISSION_BY_ENTITY = {
    "incident": "incident:update",
    "complaint": "complaint:update",
    "rta": "rta:update",
    "near_miss": "near_miss:update",
}


def _user_can_triage_entity(user: User, entity_type: str) -> bool:
    """Return True when the user may own triage for this portal entity type."""
    if user.is_superuser:
        return True
    permission = _UPDATE_PERMISSION_BY_ENTITY.get(entity_type)
    if permission and user.has_permission(permission):
        return True
    for role in user.roles:
        if role.name.lower() in _TRIAGE_ROLE_NAMES:
            return True
    return False


def pick_triage_owner_from_users(
    users: list[User],
    entity_type: str,
    *,
    submitter: Any | None = None,
    tenant_id: int | None = None,
) -> Optional[int]:
    """Pure selection logic for portal triage owner (unit-testable)."""
    if submitter is not None:
        submitter_id = getattr(submitter, "id", None)
        submitter_tenant = getattr(submitter, "tenant_id", None)
        submitter_active = getattr(submitter, "is_active", True)
        if (
            submitter_id is not None
            and submitter_active
            and (tenant_id is None or submitter_tenant == tenant_id)
            and _user_can_triage_entity(submitter, entity_type)
        ):
            return int(submitter_id)

    for user in users:
        if user.is_active and _user_can_triage_entity(user, entity_type):
            return user.id

    for user in users:
        if user.is_active:
            return user.id

    return None


async def resolve_portal_triage_owner(
    db: AsyncSession,
    tenant_id: int,
    entity_type: str,
    submitter: Any | None = None,
) -> Optional[int]:
    """Resolve the case owner for a new portal intake in the tenant."""
    result = await db.execute(
        select(User)
        .options(selectinload(User.roles))
        .where(User.tenant_id == tenant_id, User.is_active.is_(True))
        .order_by(User.is_superuser.desc(), User.id.asc())
    )
    users = list(result.scalars().all())
    return pick_triage_owner_from_users(users, entity_type, submitter=submitter, tenant_id=tenant_id)


def apply_portal_owner(entity: Any, entity_type: str, owner_id: int) -> None:
    """Set the owner/assignee field on a freshly created portal record."""
    if entity_type == "near_miss":
        entity.assigned_to_id = owner_id
    else:
        entity.owner_id = owner_id


async def assign_and_notify_portal_intake(
    db: AsyncSession,
    *,
    entity: Any,
    entity_type: str,
    reference: str,
    tenant_id: int,
    submitter: Any | None = None,
) -> Optional[int]:
    """Assign case owner on portal submit and notify via NotificationService."""
    owner_id = await resolve_portal_triage_owner(db, tenant_id, entity_type, submitter)
    if owner_id is None:
        logger.warning(
            "Portal intake for %s (%s) has no triage owner in tenant %s",
            entity_type,
            reference,
            tenant_id,
        )
        return None

    apply_portal_owner(entity, entity_type, owner_id)
    await db.commit()
    await db.refresh(entity)

    assigned_by_id = int(getattr(submitter, "id", owner_id) or owner_id)
    try:
        service = NotificationService(db)
        await service.create_assignment(
            entity_type=entity_type,
            entity_id=str(entity.id),
            assigned_to_user_id=owner_id,
            assigned_by_user_id=assigned_by_id,
            notes=f"New portal intake assigned to you — {reference}",
            priority="high",
        )
    except Exception:
        logger.exception(
            "Failed to notify portal triage assignment for %s %s",
            entity_type,
            getattr(entity, "id", "?"),
        )

    return owner_id
