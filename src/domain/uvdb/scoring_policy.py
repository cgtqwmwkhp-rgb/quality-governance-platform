"""UVDB qualification scoring policy (PX-255).

Imported Achilles reports often carry per-section percentages for protocol
sections whose questions were never loaded into this system
(``content_status == "pending_protocol_pdf"``). Rendering those figures as
live qualification evidence fabricates a high overall score from absent
content.

Policy:
  * A section is **assessable** only when its protocol content is loaded
    (not pending the official PDF).
  * Scores on non-assessable sections are **excluded** from the qualification
    average (cleared to absent), never treated as compliant.
  * The exclusion is stated on the returned entry so the UI can explain it.
  * Zeroing is available as an explicit mode for callers that prefer a hard
    fail over exclusion; the default path excludes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Literal, Optional

from src.domain.services.uvdb_service import average_percentage, coerce_score, derive_percentage

CONTENT_STATUS_LOADED = "loaded"
CONTENT_STATUS_PENDING_PROTOCOL_PDF = "pending_protocol_pdf"

EXCLUSION_PENDING_PROTOCOL_PDF = "pending_protocol_pdf"
EXCLUSION_EMPTY_SECTION = "empty_section"

ScorePolicyMode = Literal["exclude", "zero"]


def section_is_assessable(section: Mapping[str, Any] | None) -> bool:
    """Return True when the protocol section can contribute to qualification.

    Pending-PDF shells (no loaded questions) are not assessable. A missing
    section descriptor is treated as non-assessable so we never invent
    assessability we cannot prove.
    """
    if not section:
        return False
    status = str(section.get("content_status") or CONTENT_STATUS_LOADED).strip()
    if status == CONTENT_STATUS_PENDING_PROTOCOL_PDF:
        return False
    questions = section.get("questions")
    if isinstance(questions, list) and len(questions) == 0:
        # Loaded status with an empty question list is still absent content.
        max_score = coerce_score(section.get("max_score")) or 0.0
        if max_score <= 0:
            return False
    return True


def build_assessability_index(
    protocol_sections: Sequence[Mapping[str, Any]],
) -> dict[str, Mapping[str, Any]]:
    """Map protocol section number -> section descriptor."""
    index: dict[str, Mapping[str, Any]] = {}
    for section in protocol_sections:
        number = str(section.get("number") or "").strip()
        if number:
            index[number] = section
    return index


def _clear_score_fields(entry: dict[str, Any], *, zero: bool) -> dict[str, Any]:
    out = dict(entry)
    if zero:
        out["score"] = 0.0
        out["percentage"] = 0.0
        # Preserve max_score when present so the UI can still show 0/N.
        if out.get("max_score") is None:
            out["max_score"] = 0.0
    else:
        out["score"] = None
        out["percentage"] = None
        # Keep max_score for context when the report supplied one; absence stays.
    return out


def apply_section_score_policy(
    entry: Mapping[str, Any],
    *,
    content_status: Optional[str],
    mode: ScorePolicyMode = "exclude",
    protocol_section: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply PX-255 policy to one normalised section score entry.

    Assessable sections pass through with ``assessed=True``. Non-assessable
    sections are excluded (default) or zeroed, and always carry an explicit
    exclusion reason.
    """
    normalised = dict(entry)
    section = protocol_section
    if section is None and content_status is not None:
        section = {"content_status": content_status, "questions": [], "max_score": 0}

    assessable = section_is_assessable(section)
    if assessable:
        normalised["assessed"] = True
        normalised["excluded_from_qualification"] = False
        normalised["exclusion_reason"] = None
        # Re-derive percentage if only score/max present.
        if normalised.get("percentage") is None:
            normalised["percentage"] = derive_percentage(
                coerce_score(normalised.get("score")),
                coerce_score(normalised.get("max_score")),
            )
        return normalised

    reason = EXCLUSION_PENDING_PROTOCOL_PDF
    status = str((section or {}).get("content_status") or content_status or "").strip()
    if status != CONTENT_STATUS_PENDING_PROTOCOL_PDF:
        reason = EXCLUSION_EMPTY_SECTION

    cleared = _clear_score_fields(normalised, zero=(mode == "zero"))
    cleared["assessed"] = False
    cleared["excluded_from_qualification"] = True
    cleared["exclusion_reason"] = reason
    return cleared


