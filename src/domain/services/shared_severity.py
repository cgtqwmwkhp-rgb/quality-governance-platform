"""The one severity set the case registers share, and how portal text reaches it.

``severity_levels`` is a single admin lookup category that fills three
differently-named fields: incident ``severity``, complaint ``priority`` and
near-miss ``potential_severity``. Until B-9 the three disagreed — the dropdown
offered ``negligible`` and only incident severity accepted it, so a reporter who
picked it got HTTP 422 on a complaint and on a near miss. The product decision
was one shared set rather than three taxonomies, and this module is where that
set is stated once.

:class:`IncidentSeverity` is the definition; :class:`ComplaintPriority` mirrors it
member for member, which ``tests/unit/test_shared_severity_set.py`` holds.

Two scales deliberately stay outside it:

* ``RTASeverity`` is an injury-outcome scale derived from reported harm, never
  from a triage word — see :mod:`src.domain.services.rta_severity`.
* ``NearMiss.priority`` is a workflow queue, still four uppercase values under
  ``ck_near_misses_priority``. :func:`near_miss_priority_for_severity` is the
  documented projection from the five-value set onto it.
"""

from __future__ import annotations

from typing import Any

from src.domain.models.complaint import ComplaintPriority
from src.domain.models.incident import IncidentSeverity

SHARED_SEVERITY_VALUES: frozenset[str] = frozenset(member.value for member in IncidentSeverity)

_FALLBACK = IncidentSeverity.MEDIUM.value

_NEAR_MISS_PRIORITY_FOR_SEVERITY: dict[str, str] = {
    IncidentSeverity.NEGLIGIBLE.value: "LOW",
    IncidentSeverity.LOW.value: "LOW",
    IncidentSeverity.MEDIUM.value: "MEDIUM",
    IncidentSeverity.HIGH.value: "HIGH",
    IncidentSeverity.CRITICAL.value: "CRITICAL",
}


def normalize_portal_severity(severity: Any) -> str:
    """Read the portal's severity word as a member of the shared set.

    ``QuickReportCreate.severity`` is an unvalidated string, so a portal client can
    post anything at all. Every column it reaches is a closed set — two of them now
    carry a CHECK constraint saying so — therefore an unrecognised word has to
    become a known one here rather than arriving at the database as free text.
    """
    candidate = str(severity or "").strip().lower()
    return candidate if candidate in SHARED_SEVERITY_VALUES else _FALLBACK


def map_portal_severity(severity: Any) -> tuple[IncidentSeverity, ComplaintPriority]:
    """Resolve one portal severity word onto both case enums."""
    shared = normalize_portal_severity(severity)
    return IncidentSeverity(shared), ComplaintPriority(shared)


def near_miss_priority_for_severity(severity: Any) -> str:
    """Project the shared severity set onto the near-miss workflow priority."""
    return _NEAR_MISS_PRIORITY_FOR_SEVERITY[normalize_portal_severity(severity)]
