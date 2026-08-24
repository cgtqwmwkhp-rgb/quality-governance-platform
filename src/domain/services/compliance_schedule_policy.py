"""Pure date/status policy for Compliance Schedule (Wave 0).

All functions take an injected ``now`` (or explicit dates) so UAT repeat-runs
and unit tests stay deterministic. Status vocabulary is intentionally
``current`` / ``due_soon`` / ``overdue`` only.
"""

from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional, Union

ComplianceStatus = Literal["current", "due_soon", "overdue"]
DueBand = Literal["due_60", "due_30", "due_7", "overdue"]
Anchor = Literal["completion", "schedule"]

DateLike = Union[date, datetime]

# Exclusive bands for upcoming due dates (days until due), matching the
# library-review 60/30/7 set — not the safety-asset 90-day window.
_BAND_WINDOWS: tuple[tuple[DueBand, int, int], ...] = (
    ("due_7", 0, 7),
    ("due_30", 8, 30),
    ("due_60", 31, 60),
)


def _as_date(value: DateLike) -> date:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.date()
    return value


def _as_utc_datetime(value: Optional[datetime], *, fallback: datetime) -> datetime:
    if value is None:
        return fallback
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def add_months(base: DateLike, months: int) -> date:
    """Add calendar months with month-end clamp (31 Jan + 1mo → last day of Feb)."""
    start = _as_date(base)
    if months == 0:
        return start

    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(start.day, last_day)
    return date(year, month, day)


def add_days(base: DateLike, days: int) -> date:
    return _as_date(base) + timedelta(days=days)


def derive_status(
    now: DateLike,
    next_due: Optional[DateLike],
    *,
    due_soon_days: int = 30,
) -> Optional[ComplianceStatus]:
    """Map ``next_due`` against ``now`` to current | due_soon | overdue.

    Returns ``None`` when there is no due date. Does not produce a ``missed``
    label — that is a record outcome written by the sweep, not a live status.
    """
    if next_due is None:
        return None

    today = _as_date(now)
    due = _as_date(next_due)
    delta = (due - today).days

    if delta < 0:
        return "overdue"
    if delta <= due_soon_days:
        return "due_soon"
    return "current"


def classify_due_band(
    next_due: Optional[DateLike],
    *,
    now: Optional[DateLike] = None,
) -> Optional[DueBand]:
    """Exclusive reminder bands: overdue | due_7 | due_30 | due_60 | None."""
    if next_due is None:
        return None

    today = _as_date(now or datetime.now(timezone.utc))
    due = _as_date(next_due)
    days_until = (due - today).days

    if days_until < 0:
        return "overdue"

    for band, low, high in _BAND_WINDOWS:
        if low <= days_until <= high:
            return band
    return None


def compute_next_due(
    anchor: Anchor,
    *,
    previous_due: DateLike,
    completed_at: Optional[DateLike] = None,
    frequency_months: Optional[int] = None,
    frequency_days: Optional[int] = None,
) -> date:
    """Roll the schedule forward after an occurrence closes.

    * ``completion`` — interval from the completion (or work) date.
    * ``schedule`` — interval from the previous due date (preserves anniversary).
    """
    if frequency_months is None and frequency_days is None:
        raise ValueError("frequency_months or frequency_days is required")

    if anchor == "completion":
        if completed_at is None:
            raise ValueError("completed_at is required when anchor is 'completion'")
        base = _as_date(completed_at)
    elif anchor == "schedule":
        base = _as_date(previous_due)
    else:
        raise ValueError(f"unknown anchor: {anchor}")

    if frequency_months is not None:
        result = add_months(base, frequency_months)
        if frequency_days:
            result = add_days(result, frequency_days)
        return result
    return add_days(base, int(frequency_days or 0))


__all__ = [
    "add_days",
    "add_months",
    "classify_due_band",
    "compute_next_due",
    "derive_status",
]
