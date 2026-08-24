"""Library CUT-1 — the one retention policy for Register documents.

ADR-0023 makes QGP the system of record and retires Citation (ATLAS)'s flat
"7 Years / all employees" position. Its own risk register names the condition
that has to hold before that retirement is honest:

    Retention becomes load-bearing the moment QGP is authoritative, but
    ``retention_rule`` is still free-text prose that computes nothing.
    Mitigation: treat machine-readable retention (``retention_years`` +
    ``retention_basis``) as a prerequisite of cutover, not a follow-up.

F-7 (`docs/governance/library-home-inventory-f7.md` §2) then assigns the homes:
category ``retention_rule`` **migrates** to machine-readable defaults copied onto
the document at file, and ``documents.retention_until`` **stays** the single
document-level clock. This module is that migration's brain — the only place
prose becomes a number, and the only place a number becomes a date.

Northern Star R19 ("Retention is a number of years with a basis; a disposal date
must be calculable") is therefore satisfied *or explicitly refused* here, never
guessed.

What changed and why it matters
-------------------------------
The pre-CUT-1 parser was ``re.search(r"(\\d+)\\s*years?")`` — first match wins,
clock always starts at approval. On the checked-in taxonomy that silently
produced disposal dates that are **too early**, and disposal hard-deletes the
row and the blob:

- ``"3 years minimum (to age 21 if a minor); investigations 6 years"`` took 3,
  dropping the 6-year investigation leg entirely.
- ``"Current + superseded 6 years"`` started the six years at *approval*, so a
  document that stayed current for ten years was disposable the day it was
  superseded — the rule says six years *after* that.
- ``"Life of asset + 6 years"`` started at approval, before the asset existed.

Every rule is therefore classified into an :class:`RetentionAnchor`, and a rule
that names two different periods, a scoped clause or a condition is **refused**
rather than reduced to whichever number the regex found first. A refusal leaves
``retention_until`` NULL, and a NULL is never a disposal candidate — so the
conservative outcome of an unreadable rule is "keep", not "destroy".

The resulting invariant, pinned by ``tests/unit/test_lib_cut1_retention_policy``:
for every rule in the checked-in taxonomy, the CUT-1 disposal date is never
earlier than the pre-CUT-1 one. Converging retention can extend how long a
document is kept; it can never shorten it.
"""

from __future__ import annotations

import calendar
import enum
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Final, Optional


class RetentionAnchor(str, enum.Enum):
    """The event the retention period is measured from."""

    #: Measured from the date the document was approved / issued.
    ISSUE = "issue"
    #: Measured from the date the document was superseded or otherwise left the
    #: live set. Not calculable while the document is still current.
    SUPERSEDE = "supersede"
    #: Measured from an event QGP does not hold (life of an asset, duration of
    #: employment, end of a contract). Never calculable in-app.
    EVENT = "event"
    #: No elapsed period at all — the current issue is kept indefinitely.
    INDEFINITE = "indefinite"


#: Why a rule produced no policy. Stable strings: the cutover readiness report
#: and the disposal queue both group by them, and stewards clear them by name.
REASON_ABSENT: Final[str] = "absent"
REASON_SCOPED_CLAUSES: Final[str] = "scoped_clauses"
REASON_CONDITIONAL: Final[str] = "conditional"
REASON_MULTIPLE_PERIODS: Final[str] = "multiple_periods"
REASON_SUB_YEAR_PERIOD: Final[str] = "sub_year_period"
REASON_UNPARSED: Final[str] = "unparsed"

UNDECIDABLE_REASONS: Final[frozenset[str]] = frozenset(
    {
        REASON_ABSENT,
        REASON_SCOPED_CLAUSES,
        REASON_CONDITIONAL,
        REASON_MULTIPLE_PERIODS,
        REASON_SUB_YEAR_PERIOD,
        REASON_UNPARSED,
    }
)

_DURATION_RE = re.compile(r"(\d+)\s*(year|month)s?", re.IGNORECASE)

# A colon or semicolon in these rules introduces a *different* record type with
# its own period ("Tacho data 12 months; working time records 2 years"). One
# category-level number cannot represent two, so the category needs a steward
# decision rather than a coin toss.
_SCOPE_SEPARATORS: Final[tuple[str, ...]] = (";", ":")

# Words that make the period conditional on something the register does not
# record ("longer if incident-related", "40 years where linked to exposure
# monitoring", "recommended", "minimum").
_CONDITIONAL_MARKERS: Final[tuple[str, ...]] = (
    " if ",
    " where ",
    "longer",
    "recommended",
    "minimum",
)

# Events QGP does not hold a date for. Checked before the supersede markers
# because "Current logbook + 6 years" is anchored on the logbook closing, not on
# the document being superseded.
_EVENT_MARKERS: Final[tuple[str, ...]] = (
    "life of",
    "duration of",
    "employment",
    "while processing",
    "contract",
    "occupancy",
    "logbook",
    "until next report",
)

# "Keep the current issue, and superseded issues for N years."
_SUPERSEDE_MARKERS: Final[tuple[str, ...]] = ("supersede", "superseded", "current", "previous")


