"""Document freshness and audit-lapse classification for the composer (JL-UX-W3).

Every verdict here is *read* from the Library / Document Control system of
record and from audit runs. This module never writes a status, and it never
substitutes a guess for a missing one: where the SSOT has no review date, no
audit cadence or no completed run, the answer is ``unknown`` with a reason,
not an optimistic ``current``.

Freshness and lapse are deliberately separate vocabularies. A document is
``obsolete`` because Library or Document Control says so; an audit outcome is
``lapsed`` because its cadence has elapsed. Neither is inferred from the other.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

#: Freshness states a cell chip / tray chip may render.
DOCUMENT_FRESHNESS_STATES: tuple[str, ...] = (
    "current",
    "due_soon",
    "overdue",
    "obsolete",
    "unknown",
)

#: Library ``DocumentStatus`` values that mean "withdrawn from active use".
#: Attaching one of these to a live job cycle is what W3 blocks.
OBSOLETE_LIBRARY_STATUSES: frozenset[str] = frozenset(
    {"obsolete", "superseded", "retired", "archived"}
)

#: ``ControlledDocument.status`` is a free ``String(50)``, not an enum, so the
#: same withdrawn vocabulary is matched case-insensitively on the doc-control
#: side. ``document_control`` writes exactly ``"obsolete"``.
OBSOLETE_CONTROLLED_STATUSES: frozenset[str] = frozenset(
    {"obsolete", "superseded", "retired", "archived"}
)

#: How far ahead of a review date a document reads as "due soon".
DOCUMENT_DUE_SOON_WINDOW_DAYS = 30

#: Audit lapse states.
AUDIT_LAPSE_STATES: tuple[str, ...] = ("current", "due_soon", "lapsed", "unknown")

#: ``AuditTemplate.frequency`` is constrained by ``AuditTemplateCreate`` to this
#: vocabulary. ``ad_hoc`` is deliberately absent: an ad-hoc audit has no cadence,
#: so it can never be "lapsed" — it resolves to ``unknown``.
AUDIT_FREQUENCY_DAYS: dict[str, int] = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
    "quarterly": 91,
    "annually": 365,
}

#: Upper bound on the "due soon" window for an audit cadence. Scaled down for
#: short cadences below, so a daily audit is never permanently "due soon".
AUDIT_LAPSE_DUE_SOON_WINDOW_DAYS = 30


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def as_aware_utc(value: Optional[datetime]) -> Optional[datetime]:
    """Naive columns (``ControlledDocument.next_review_date``) are read as UTC.

    Mixing naive and aware datetimes raises at comparison time, and the naive
    columns in this codebase are written from ``utcnow``-shaped helpers, so
    reading them as UTC is the honest interpretation rather than a convenience.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def normalise_status(value: Any) -> Optional[str]:
    """Lower-cased status string from an enum member, a raw string, or ``None``."""
    if value is None:
        return None
    raw = getattr(value, "value", value)
    if not isinstance(raw, str):
        raw = str(raw)
    cleaned = raw.strip().lower()
    return cleaned or None


def is_obsolete_library_status(value: Any) -> bool:
    status = normalise_status(value)
    return status is not None and status in OBSOLETE_LIBRARY_STATUSES


def is_obsolete_controlled_status(value: Any) -> bool:
    status = normalise_status(value)
    return status is not None and status in OBSOLETE_CONTROLLED_STATUSES


@dataclass(frozen=True)
class DocumentFreshnessVerdict:
    """Why a document reads as fresh, stale or withdrawn — and from which field."""

    state: str
    reason: str
    review_date: Optional[datetime]
    is_obsolete: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "reason": self.reason,
            "review_date": self.review_date,
            "is_obsolete": self.is_obsolete,
        }


def classify_document_freshness(
    *,
    library_status: Any = None,
    controlled_status: Any = None,
    library_review_date: Optional[datetime] = None,
    controlled_next_review_date: Optional[datetime] = None,
    found: bool = True,
    now: Optional[datetime] = None,
) -> DocumentFreshnessVerdict:
    """Classify one document against the Library / Document Control SSOT.

    Obsolescence wins over every date: a withdrawn document is not "overdue for
    review", it is out of use. Where a controlled document is linked, its
    ``next_review_date`` is preferred over the library ``review_date`` because
    doc control owns the review cycle for controlled documents.
    """
    if not found:
        return DocumentFreshnessVerdict(
            state="unknown",
            reason="document_not_found",
            review_date=None,
            is_obsolete=False,
        )

    if is_obsolete_controlled_status(controlled_status):
        return DocumentFreshnessVerdict(
            state="obsolete",
            reason="obsolete_controlled_status",
            review_date=as_aware_utc(controlled_next_review_date),
            is_obsolete=True,
        )
    if is_obsolete_library_status(library_status):
        return DocumentFreshnessVerdict(
            state="obsolete",
            reason="obsolete_library_status",
            review_date=as_aware_utc(library_review_date),
            is_obsolete=True,
        )

    review_date = as_aware_utc(controlled_next_review_date) or as_aware_utc(library_review_date)
    if review_date is None:
        return DocumentFreshnessVerdict(
            state="unknown",
            reason="no_review_date",
            review_date=None,
            is_obsolete=False,
        )

    moment = as_aware_utc(now) or _utc_now()
    if moment > review_date:
        return DocumentFreshnessVerdict(
            state="overdue",
            reason="review_overdue",
            review_date=review_date,
            is_obsolete=False,
        )
    if moment >= review_date - timedelta(days=DOCUMENT_DUE_SOON_WINDOW_DAYS):
        return DocumentFreshnessVerdict(
            state="due_soon",
            reason="review_due_soon",
            review_date=review_date,
            is_obsolete=False,
        )
    return DocumentFreshnessVerdict(
        state="current",
        reason="review_current",
        review_date=review_date,
        is_obsolete=False,
    )


