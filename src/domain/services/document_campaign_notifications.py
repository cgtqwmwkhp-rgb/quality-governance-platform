"""Typed in-app notification helpers for document campaigns (O-05).

Uses distinct ``entity_type`` values and existing ``NotificationType`` enum members
to avoid PostgreSQL enum migrations (Option B).
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional, Set

from src.domain.models.notification import NotificationPriority, NotificationType

ENTITY_TYPE_CAMPAIGN = "document_campaign"
ENTITY_TYPE_CAMPAIGN_REMINDER = "document_campaign_reminder"
ENTITY_TYPE_CAMPAIGN_OVERDUE = "document_campaign_overdue"

_MANAGER_FIELD_NAMES = ("manager_id", "supervisor_id", "reports_to")


def user_display_name(user: Any, fallback_user_id: int) -> str:
    """Human-readable assignee label for manager/HSEC overdue messages."""
    if user is None:
        return f"User {fallback_user_id}"
    full_name = getattr(user, "full_name", None)
    if callable(full_name):
        try:
            return str(full_name())
        except Exception:  # noqa: BLE001
            pass
    elif full_name:
        return str(full_name)
    first = getattr(user, "first_name", "") or ""
    last = getattr(user, "last_name", "") or ""
    combined = f"{first} {last}".strip()
    return combined or f"User {fallback_user_id}"


def user_manager_id(user: Any) -> Optional[int]:
    """Return a manager/supervisor user id when the User model exposes one."""
    for attr in _MANAGER_FIELD_NAMES:
        value = getattr(user, attr, None)
        if value is not None:
            try:
                return int(value)
            except (TypeError, ValueError):
                continue
    return None


def sorted_reminder_offsets_hours(offsets: Iterable[int]) -> List[int]:
    """Return reminder offsets sorted descending (furthest-from-due first)."""
    return sorted({int(h) for h in offsets if int(h) > 0}, reverse=True)


def reminder_due_now(
    *,
    now,
    due_at,
    reminders_sent: int,
    reminder_offsets_hours: Iterable[int],
) -> bool:
    """True when the next scheduled reminder should fire."""
    offsets = sorted_reminder_offsets_hours(reminder_offsets_hours)
    if reminders_sent >= len(offsets):
        return False
    from datetime import timedelta

    trigger_at = due_at - timedelta(hours=offsets[reminders_sent])
    return now >= trigger_at


def hsec_owner_user_ids(*, created_by_id: Optional[int], launched_by_id: Optional[int]) -> List[int]:
    """De-duplicated HSEC owner ids (campaign creator / launcher)."""
    seen: Set[int] = set()
    ordered: List[int] = []
    for uid in (created_by_id, launched_by_id):
        if uid is None or uid in seen:
            continue
        seen.add(uid)
        ordered.append(uid)
    return ordered


def overdue_escalation_recipients(
    *,
    assignee_user_id: int,
    assignee_user: Any,
    created_by_id: Optional[int],
    launched_by_id: Optional[int],
) -> List[int]:
    """Assignee + optional manager + HSEC owners, de-duplicated (assignee first)."""
    seen: Set[int] = set()
    ordered: List[int] = []

    def _add(uid: Optional[int]) -> None:
        if uid is None or uid in seen:
            return
        seen.add(uid)
        ordered.append(uid)

    _add(assignee_user_id)
    _add(user_manager_id(assignee_user))
    for owner_id in hsec_owner_user_ids(created_by_id=created_by_id, launched_by_id=launched_by_id):
        _add(owner_id)
    return ordered


def build_assignment_notification_kwargs(
    *,
    tenant_id: int,
    user_id: int,
    campaign_id: int,
    document_id: int,
    doc_title: str,
    require_quiz: bool,
    sender_id: Optional[int],
) -> Dict[str, Any]:
    message = (
        f"You have been assigned to read{' and complete a quiz for' if require_quiz else ''} "
        f"'{doc_title}'."
    )
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "type": NotificationType.ASSIGNMENT,
        "priority": NotificationPriority.MEDIUM,
        "title": "Document campaign assigned",
        "message": message,
        "entity_type": ENTITY_TYPE_CAMPAIGN,
        "entity_id": str(campaign_id),
        "action_url": f"/documents/{document_id}",
        "sender_id": sender_id,
    }


def build_reminder_notification_kwargs(
    *,
    tenant_id: int,
    user_id: int,
    campaign_id: int,
    document_id: int,
    doc_title: str,
    due_at,
) -> Dict[str, Any]:
    due_label = due_at.date().isoformat() if hasattr(due_at, "date") else str(due_at)
    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "type": NotificationType.ACTION_DUE_SOON,
        "priority": NotificationPriority.MEDIUM,
        "title": "Document campaign reminder",
        "message": f"Reminder: complete your assignment for '{doc_title}' by {due_label}.",
        "entity_type": ENTITY_TYPE_CAMPAIGN_REMINDER,
        "entity_id": str(campaign_id),
        "action_url": f"/documents/{document_id}",
        "extra_data": {"assignment_due_at": due_label},
    }


def build_overdue_notification_kwargs(
    *,
    tenant_id: int,
    user_id: int,
    campaign_id: int,
    document_id: int,
    doc_title: str,
    assignee_user_id: int,
    assignee_display_name: str,
    recipient_role: str,
) -> Dict[str, Any]:
    if recipient_role == "assignee":
        title = "Document campaign overdue"
        message = f"Your assignment for '{doc_title}' is now overdue. Please complete it as soon as possible."
    elif recipient_role == "manager":
        title = "Team member campaign overdue"
        message = (
            f"{assignee_display_name}'s assignment for '{doc_title}' is overdue. "
            "Please follow up with them."
        )
    else:
        title = "Campaign assignment overdue"
        message = (
            f"An assignment for '{doc_title}' is overdue "
            f"(assignee: {assignee_display_name}). Review campaign compliance."
        )

    return {
        "tenant_id": tenant_id,
        "user_id": user_id,
        "type": NotificationType.ACTION_OVERDUE,
        "priority": NotificationPriority.HIGH,
        "title": title,
        "message": message,
        "entity_type": ENTITY_TYPE_CAMPAIGN_OVERDUE,
        "entity_id": str(campaign_id),
        "action_url": f"/documents/{document_id}",
        "extra_data": {
            "assignee_user_id": assignee_user_id,
            "recipient_role": recipient_role,
        },
    }


def overdue_recipient_role(*, recipient_user_id: int, assignee_user_id: int, assignee_user: Any) -> str:
    if recipient_user_id == assignee_user_id:
        return "assignee"
    manager_id = user_manager_id(assignee_user)
    if manager_id is not None and recipient_user_id == manager_id:
        return "manager"
    return "hsec_owner"
