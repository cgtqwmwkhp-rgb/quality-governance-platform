"""Composition helpers for branching audits.

Determines which sections/questions are in-scope for a given audit run based
on the run's ``assessment_mode`` and ``asset_type_id`` dimensions and each
section's ``applicability_rules_json``.

Rule shape (``AuditSection.applicability_rules_json``)::

    {"assessment_modes": ["full", "spot_check"] | None, "asset_type_ids": [1, 2] | None}

``None``, an empty dict, or a missing key means that dimension is unrestricted
(always applicable). A question inherits its section's applicability — there
is no independent per-question composition rule in this slice.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional, Protocol, runtime_checkable


@runtime_checkable
class _SectionLike(Protocol):
    id: Any
    applicability_rules_json: Optional[dict]


@runtime_checkable
class _QuestionLike(Protocol):
    id: Any
    section_id: Optional[Any]
    is_active: bool


def _normalize_rule_list(raw: Any) -> Optional[list]:
    """Return ``None`` for "unrestricted", else a list of allowed values."""
    if raw is None:
        return None
    if isinstance(raw, (list, tuple, set)):
        values = [v for v in raw if v is not None]
        return values or None
    return [raw]


def section_is_applicable(
    section: Any,
    *,
    assessment_mode: Optional[str] = None,
    asset_type_id: Optional[int] = None,
) -> bool:
    """Return True when *section* is in scope for the given run dimensions.

    A section with no rules (or an empty/None ``applicability_rules_json``)
    is always applicable. Each configured dimension must match for the
    section to apply; unconfigured dimensions on the rule are ignored.
    """
    rules = getattr(section, "applicability_rules_json", None)
    if not rules:
        return True
    if not isinstance(rules, dict):
        return True

    allowed_modes = _normalize_rule_list(rules.get("assessment_modes"))
    if allowed_modes is not None:
        if assessment_mode is None or assessment_mode not in allowed_modes:
            return False

    allowed_asset_types = _normalize_rule_list(rules.get("asset_type_ids"))
    if allowed_asset_types is not None:
        if asset_type_id is None or asset_type_id not in allowed_asset_types:
            return False

    return True


def question_is_applicable(
    question: Any,
    *,
    section: Any = None,
    assessment_mode: Optional[str] = None,
    asset_type_id: Optional[int] = None,
) -> bool:
    """Return True when *question* is in scope, inheriting its section's rules.

    If *section* is not supplied, falls back to ``question.section`` (a loaded
    relationship) when available; a question with no resolvable section is
    treated as always applicable (top-level / unsectioned questions).
    """
    resolved_section = section if section is not None else getattr(question, "section", None)
    if resolved_section is None:
        return True
    return section_is_applicable(
        resolved_section,
        assessment_mode=assessment_mode,
        asset_type_id=asset_type_id,
    )


def compose_template_questions(
    template_or_sections: Any,
    *,
    assessment_mode: Optional[str] = None,
    asset_type_id: Optional[int] = None,
    questions: Optional[Iterable[Any]] = None,
) -> set:
    """Return the set of question ids that are in-scope for these dimensions.

    Accepts either an ``AuditTemplate`` (with ``.sections`` and ``.questions``
    relationships loaded) or an iterable of ``AuditSection`` objects. When a
    plain iterable of sections is passed, *questions* must also be supplied
    (since sections alone don't necessarily expose their questions).
    """
    sections: list = []
    all_questions: list = []

    if hasattr(template_or_sections, "sections") and hasattr(template_or_sections, "questions"):
        sections = list(template_or_sections.sections or [])
        all_questions = list(template_or_sections.questions or [])
        # Some call sites only populate section.questions (not the flat template.questions
        # list) — fall back to the union so nothing silently drops out.
        seen_ids = {id(q) for q in all_questions}
        for sec in sections:
            for q in getattr(sec, "questions", None) or []:
                if id(q) not in seen_ids:
                    all_questions.append(q)
                    seen_ids.add(id(q))
    else:
        sections = list(template_or_sections or [])
        all_questions = list(questions or [])

    section_by_id = {sec.id: sec for sec in sections}
    applicable_ids: set = set()

    for question in all_questions:
        if not getattr(question, "is_active", True):
            continue
        section_id = getattr(question, "section_id", None)
        section = section_by_id.get(section_id) if section_id is not None else None
        if section_id is not None and section is None:
            # Section reference not resolvable in the supplied set — fail open
            # (treat as unsectioned) rather than silently excluding questions.
            applicable = True
        else:
            applicable = question_is_applicable(
                question,
                section=section,
                assessment_mode=assessment_mode,
                asset_type_id=asset_type_id,
            )
        if applicable:
            applicable_ids.add(question.id)

    return applicable_ids
