"""Notification preference resolution — FR-NOTIF-ADMIN-03.

Pure, database-free rules shared by the canonical dispatcher
(:mod:`src.domain.services.notification_service`) and by **both** preference
write surfaces (``PUT /api/v1/notifications/preferences`` and
``PUT /api/v1/notifications/push/preferences``).

Keeping these rules in one module is deliberate: ``category_preferences`` is a
single JSON column written by two APIs with two different value shapes, and the
#1707 honesty sweep found that the two surfaces disagreed about update
semantics. One merge function and one read function keep them consistent.

Two value shapes are supported for a category entry:

``{"email": true, "push": false, "in_app": true}``
    Written by the user-facing Notifications preferences tab. Each key is an
    explicit per-channel opinion. Channels absent from the map (``sms``) carry
    no opinion.

``true`` / ``false``
    Written by the push preferences API, whose flags are push-surface event
    toggles. A bare ``false`` therefore suppresses **push only** — that route
    governs no other channel, so widening it to email/SMS would enforce an
    intent the user never expressed.

Absent keys always mean "no opinion", never "off". A user who has never saved
preferences must keep receiving exactly what they received before this rule
existed.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, time, timezone
from typing import Any, Iterable, Mapping, Optional
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from src.domain.models.notification import NotificationChannel, NotificationPriority, NotificationType

logger = logging.getLogger(__name__)


# ============================================================================
# Category vocabulary
# ============================================================================

# Categories offered by the user-facing preferences tab (frontend CATEGORY_IDS).
CATEGORY_HIGH_PRIORITY_ALERTS = "high_priority_alerts"
CATEGORY_ACTION_REMINDERS = "action_reminders"
CATEGORY_AUDIT_NOTIFICATIONS = "audit_notifications"
CATEGORY_DOCUMENT_UPDATES = "document_updates"
CATEGORY_ASSIGNMENT_NOTIFICATIONS = "assignment_notifications"

# Additional categories only the push preferences API writes today.
CATEGORY_INCIDENT_ALERTS = "incident_alerts"
CATEGORY_COMPLIANCE_UPDATES = "compliance_updates"
CATEGORY_MENTIONS = "mentions"

# Which category owns each notification type.
#
# CATEGORY_DOCUMENT_UPDATES is intentionally absent: no ``NotificationType``
# models a document event, and document campaign notifications are inserted
# directly rather than dispatched through NotificationService, so the toggle has
# nothing to gate. Enforcing it would require routing those inserts through this
# service first — tracked as follow-up, not silently faked here.
CATEGORY_BY_TYPE: dict[NotificationType, str] = {
    NotificationType.MENTION: CATEGORY_MENTIONS,
    NotificationType.ASSIGNMENT: CATEGORY_ASSIGNMENT_NOTIFICATIONS,
    NotificationType.REASSIGNMENT: CATEGORY_ASSIGNMENT_NOTIFICATIONS,
    NotificationType.ACTION_ASSIGNED: CATEGORY_ASSIGNMENT_NOTIFICATIONS,
    NotificationType.ACTION_DUE_SOON: CATEGORY_ACTION_REMINDERS,
    NotificationType.ACTION_OVERDUE: CATEGORY_ACTION_REMINDERS,
    NotificationType.INCIDENT_NEW: CATEGORY_INCIDENT_ALERTS,
    NotificationType.INCIDENT_UPDATE: CATEGORY_INCIDENT_ALERTS,
    NotificationType.INCIDENT_ESCALATED: CATEGORY_INCIDENT_ALERTS,
    NotificationType.SOS_ALERT: CATEGORY_INCIDENT_ALERTS,
    NotificationType.RIDDOR_INCIDENT: CATEGORY_INCIDENT_ALERTS,
    NotificationType.AUDIT_SCHEDULED: CATEGORY_AUDIT_NOTIFICATIONS,
    NotificationType.AUDIT_STARTED: CATEGORY_AUDIT_NOTIFICATIONS,
    NotificationType.AUDIT_COMPLETED: CATEGORY_AUDIT_NOTIFICATIONS,
    NotificationType.AUDIT_FINDING: CATEGORY_AUDIT_NOTIFICATIONS,
    NotificationType.COMPLIANCE_ALERT: CATEGORY_COMPLIANCE_UPDATES,
    NotificationType.CERTIFICATE_EXPIRING: CATEGORY_COMPLIANCE_UPDATES,
    NotificationType.CERTIFICATE_EXPIRED: CATEGORY_COMPLIANCE_UPDATES,
}

# Channel keys understood inside a nested category entry. ``inApp`` is tolerated
# because older frontend payloads sent camelCase.
_CHANNEL_KEYS: dict[NotificationChannel, tuple[str, ...]] = {
    NotificationChannel.IN_APP: ("in_app", "inApp"),
    NotificationChannel.EMAIL: ("email",),
    NotificationChannel.PUSH: ("push",),
    NotificationChannel.SMS: ("sms",),
}

# Channels a bare boolean category flag can speak for (see module docstring).
_FLAG_CHANNELS = frozenset({NotificationChannel.PUSH})

# Device-interruptive channels held back during quiet hours. In-app is passive
# and email is pull-based; suppressing email would drop the only durable
# off-platform record, because no digest queue exists to defer it to.
QUIET_HOURS_CHANNELS = frozenset({NotificationChannel.PUSH, NotificationChannel.SMS})

DEFAULT_QUIET_HOURS_TIMEZONE = "Europe/London"


# ============================================================================
# Snapshot
# ============================================================================


@dataclass(frozen=True)
class PreferenceSnapshot:
    """Plain read-only view of the preference fields delivery depends on.

    Built with ``getattr`` defaults so a partially-populated row (or a test
    double) degrades to "no opinion" instead of raising mid-dispatch.
    """

    category_preferences: Mapping[str, Any] = field(default_factory=dict)
    quiet_hours_enabled: bool = False
    quiet_hours_start: Optional[str] = None
    quiet_hours_end: Optional[str] = None

    @classmethod
    def from_row(cls, row: Any) -> "PreferenceSnapshot":
        """Snapshot a ``NotificationPreference`` row; ``None`` yields defaults."""
        if row is None:
            return cls()
        raw_categories = getattr(row, "category_preferences", None)
        return cls(
            category_preferences=raw_categories if isinstance(raw_categories, Mapping) else {},
            quiet_hours_enabled=bool(getattr(row, "quiet_hours_enabled", False)),
            quiet_hours_start=getattr(row, "quiet_hours_start", None),
            quiet_hours_end=getattr(row, "quiet_hours_end", None),
        )


@dataclass(frozen=True)
class ChannelDecision:
    """Channels that survived preference enforcement, plus why the rest did not."""

    allowed: list[NotificationChannel]
    suppressed: dict[str, str]

    @property
    def has_suppressions(self) -> bool:
        return bool(self.suppressed)


# ============================================================================
# Category enforcement
# ============================================================================


def categories_for(
    notification_type: NotificationType,
    priority: NotificationPriority,
) -> tuple[str, ...]:
    """Categories whose toggles govern this notification.

    A high-priority notification is governed both by its own subject category
    and by ``high_priority_alerts``, so either toggle can hold it back.
    """
    categories: list[str] = []
    owner = CATEGORY_BY_TYPE.get(notification_type)
    if owner:
        categories.append(owner)
    if priority == NotificationPriority.HIGH:
        categories.append(CATEGORY_HIGH_PRIORITY_ALERTS)
    return tuple(categories)


def _channel_opinion(entry: Any, channel: NotificationChannel) -> Optional[bool]:
    """Read a stored category entry's opinion of one channel.

    Returns ``None`` when the entry expresses no opinion — an unknown shape, a
    channel it does not model, or a non-boolean value.
    """
    if isinstance(entry, bool):
        return entry if channel in _FLAG_CHANNELS else None
    if isinstance(entry, Mapping):
        for key in _CHANNEL_KEYS[channel]:
            if key in entry:
                value = entry[key]
                if isinstance(value, bool):
                    return value
        return None
    return None


def is_channel_muted(
    snapshot: PreferenceSnapshot,
    notification_type: NotificationType,
    priority: NotificationPriority,
    channel: NotificationChannel,
) -> Optional[str]:
    """Return the category that mutes ``channel``, or ``None`` if none does."""
    for category in categories_for(notification_type, priority):
        entry = snapshot.category_preferences.get(category)
        if entry is None:
            continue
        if _channel_opinion(entry, channel) is False:
            return category
    return None


# ============================================================================
# Quiet hours
# ============================================================================


def parse_hhmm(value: Any) -> Optional[time]:
    """Parse a stored ``HH:MM`` bound; ``None`` when unusable."""
    if not isinstance(value, str):
        return None
    parts = value.strip().split(":")
    if len(parts) != 2:
        return None
    try:
        hour, minute = int(parts[0]), int(parts[1])
    except ValueError:
        return None
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        return None
    return time(hour=hour, minute=minute)


def in_quiet_window(moment: time, start: time, end: time) -> bool:
    """Is ``moment`` inside ``[start, end)``, allowing a window across midnight?

    Equal bounds describe no window at all rather than a whole day, so a
    mis-saved ``22:00``/``22:00`` cannot mute a user around the clock.
    """
    if start == end:
        return False
    if start < end:
        return start <= moment < end
    return moment >= start or moment < end


def _now_utc() -> datetime:
    """Current UTC time as a single seam, so quiet-hours tests can freeze it."""
    return datetime.now(timezone.utc)


def resolve_timezone(name: Optional[str]) -> ZoneInfo:
    """Resolve a quiet-hours timezone name, falling back to UTC if unknown."""
    if not name:
        return ZoneInfo("UTC")
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("Unknown quiet-hours timezone %r; evaluating quiet hours in UTC", name)
        return ZoneInfo("UTC")


def is_quiet_hours(
    snapshot: PreferenceSnapshot,
    *,
    now: Optional[datetime] = None,
    tz_name: Optional[str] = DEFAULT_QUIET_HOURS_TIMEZONE,
) -> bool:
    """Is the user inside their configured quiet hours right now?

    Quiet hours are stored as bare ``HH:MM`` strings with no per-user timezone
    column, so bounds are interpreted in ``tz_name`` (a deployment-wide
    setting), not in each user's own timezone.
    """
    if not snapshot.quiet_hours_enabled:
        return False
    start = parse_hhmm(snapshot.quiet_hours_start)
    end = parse_hhmm(snapshot.quiet_hours_end)
    if start is None or end is None:
        logger.debug(
            "Quiet hours enabled but bounds unusable (start=%r end=%r); not gating delivery",
            snapshot.quiet_hours_start,
            snapshot.quiet_hours_end,
        )
        return False
    moment = (now or _now_utc()).astimezone(resolve_timezone(tz_name))
    return in_quiet_window(moment.time(), start, end)


# ============================================================================
# Combined enforcement
# ============================================================================


def filter_channels(
    channels: Iterable[NotificationChannel],
    *,
    snapshot: PreferenceSnapshot,
    notification_type: NotificationType,
    priority: NotificationPriority,
    now: Optional[datetime] = None,
    tz_name: Optional[str] = DEFAULT_QUIET_HOURS_TIMEZONE,
) -> ChannelDecision:
    """Apply category preferences and quiet hours to a set of channels.

    ``CRITICAL`` notifications (SOS, RIDDOR) bypass both gates: a preference
    toggle must never be able to mute a life-safety alert.
    """
    requested = list(dict.fromkeys(channels))
    if priority == NotificationPriority.CRITICAL:
        return ChannelDecision(allowed=requested, suppressed={})

    quiet = is_quiet_hours(snapshot, now=now, tz_name=tz_name)

    allowed: list[NotificationChannel] = []
    suppressed: dict[str, str] = {}
    for channel in requested:
        muting_category = is_channel_muted(snapshot, notification_type, priority, channel)
        if muting_category:
            suppressed[channel.value] = f"category:{muting_category}"
            continue
        if quiet and channel in QUIET_HOURS_CHANNELS:
            suppressed[channel.value] = "quiet_hours"
            continue
        allowed.append(channel)

    return ChannelDecision(allowed=allowed, suppressed=suppressed)


# ============================================================================
# Write semantics
# ============================================================================


def merge_category_preferences(
    existing: Any,
    incoming: Any,
) -> dict[str, Any]:
    """Merge a ``category_preferences`` update into what is already stored.

    Both preference APIs write this one JSON column with different key
    namespaces, so a wholesale replace on either surface silently wipes the
    other's settings. Merging key-wise stops that:

    * keys only present in storage survive an update that omits them;
    * a key present in the update replaces the stored value for that key;
    * when both values are channel maps, channels are merged individually so a
      partial payload cannot drop a channel the user never touched;
    * ``None`` (or any non-mapping) update is treated as "no change", because no
      caller has a legitimate reason to blank every other surface's settings.
    """
    merged: dict[str, Any] = dict(existing) if isinstance(existing, Mapping) else {}
    if not isinstance(incoming, Mapping):
        return merged

    for key, value in incoming.items():
        current = merged.get(key)
        if isinstance(current, Mapping) and isinstance(value, Mapping):
            merged[key] = {**current, **value}
        else:
            merged[key] = value
    return merged
