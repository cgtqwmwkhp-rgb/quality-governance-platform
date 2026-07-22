"""Canonical audit question type registry for builder ↔ API round-trip.

Mirrors ``src/api/schemas/audit.py`` ``question_type`` allowlist and the
frontend audit-builder palette types. Prefer lossless mappings; document
unavoidable collapses (``datetime``→``date``, ``dropdown``→``multi_choice``,
``file``→``text_short``, ``score``→scale via rating metadata).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

# Matches Field pattern on AuditQuestionBase.question_type in schemas/audit.py.
API_QUESTION_TYPES: frozenset[str] = frozenset(
    {
        "text",
        "textarea",
        "number",
        "checkbox",
        "radio",
        "dropdown",
        "date",
        "datetime",
        "signature",
        "photo",
        "file",
        "rating",
        "yes_no",
        "pass_fail",
        "score",
        "user_select",
        "location_select",
        "customer_select",
    }
)

# Frontend audit-builder palette (see QuestionEditor QUESTION_TYPES).
FE_BUILDER_QUESTION_TYPES: frozenset[str] = frozenset(
    {
        "yes_no",
        "yes_no_na",
        "scale_1_5",
        "scale_1_10",
        "text_short",
        "text_long",
        "numeric",
        "date",
        "photo",
        "signature",
        "multi_choice",
        "checklist",
        "pass_fail",
        "user_select",
        "location_select",
        "customer_select",
    }
)

# Ordered palette list for parametrized round-trip tests.
FE_PALETTE_ORDER: tuple[str, ...] = (
    "yes_no",
    "yes_no_na",
    "pass_fail",
    "scale_1_5",
    "scale_1_10",
    "multi_choice",
    "checklist",
    "text_short",
    "text_long",
    "numeric",
    "date",
    "photo",
    "signature",
    "user_select",
    "location_select",
    "customer_select",
)

# API types produced by the palette forward map (round-trip reverse targets).
PALETTE_API_TYPES: frozenset[str] = frozenset(
    {
        "yes_no",
        "pass_fail",
        "rating",
        "radio",
        "checkbox",
        "text",
        "textarea",
        "number",
        "date",
        "photo",
        "signature",
        "user_select",
        "location_select",
        "customer_select",
    }
)


@dataclass(frozen=True)
class ApiQuestionTypeSpec:
    """API question_type plus metadata required for lossless FE→API encoding."""

    question_type: str
    allow_na: bool = False
    max_score: Optional[float] = None
    max_value: Optional[float] = None


_FE_TO_API: dict[str, ApiQuestionTypeSpec] = {
    "yes_no": ApiQuestionTypeSpec(question_type="yes_no", allow_na=False),
    "yes_no_na": ApiQuestionTypeSpec(question_type="yes_no", allow_na=True),
    "scale_1_5": ApiQuestionTypeSpec(question_type="rating", max_score=5.0, max_value=5.0),
    "scale_1_10": ApiQuestionTypeSpec(question_type="rating", max_score=10.0, max_value=10.0),
    "text_short": ApiQuestionTypeSpec(question_type="text"),
    "text_long": ApiQuestionTypeSpec(question_type="textarea"),
    "numeric": ApiQuestionTypeSpec(question_type="number"),
    "date": ApiQuestionTypeSpec(question_type="date"),
    "photo": ApiQuestionTypeSpec(question_type="photo"),
    "signature": ApiQuestionTypeSpec(question_type="signature"),
    "multi_choice": ApiQuestionTypeSpec(question_type="radio"),
    "checklist": ApiQuestionTypeSpec(question_type="checkbox"),
    "pass_fail": ApiQuestionTypeSpec(question_type="pass_fail"),
    "user_select": ApiQuestionTypeSpec(question_type="user_select"),
    "location_select": ApiQuestionTypeSpec(question_type="location_select"),
    "customer_select": ApiQuestionTypeSpec(question_type="customer_select"),
}


def to_api_question_type(fe_type: str) -> ApiQuestionTypeSpec:
    """Map a frontend builder type to an API question_type + metadata.

    Raises:
        ValueError: if ``fe_type`` is not a known builder palette type.
    """
    try:
        return _FE_TO_API[fe_type]
    except KeyError as exc:
        raise ValueError(f"Unknown frontend builder question type: {fe_type!r}") from exc


def from_api_question_type(
    api_type: str,
    *,
    allow_na: bool = False,
    max_score: Optional[float] = None,
    max_value: Optional[float] = None,
) -> str:
    """Map an API question_type (+ metadata) to a frontend builder type.

    Unavoidable collapses (no distinct palette peer):
    - ``datetime`` → ``date``
    - ``dropdown`` → ``multi_choice`` (same as ``radio``)
    - ``file`` → ``text_short``
    - ``score`` → scale via rating metadata (same as ``rating``)
    """
    if api_type == "yes_no":
        return "yes_no_na" if allow_na else "yes_no"
    if api_type == "pass_fail":
        return "pass_fail"
    if api_type in {"date", "datetime"}:
        return "date"
    if api_type == "textarea":
        return "text_long"
    if api_type == "number":
        return "numeric"
    if api_type == "photo":
        return "photo"
    if api_type == "signature":
        return "signature"
    if api_type in {"radio", "dropdown"}:
        return "multi_choice"
    if api_type == "checkbox":
        return "checklist"
    if api_type == "user_select":
        return "user_select"
    if api_type == "location_select":
        return "location_select"
    if api_type == "customer_select":
        return "customer_select"
    if api_type in {"rating", "score"}:
        scale = max_score if max_score is not None else max_value
        if scale is None:
            scale = 5.0
        return "scale_1_10" if scale > 5 else "scale_1_5"
    if api_type == "text":
        return "text_short"
    if api_type == "file":
        return "text_short"
    # Unknown API types default to short text (matches prior builder behaviour).
    return "text_short"
