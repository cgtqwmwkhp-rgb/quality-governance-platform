"""UVDB Achilles Verify B2 business logic.

Encapsulates LTIFR calculation, audit reference number generation, and the
presentation rules for UVDB scores (provenance and absent-score handling).
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping, Sequence
from datetime import datetime, timezone
from typing import Any, Optional

# Provenance of a displayed UVDB score. A UVDB audit can be scored in-app from
# protocol question responses, or carry a score lifted out of an externally
# issued PDF report at import time. The two are not interchangeable evidence,
# so every score leaves the API tagged with which one it is.
SCORE_SOURCE_IMPORTED = "imported"
SCORE_SOURCE_CALCULATED = "calculated"
# Used when the import linkage could not be read (e.g. the external-import
# tables are absent). Claiming "calculated" here would assert provenance we do
# not have.
SCORE_SOURCE_UNKNOWN = "unknown"

_SECTION_PREFIX_RE = re.compile(r"^\s*(?:section|sec)\.?\s*(\d{1,2})\b", re.IGNORECASE)
_LEADING_NUMBER_RE = re.compile(r"^\s*(\d{1,2})(?:\.\d+)*\s*[.)\u2013\u2014:-]\s*")
_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")


def resolve_provenance(*, import_job_id: Optional[int], provenance_resolved: bool = True) -> str:
    """Classify where a UVDB score came from.

    *provenance_resolved* is False when the import linkage could not be
    queried, in which case the provenance is reported as unknown rather than
    defaulted to "calculated".
    """
    if not provenance_resolved:
        return SCORE_SOURCE_UNKNOWN
    return SCORE_SOURCE_IMPORTED if import_job_id else SCORE_SOURCE_CALCULATED


def resolve_score_source(
    percentage_score: Optional[float],
    *,
    import_job_id: Optional[int],
    provenance_resolved: bool = True,
) -> Optional[str]:
    """Return the provenance of a score, or None when there is no score.

    A None return means "not scored" and must render as absent — never as 0.
    """
    if percentage_score is None:
        return None
    return resolve_provenance(import_job_id=import_job_id, provenance_resolved=provenance_resolved)


def coerce_score(value: Any) -> Optional[float]:
    """Parse a score-ish value, preserving absence as None.

    Imported breakdowns are OCR-derived, so values arrive as numbers, numeric
    strings, or "82%". Anything unparseable is absent, not zero.
    """
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip().rstrip("%").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def derive_percentage(score: Optional[float], max_score: Optional[float]) -> Optional[float]:
    """Percentage of *score* against *max_score*, or None when undefined.

    An absent or zero denominator yields None. It must never yield 100.0 —
    "nothing to score" is not "everything passed".
    """
    if score is None or max_score is None or max_score <= 0:
        return None
    return round((score / max_score) * 100, 1)


def average_percentage(values: Iterable[Optional[float]]) -> Optional[float]:
    """Mean of the scored values, or None when nothing is scored.

    Returns None rather than 0.0 or 100.0 on an empty population.
    """
    scored = [float(value) for value in values if value is not None]
    if not scored:
        return None
    return round(sum(scored) / len(scored), 1)


def normalise_section_score(
    entry: Mapping[str, Any],
    *,
    audit_reference: Optional[str],
    score_source: Optional[str],
) -> dict[str, Any]:
    """Coerce one imported score-breakdown entry into the API shape.

    Missing score / max_score / percentage stay None so the UI can render them
    as absent instead of as a real-looking zero.
    """
    label = str(entry.get("label") or "").strip()
    score = coerce_score(entry.get("score"))
    max_score = coerce_score(entry.get("max_score"))
    percentage = coerce_score(entry.get("percentage"))
    if percentage is None:
        percentage = derive_percentage(score, max_score)
    return {
        "label": label,
        "score": score,
        "max_score": max_score,
        "percentage": percentage,
        "audit_reference": audit_reference,
        "score_source": score_source,
    }


def _normalise_title(value: str) -> str:
    return _NON_ALNUM_RE.sub(" ", value.lower()).strip()


def build_section_title_index(sections: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """Index protocol section titles to section numbers for exact-title matching.

    Titles that are not unique across the protocol are excluded, so a lookup can
    never attribute an imported score to the wrong section.
    """
    counts: dict[str, int] = {}
    index: dict[str, str] = {}
    for section in sections:
        title = _normalise_title(str(section.get("title") or ""))
        number = str(section.get("number") or "").strip()
        if not title or not number:
            continue
        counts[title] = counts.get(title, 0) + 1
        index[title] = number
    return {title: number for title, number in index.items() if counts[title] == 1}


def match_protocol_section(
    label: str,
    *,
    valid_section_numbers: Iterable[str],
    title_index: Optional[Mapping[str, str]] = None,
) -> Optional[str]:
    """Map an imported breakdown label onto a UVDB protocol section number.

    Only deterministic evidence is accepted: an explicit "Section N" prefix, a
    leading "N." token, or an exact match on a unique protocol section title.
    Returns None when the label cannot be mapped — callers must surface such an
    entry as unmapped rather than guessing, because a positional guess silently
    attributes a real score to the wrong section.
    """
    if not label:
        return None
    valid = {str(number).strip() for number in valid_section_numbers}

    for pattern in (_SECTION_PREFIX_RE, _LEADING_NUMBER_RE):
        match = pattern.match(label)
        if match and match.lastindex:
            number = str(int(match.group(1)))
            if number in valid:
                return number

    if title_index:
        by_title = title_index.get(_normalise_title(label))
        if by_title and by_title in valid:
            return by_title

    return None


class UVDBService:
    """Pure-function service for UVDB audit calculations."""

    @staticmethod
    def calculate_ltifr(
        lost_time_incidents: int,
        riddor_reportable: int,
        total_man_hours: int | None,
    ) -> float | None:
        """Calculate the Lost Time Injury Frequency Rate.

        ``LTIFR = (lost_time + riddor) / man_hours * 1_000_000``

        Returns *None* when *total_man_hours* is missing or zero.
        """
        if not total_man_hours or total_man_hours <= 0:
            return None
        lost_time = lost_time_incidents + riddor_reportable
        return (lost_time / total_man_hours) * 1_000_000

    @staticmethod
    def generate_audit_reference(existing_count: int, year: int | None = None) -> str:
        """Generate the next sequential audit reference.

        Format: ``UVDB-{year}-{nnnn}``
        """
        if year is None:
            year = datetime.now(timezone.utc).year
        return f"UVDB-{year}-{(existing_count + 1):04d}"
