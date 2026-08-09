"""Pure notification helpers for Compliance Schedule (due sweep + owner assignment).

Every function here is pure: no session, no clock of its own, no I/O. ``now`` is
injected exactly as :mod:`src.domain.services.compliance_schedule_policy` requires, so
the sweep computes it once per run and threads it through. Bands come from
``classify_due_band`` rather than being recomputed here -- there is one definition of
"due soon" in this module and it lives in the policy.

Language: the only words used for a passed date are *overdue* and *due*. The
lapsed-certificate vocabulary this module avoids would imply the requirement itself
ceased to apply, which is the opposite of what a missed inspection date means -- the
obligation is still owed, and more urgently. The same rule is enforced on the policy
module, and a test here greps this file for it.

Due-reminder notification type is :attr:`NotificationType.COMPLIANCE_ALERT` for every
band. The alternative -- mapping overdue to ``ACTION_OVERDUE`` as document campaigns
do -- would label these as Actions, and the Actions module means something specific in
this product (a CAPA someone owns). Urgency is carried by ``priority`` and by
``extra_data['band']`` instead, and no PostgreSQL enum migration is needed either way.

Owner allocation uses :attr:`NotificationType.ASSIGNMENT` /
:attr:`NotificationType.REASSIGNMENT` (existing enum values; no migration).

Once an occurrence is completed, ``next_due_date`` rolls forward and the dedupe key
(requirement + occurrence date + band) no longer matches prior reminder rows, so the
sweep naturally stops nagging that cycle — there is no separate cancel job.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from src.domain.models.notification import NotificationPriority, NotificationType
from src.domain.services.compliance_schedule_policy import DueBand

#: ``Notification.entity_type`` for every row this module builds. The partial unique
#: index that makes de-duplication a guarantee rather than a hope is predicated on
#: exactly this string, so changing it silently disables that index.
ENTITY_TYPE = "compliance_requirement"

NOTIFICATION_CATEGORY = "compliance_schedule_due"
ASSIGNMENT_NOTIFICATION_CATEGORY = "compliance_schedule_assignment"

DEFAULT_ADMIN_ROLE = "admin"

#: Bands an admin is copied on when the requirement is not statutory. Owners get every
#: band; admins get only what they can realistically act on, which is the tail. This is
#: the anti-flood mechanism, and it needs no digest machinery to work.
ADMIN_BANDS_ROUTINE: tuple[DueBand, ...] = ("overdue",)

#: Statutory obligations additionally escalate a week out, because a statutory date
#: slipping is the case where a week's notice still buys someone a remedy.
ADMIN_BANDS_STATUTORY: tuple[DueBand, ...] = ("overdue", "due_7")

_BAND_PRIORITY: Dict[DueBand, NotificationPriority] = {
    "overdue": NotificationPriority.HIGH,
    "due_7": NotificationPriority.HIGH,
    "due_30": NotificationPriority.MEDIUM,
    "due_60": NotificationPriority.LOW,
}

_BAND_TITLE: Dict[DueBand, str] = {
    "overdue": "Compliance requirement overdue",
    "due_7": "Compliance requirement due within 7 days",
    "due_30": "Compliance requirement due within 30 days",
    "due_60": "Compliance requirement due within 60 days",
}

_BAND_WINDOW_DAYS: Dict[DueBand, str] = {
    "due_7": "7",
    "due_30": "30",
    "due_60": "60",
}


def action_url_for_requirement(requirement_id: int) -> str:
    """In-app deep link to the requirement's detail page."""
    return f"/compliance-schedule/{requirement_id}"


def dedupe_key(requirement_id: int, due_date: date, band: DueBand) -> str:
    """Stable key identifying one reminder: this requirement, this occurrence, this band.

    The occurrence date is part of the key, which is the difference between this and
    ``safety_asset_expiry_tasks.dedupe_key``. A compliance requirement is *recurring*:
    the same requirement legitimately re-enters ``due_7`` on its next occurrence, and an
    occurrence-blind key would suppress that reminder for the lifetime of the row.

    Two consequences worth knowing rather than discovering:

    * ``overdue`` is a single band, so one occurrence yields one overdue notification per
      recipient, ever -- not a daily nag. Escalating repeats would need a further band and
      is a product decision, not an implementation detail.
    * Editing ``next_due_date`` changes the key, so a recipient may receive a fresh
      notification for the same requirement. That is intended: the schedule changed.
    """
    return f"{ENTITY_TYPE}:{requirement_id}:{due_date.isoformat()}:{band}"