def audit_frequency_days(frequency: Any) -> Optional[int]:
    """Cadence in days for a known ``AuditTemplate.frequency``, else ``None``.

    ``ad_hoc``, an unrecognised string and ``NULL`` all return ``None`` — the
    caller must then report ``unknown`` rather than inventing a cadence.
    """
    key = normalise_status(frequency)
    if key is None:
        return None
    return AUDIT_FREQUENCY_DAYS.get(key)


def _lapse_due_soon_window(frequency_days: int) -> timedelta:
    """Quarter of the cadence, capped at 30 days.

    A fixed 30-day window would put a daily or weekly audit permanently in
    "due soon", which would make the cue meaningless for exactly the audits
    that repeat most often.
    """
    days = min(AUDIT_LAPSE_DUE_SOON_WINDOW_DAYS, max(0, frequency_days // 4))
    return timedelta(days=days)


@dataclass(frozen=True)
class AuditLapseVerdict:
    """Whether an audit outcome's cadence has elapsed, and on what evidence."""

    state: str
    reason: str
    last_completed_at: Optional[datetime]
    next_due_at: Optional[datetime]
    frequency: Optional[str]
    frequency_days: Optional[int]

    def as_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "reason": self.reason,
            "last_completed_at": self.last_completed_at,
            "next_due_at": self.next_due_at,
            "frequency": self.frequency,
            "frequency_days": self.frequency_days,
        }


UNKNOWN_AUDIT_LAPSE = AuditLapseVerdict(
    state="unknown",
    reason="no_audit_run",
    last_completed_at=None,
    next_due_at=None,
    frequency=None,
    frequency_days=None,
)


def classify_audit_lapse(
    *,
    completed_at: Optional[datetime] = None,
    due_date: Optional[datetime] = None,
    frequency: Any = None,
    found: bool = True,
    now: Optional[datetime] = None,
) -> AuditLapseVerdict:
    """Classify one ``audit_outcome`` link's run against its cadence.

    Two distinct kinds of lapse are recognised, and neither is fabricated:

    * a run that was never completed and is past its own ``due_date``;
    * a completed run whose template cadence has since elapsed.

    A run with no cadence and no due date yields ``unknown`` — the composer
    says so rather than implying the audit is in good standing.
    """
    if not found:
        return UNKNOWN_AUDIT_LAPSE

    moment = as_aware_utc(now) or _utc_now()
    freq_key = normalise_status(frequency)
    freq_days = audit_frequency_days(frequency)
    completed = as_aware_utc(completed_at)

    if completed is None:
        due = as_aware_utc(due_date)
        if due is None:
            return AuditLapseVerdict(
                state="unknown",
                reason="audit_not_completed",
                last_completed_at=None,
                next_due_at=None,
                frequency=freq_key,
                frequency_days=freq_days,
            )
        if moment > due:
            state, reason = "lapsed", "run_past_due"
        elif moment >= due - timedelta(days=AUDIT_LAPSE_DUE_SOON_WINDOW_DAYS):
            state, reason = "due_soon", "run_due_soon"
        else:
            state, reason = "current", "run_within_due"
        return AuditLapseVerdict(
            state=state,
            reason=reason,
            last_completed_at=None,
            next_due_at=due,
            frequency=freq_key,
            frequency_days=freq_days,
        )

    if freq_days is None:
        return AuditLapseVerdict(
            state="unknown",
            reason="no_audit_cadence",
            last_completed_at=completed,
            next_due_at=None,
            frequency=freq_key,
            frequency_days=None,
        )

    next_due = completed + timedelta(days=freq_days)
    if moment > next_due:
        state, reason = "lapsed", "cadence_overdue"
    elif moment >= next_due - _lapse_due_soon_window(freq_days):
        state, reason = "due_soon", "cadence_due_soon"
    else:
        state, reason = "current", "within_cadence"
    return AuditLapseVerdict(
        state=state,
        reason=reason,
        last_completed_at=completed,
        next_due_at=next_due,
        frequency=freq_key,
        frequency_days=freq_days,
    )


__all__ = [
    "AUDIT_FREQUENCY_DAYS",
    "AUDIT_LAPSE_DUE_SOON_WINDOW_DAYS",
    "AUDIT_LAPSE_STATES",
    "DOCUMENT_DUE_SOON_WINDOW_DAYS",
    "DOCUMENT_FRESHNESS_STATES",
    "OBSOLETE_CONTROLLED_STATUSES",
    "OBSOLETE_LIBRARY_STATUSES",
    "UNKNOWN_AUDIT_LAPSE",
    "AuditLapseVerdict",
    "DocumentFreshnessVerdict",
    "as_aware_utc",
    "audit_frequency_days",
    "classify_audit_lapse",
    "classify_document_freshness",
    "is_obsolete_controlled_status",
    "is_obsolete_library_status",
    "normalise_status",
]