@dataclass(frozen=True)
class RetentionPolicy:
    """A machine-readable retention rule: R19's number plus its basis."""

    years: Optional[int]
    anchor: RetentionAnchor
    #: The source rule, verbatim. R19 requires a *basis*, and the honest basis
    #: is the governance prose the number was read from — not a paraphrase.
    basis: str

    @property
    def is_computable(self) -> bool:
        """True when a disposal date can ever be calculated for this policy."""
        return self.years is not None and self.anchor in (RetentionAnchor.ISSUE, RetentionAnchor.SUPERSEDE)


@dataclass(frozen=True)
class RetentionDecision:
    """The resolver's answer, including why when there is no policy."""

    policy: Optional[RetentionPolicy]
    reason: str

    @property
    def is_decided(self) -> bool:
        return self.policy is not None


def _normalised(rule: Optional[str]) -> str:
    return " ".join((rule or "").split()).lower()


def resolve_retention_rule(rule: Optional[str]) -> RetentionDecision:
    """Classify one taxonomy ``retention_rule`` into a policy, or refuse it.

    Deterministic and total: every input returns a decision, and an input the
    grammar cannot read returns ``policy=None`` with a named reason instead of a
    plausible-looking number.
    """
    text = _normalised(rule)
    if not text:
        return RetentionDecision(None, REASON_ABSENT)

    if any(separator in text for separator in _SCOPE_SEPARATORS):
        return RetentionDecision(None, REASON_SCOPED_CLAUSES)
    if any(marker in f" {text} " for marker in _CONDITIONAL_MARKERS):
        return RetentionDecision(None, REASON_CONDITIONAL)

    durations = _DURATION_RE.findall(text)
    periods = {(int(amount), unit.lower()) for amount, unit in durations}
    if len(periods) > 1:
        return RetentionDecision(None, REASON_MULTIPLE_PERIODS)

    years: Optional[int] = None
    if periods:
        amount, unit = next(iter(periods))
        if unit != "year":
            # `retention_years` is a year count by definition (R19). A months-only
            # rule is not roundable to years without changing the policy.
            return RetentionDecision(None, REASON_SUB_YEAR_PERIOD)
        if amount <= 0:
            return RetentionDecision(None, REASON_UNPARSED)
        years = amount

    basis = " ".join((rule or "").split())

    if any(marker in text for marker in _EVENT_MARKERS):
        return RetentionDecision(RetentionPolicy(years, RetentionAnchor.EVENT, basis), RetentionAnchor.EVENT.value)

    if years is None:
        if any(marker in text for marker in _SUPERSEDE_MARKERS):
            return RetentionDecision(
                RetentionPolicy(None, RetentionAnchor.INDEFINITE, basis),
                RetentionAnchor.INDEFINITE.value,
            )
        return RetentionDecision(None, REASON_UNPARSED)

    if any(marker in text for marker in _SUPERSEDE_MARKERS):
        return RetentionDecision(
            RetentionPolicy(years, RetentionAnchor.SUPERSEDE, basis),
            RetentionAnchor.SUPERSEDE.value,
        )
    return RetentionDecision(RetentionPolicy(years, RetentionAnchor.ISSUE, basis), RetentionAnchor.ISSUE.value)


def add_years(base: datetime, years: int) -> datetime:
    """Add whole calendar years, clamping 29 February onto 28 February.

    The pre-CUT-1 code used ``timedelta(days=years * 365)``, which lands ten days
    early on a forty-year retention. A disposal date that is short by any margin
    is a destroyed record, so the arithmetic is calendar-exact.
    """
    aware = base if base.tzinfo else base.replace(tzinfo=timezone.utc)
    target_year = aware.year + years
    last_day = calendar.monthrange(target_year, aware.month)[1]
    return aware.replace(year=target_year, day=min(aware.day, last_day))


def retention_until_for(
    policy: Optional[RetentionPolicy],
    *,
    issued_at: Optional[datetime] = None,
    superseded_at: Optional[datetime] = None,
) -> Optional[datetime]:
    """Compute the disposal date for a policy, or ``None`` when it is not due yet.

    ``None`` covers four honest cases and they are all "keep": no policy, an
    indefinite policy, an event QGP does not hold, and a supersede-anchored
    policy on a document that is still current.
    """
    if policy is None or policy.years is None:
        return None
    if policy.anchor is RetentionAnchor.ISSUE:
        return add_years(issued_at, policy.years) if issued_at is not None else None
    if policy.anchor is RetentionAnchor.SUPERSEDE:
        return add_years(superseded_at, policy.years) if superseded_at is not None else None
    return None


def policy_from_stored(
    *,
    retention_years: Optional[int],
    retention_anchor: Optional[str],
    retention_basis: Optional[str],
) -> Optional[RetentionPolicy]:
    """Rebuild a policy from the columns copied onto a document at file.

    The document is the system of record once filed (F-7 §2), so callers read
    these three columns rather than re-parsing the category prose — re-parsing
    would let a later taxonomy edit silently change the retention of documents
    that were filed under the old rule.
    """
    anchor_value = (retention_anchor or "").strip().lower()
    if not anchor_value:
        return None
    try:
        anchor = RetentionAnchor(anchor_value)
    except ValueError:
        return None
    return RetentionPolicy(retention_years, anchor, (retention_basis or "").strip())