def priority_for_band(band: DueBand) -> NotificationPriority:
    """Urgency for a band. Never CRITICAL -- that is reserved for SOS and RIDDOR."""
    return _BAND_PRIORITY[band]


def admin_bands_for(*, statutory: bool) -> tuple[DueBand, ...]:
    """Which bands an admin is copied on."""
    return ADMIN_BANDS_STATUTORY if statutory else ADMIN_BANDS_ROUTINE


def title_for_band(band: DueBand, *, title: str) -> str:
    return f"{_BAND_TITLE[band]}: {title}"


def message_for_band(
    band: DueBand,
    *,
    reference_number: str,
    title: str,
    due_date: date,
    statutory: bool,
) -> str:
    """Human-readable body. States the obligation, the date, and what to do next."""
    due_label = due_date.isoformat()
    statutory_note = " This is a statutory obligation." if statutory else ""

    if band == "overdue":
        return (
            f"{reference_number} ({title}) was due on {due_label} and has not been "
            f"recorded as complete.{statutory_note} Open the requirement to record the "
            "completion or reschedule it."
        )

    window = _BAND_WINDOW_DAYS[band]
    return (
        f"{reference_number} ({title}) is due within {window} days (due {due_label})."
        f"{statutory_note} Open the requirement to plan or record the completion."
    )


def recipient_user_ids(
    *,
    owner_user_id: Optional[int],
    admin_user_ids: Iterable[int],
    band: DueBand,
    statutory: bool,
) -> List[int]:
    """Who to notify for this band, owner first, de-duplicated and order-stable.

    When a requirement has no owner the admins are used as the fallback for *every*
    band rather than the escalation subset. An unowned statutory obligation going
    overdue with nobody told is precisely the failure this module exists to prevent, so
    silence is not an acceptable default -- unlike ``safety_asset_expiry_tasks``, which
    skips a row whose recipient list is empty.
    """
    admins = [uid for uid in admin_user_ids if uid is not None]

    if owner_user_id is None:
        candidates: Sequence[Optional[int]] = admins
    else:
        escalate = band in admin_bands_for(statutory=statutory)
        candidates = [owner_user_id] + (admins if escalate else [])

    seen: Set[int] = set()
    ordered: List[int] = []
    for uid in candidates:
        if uid is None or uid in seen:
            continue
        seen.add(uid)
        ordered.append(uid)
    return ordered


def notification_exists_for_key(
    existing_rows: Iterable[Any],
    *,
    user_id: int,
    requirement_id: int,
    due_date: date,
    band: DueBand,
) -> bool:
    """Whether this exact reminder already exists among ``existing_rows``.

    A fast path only. It closes the sequential duplicate case -- chiefly a task
    redelivered after a partial run, since ``task_acks_late`` is on -- but two concurrent
    workers can both pass it before either commits. The partial unique index on
    ``notifications`` is what actually makes duplicates impossible; this check exists so
    the common case does no wasted insert and so the sweep can report a skip count.
    """
    key = dedupe_key(requirement_id, due_date, band)
    for row in existing_rows:
        if getattr(row, "user_id", None) != user_id:
            continue
        if getattr(row, "entity_type", None) != ENTITY_TYPE:
            continue
        extra = getattr(row, "extra_data", None) or {}
        if extra.get("dedupe_key") == key:
            return True
    return False


