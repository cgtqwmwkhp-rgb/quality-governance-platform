"""In-app notifications when operational standards assess proposes links."""

from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.notification import Notification, NotificationPriority, NotificationType

logger = logging.getLogger(__name__)

_CASE_STANDARDS_PATHS: dict[str, str] = {
    "incident": "/incidents/{id}?tab=standards",
    "complaint": "/complaints/{id}?tab=standards",
    "near_miss": "/near-misses/{id}?tab=standards",
    "rta": "/rtas/{id}?tab=standards",
}


def exceptions_deep_link(entity_type: str) -> str:
    """Deep link into Knowledge Exceptions filtered by entity type."""
    return f"/knowledge-exceptions?entity_type={entity_type}"


def case_standards_deep_link(entity_type: str, entity_id: str) -> str:
    """Deep link to the case Standards tab when a detail route exists."""
    template = _CASE_STANDARDS_PATHS.get(entity_type)
    if template:
        return template.format(id=entity_id)
    return exceptions_deep_link(entity_type)


async def resolve_case_notify_user_ids(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    tenant_id: int,
) -> list[int]:
    """Return owner/assignee + creator user IDs for an operational case entity."""
    try:
        eid = int(entity_id)
    except (TypeError, ValueError):
        return []

    owner_ids: list[int] = []

    if entity_type == "incident":
        from src.domain.models.incident import Incident

        row = (
            await db.execute(select(Incident).where(Incident.id == eid, Incident.tenant_id == tenant_id))
        ).scalar_one_or_none()
        if row:
            if getattr(row, "owner_id", None):
                owner_ids.append(int(row.owner_id))
            if getattr(row, "created_by_id", None):
                owner_ids.append(int(row.created_by_id))
    elif entity_type == "complaint":
        from src.domain.models.complaint import Complaint

        row = (
            await db.execute(select(Complaint).where(Complaint.id == eid, Complaint.tenant_id == tenant_id))
        ).scalar_one_or_none()
        if row:
            if getattr(row, "owner_id", None):
                owner_ids.append(int(row.owner_id))
            if getattr(row, "created_by_id", None):
                owner_ids.append(int(row.created_by_id))
    elif entity_type == "near_miss":
        from src.domain.models.near_miss import NearMiss

        row = (
            await db.execute(select(NearMiss).where(NearMiss.id == eid, NearMiss.tenant_id == tenant_id))
        ).scalar_one_or_none()
        if row:
            if getattr(row, "assigned_to_id", None):
                owner_ids.append(int(row.assigned_to_id))
            if getattr(row, "created_by_id", None):
                owner_ids.append(int(row.created_by_id))
    elif entity_type == "rta":
        from src.domain.models.rta import RTA

        row = (await db.execute(select(RTA).where(RTA.id == eid, RTA.tenant_id == tenant_id))).scalar_one_or_none()
        if row:
            if getattr(row, "owner_id", None):
                owner_ids.append(int(row.owner_id))
            if getattr(row, "created_by_id", None):
                owner_ids.append(int(row.created_by_id))
    elif entity_type == "audit_finding":
        from src.domain.models.audit import AuditFinding

        row = (
            await db.execute(
                select(AuditFinding).where(AuditFinding.id == eid, AuditFinding.tenant_id == tenant_id)
            )
        ).scalar_one_or_none()
        if row and getattr(row, "created_by_id", None):
            owner_ids.append(int(row.created_by_id))

    # Dedupe while preserving order
    seen: set[int] = set()
    unique: list[int] = []
    for uid in owner_ids:
        if uid not in seen:
            seen.add(uid)
            unique.append(uid)
    return unique


async def notify_proposed_standards_links(
    db: AsyncSession,
    *,
    entity_type: str,
    entity_id: str,
    tenant_id: int,
    links_created: int,
    sender_id: Optional[int] = None,
) -> list[Notification]:
    """
    Create in-app notifications for case owner/creator when proposed links appear.

    Does not commit — caller owns the transaction. Failures are logged and swallowed
    so assess never fails because of notification delivery.
    """
    if links_created <= 0:
        return []

    try:
        recipient_ids = await resolve_case_notify_user_ids(
            db,
            entity_type=entity_type,
            entity_id=entity_id,
            tenant_id=tenant_id,
        )
    except Exception:
        logger.warning(
            "Failed resolving notify targets for %s:%s",
            entity_type,
            entity_id,
            exc_info=True,
        )
        return []

    # Prefer Exceptions inbox for confirm/reject; Standards tab for case context.
    exceptions_url = exceptions_deep_link(entity_type)
    standards_url = case_standards_deep_link(entity_type, entity_id)
    title = "Standards assessment proposed"
    message = (
        f"{links_created} proposed standards link(s) need review for {entity_type} {entity_id}. "
        f"Open Exceptions to confirm/reject, or review on the case Standards tab."
    )

    created: list[Notification] = []
    for user_id in recipient_ids:
        if sender_id is not None and user_id == sender_id:
            continue
        try:
            notification = Notification(
                tenant_id=tenant_id,
                user_id=user_id,
                type=NotificationType.COMPLIANCE_ALERT,
                priority=NotificationPriority.MEDIUM,
                title=title,
                message=message,
                entity_type=entity_type,
                entity_id=str(entity_id),
                action_url=exceptions_url,
                sender_id=sender_id,
                extra_data={
                    "links_created": links_created,
                    "exceptions_url": exceptions_url,
                    "standards_url": standards_url,
                },
                delivered_channels=["in_app"],
            )
            db.add(notification)
            created.append(notification)
        except Exception:
            logger.warning(
                "Failed creating standards-proposed notification for user=%s entity=%s:%s",
                user_id,
                entity_type,
                entity_id,
                exc_info=True,
            )
    return created