def apply_section_scores_policy(
    sections_map: Mapping[str, Mapping[str, Any]],
    *,
    protocol_sections: Sequence[Mapping[str, Any]],
    mode: ScorePolicyMode = "exclude",
) -> dict[str, dict[str, Any]]:
    """Apply policy to a section-number -> score map."""
    index = build_assessability_index(protocol_sections)
    out: dict[str, dict[str, Any]] = {}
    for number, entry in sections_map.items():
        key = str(number).strip()
        protocol = index.get(key)
        content_status = str((protocol or {}).get("content_status") or CONTENT_STATUS_LOADED)
        out[key] = apply_section_score_policy(
            entry,
            content_status=content_status,
            mode=mode,
            protocol_section=protocol,
        )
    return out


def qualification_percentage_from_sections(
    sections_map: Mapping[str, Mapping[str, Any]],
    *,
    protocol_sections: Sequence[Mapping[str, Any]] | None = None,
) -> Optional[float]:
    """Mean percentage over assessable, non-excluded scored sections.

    Returns None when nothing assessable is scored — never 0.0 or 100.0 from an
    empty population.
    """
    if protocol_sections is not None:
        sections_map = apply_section_scores_policy(
            sections_map,
            protocol_sections=protocol_sections,
            mode="exclude",
        )

    values: list[Optional[float]] = []
    for entry in sections_map.values():
        if entry.get("excluded_from_qualification"):
            continue
        if entry.get("assessed") is False:
            continue
        values.append(coerce_score(entry.get("percentage")))
    return average_percentage(values)


def policy_adjusted_audit_percentage(
    *,
    stored_percentage: Optional[float],
    section_scores_raw: Any,
    protocol_sections: Sequence[Mapping[str, Any]],
    match_section,
    normalise_entry,
    title_index: Mapping[str, str] | None = None,
) -> tuple[Optional[float], dict[str, Any]]:
    """Recompute an audit's qualification % excluding pending-empty sections.

    When the audit has no usable section breakdown, falls back to the stored
    percentage (import-time figure) and reports that policy could not adjust.

    ``match_section`` / ``normalise_entry`` are injected so this module stays
    free of route-layer imports while remaining testable.
    """
    meta: dict[str, Any] = {
        "policy_applied": False,
        "excluded_section_numbers": [],
        "included_section_numbers": [],
        "fallback_to_stored": False,
    }

    entries = []
    if isinstance(section_scores_raw, dict):
        raw_list = section_scores_raw.get("sections", [])
        if isinstance(raw_list, list):
            entries = [e for e in raw_list if isinstance(e, dict)]
    if not entries:
        meta["fallback_to_stored"] = True
        return stored_percentage, meta

    valid = [str(s.get("number")) for s in protocol_sections if s.get("number") is not None]
    index = build_assessability_index(protocol_sections)
    scored: dict[str, dict[str, Any]] = {}
    for entry in entries:
        normalised = normalise_entry(entry)
        number = match_section(
            normalised.get("label") or "",
            valid_section_numbers=valid,
            title_index=title_index,
        )
        if number is None or number in scored:
            continue
        protocol = index.get(number)
        scored[number] = apply_section_score_policy(
            normalised,
            content_status=str((protocol or {}).get("content_status") or CONTENT_STATUS_LOADED),
            mode="exclude",
            protocol_section=protocol,
        )

    if not scored:
        meta["fallback_to_stored"] = True
        return stored_percentage, meta

    included = [
        n for n, e in scored.items() if not e.get("excluded_from_qualification") and e.get("percentage") is not None
    ]
    excluded = [n for n, e in scored.items() if e.get("excluded_from_qualification")]
    meta["policy_applied"] = True
    meta["included_section_numbers"] = included
    meta["excluded_section_numbers"] = excluded

    adjusted = qualification_percentage_from_sections(scored)
    return adjusted, meta