def build_notification_kwargs(
    *,
    user_id: int,
    tenant_id: int,
    requirement_id: int,
    reference_number: str,
    title: str,
    band: DueBand,
    due_date: date,
    statutory: bool,
    evaluated_at: datetime,
) -> Dict[str, Any]:
    """Kwargs for one ``Notification`` row. Pure -- builds nothing, writes nothing.

    ``tenant_id`` is required rather than optional. It is nominally metadata on
    ``Notification``, but it is the only field on the row that records which tenant's
    obligation this concerns, and a sweep that walks every tenant must not be able to
    omit it by accident.
    """
    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "type": NotificationType.COMPLIANCE_ALERT,
        "priority": priority_for_band(band),
        "title": title_for_band(band, title=title),
        "message": message_for_band(
            band,
            reference_number=reference_number,
            title=title,
            due_date=due_date,
            statutory=statutory,
        ),
        "entity_type": ENTITY_TYPE,
        "entity_id": str(requirement_id),
        "action_url": action_url_for_requirement(requirement_id),
        "extra_data": {
            "notification_category": NOTIFICATION_CATEGORY,
            "band": band,
            "dedupe_key": dedupe_key(requirement_id, due_date, band),
            "due_date": due_date.isoformat(),
            "statutory": statutory,
            "evaluated_at": evaluated_at.isoformat(),
        },
        "delivered_channels": ["in_app"],
    }


def should_notify_owner_change(
    *,
    previous_owner_id: Optional[int],
    new_owner_id: Optional[int],
) -> bool:
    """True when ownership lands on a person who did not already own it.

    Unassign (``new_owner_id is None``) and no-op same-owner writes do not notify.
    """
    if new_owner_id is None:
        return False
    return previous_owner_id != new_owner_id


def build_assignment_notification_kwargs(
    *,
    user_id: int,
    tenant_id: int,
    requirement_id: int,
    reference_number: str,
    title: str,
    assigned_by_user_id: int,
    previous_owner_id: Optional[int] = None,
    next_due_date: Optional[date] = None,
) -> Dict[str, Any]:
    """Kwargs for an owner-allocation ``Notification`` row. Pure — no I/O.

    Uses ASSIGNMENT when there was no prior owner, REASSIGNMENT when ownership moved
    from one person to another. The new owner is the only recipient (caller passes
    ``user_id``); the actor is still notified when they assign themselves — matching
    incident / action assignment, which do not skip self.
    """
    is_reassignment = previous_owner_id is not None and previous_owner_id != user_id
    notification_type = NotificationType.REASSIGNMENT if is_reassignment else NotificationType.ASSIGNMENT
    due_clause = f" Next due {next_due_date.isoformat()}." if next_due_date is not None else ""
    if is_reassignment:
        message = (
            f"You are now the owner of {reference_number} ({title})."
            f"{due_clause} Open the requirement to plan or record completion."
        )
        notif_title = f"Compliance requirement reassigned to you: {title}"
    else:
        message = (
            f"You have been allocated as owner of {reference_number} ({title})."
            f"{due_clause} Open the requirement to plan or record completion."
        )
        notif_title = f"Compliance requirement assigned to you: {title}"

    return {
        "user_id": user_id,
        "tenant_id": tenant_id,
        "type": notification_type,
        "priority": NotificationPriority.HIGH,
        "title": notif_title,
        "message": message,
        "entity_type": ENTITY_TYPE,
        "entity_id": str(requirement_id),
        "action_url": action_url_for_requirement(requirement_id),
        "sender_id": assigned_by_user_id,
        "extra_data": {
            "notification_category": ASSIGNMENT_NOTIFICATION_CATEGORY,
            "previous_owner_id": previous_owner_id,
            "reference_number": reference_number,
            "next_due_date": next_due_date.isoformat() if next_due_date is not None else None,
        },
        "delivered_channels": ["in_app"],
    }


def due_reminder_email_subject(*, title: str, band: DueBand) -> str:
    """Subject line for a due-reminder email (matches in-app title prefix)."""
    return title_for_band(band, title=title)


def due_reminder_email_body(
    *,
    reference_number: str,
    title: str,
    band: DueBand,
    due_date: date,
    statutory: bool,
    action_url: str,
) -> str:
    """Plain-text email body for a due reminder; deep link appended."""
    body = message_for_band(
        band,
        reference_number=reference_number,
        title=title,
        due_date=due_date,
        statutory=statutory,
    )
    return f"{body}\n\nOpen: {action_url}"
