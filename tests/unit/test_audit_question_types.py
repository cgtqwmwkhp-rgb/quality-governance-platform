"""Unit tests for canonical audit question type registry round-trips."""

from __future__ import annotations

import pytest

from src.domain.constants.audit_question_types import (
    API_QUESTION_TYPES,
    FE_BUILDER_QUESTION_TYPES,
    FE_PALETTE_ORDER,
    PALETTE_API_TYPES,
    ApiQuestionTypeSpec,
    from_api_question_type,
    to_api_question_type,
)

# Every FE palette type → expected API spec.
_FE_TO_API_CASES: list[tuple[str, ApiQuestionTypeSpec]] = [
    ("yes_no", ApiQuestionTypeSpec(question_type="yes_no", allow_na=False)),
    ("yes_no_na", ApiQuestionTypeSpec(question_type="yes_no", allow_na=True)),
    (
        "scale_1_5",
        ApiQuestionTypeSpec(question_type="rating", max_score=5.0, max_value=5.0),
    ),
    (
        "scale_1_10",
        ApiQuestionTypeSpec(question_type="rating", max_score=10.0, max_value=10.0),
    ),
    ("text_short", ApiQuestionTypeSpec(question_type="text")),
    ("text_long", ApiQuestionTypeSpec(question_type="textarea")),
    ("numeric", ApiQuestionTypeSpec(question_type="number")),
    ("date", ApiQuestionTypeSpec(question_type="date")),
    ("photo", ApiQuestionTypeSpec(question_type="photo")),
    ("signature", ApiQuestionTypeSpec(question_type="signature")),
    ("multi_choice", ApiQuestionTypeSpec(question_type="radio")),
    ("checklist", ApiQuestionTypeSpec(question_type="checkbox")),
    ("pass_fail", ApiQuestionTypeSpec(question_type="pass_fail")),
    ("user_select", ApiQuestionTypeSpec(question_type="user_select")),
    ("location_select", ApiQuestionTypeSpec(question_type="location_select")),
    ("customer_select", ApiQuestionTypeSpec(question_type="customer_select")),
]


@pytest.mark.parametrize(("fe_type", "expected"), _FE_TO_API_CASES)
def test_to_api_question_type_for_every_fe_palette_type(fe_type: str, expected: ApiQuestionTypeSpec) -> None:
    assert to_api_question_type(fe_type) == expected


@pytest.mark.parametrize("fe_type", FE_PALETTE_ORDER)
def test_fe_palette_round_trip_preserves_builder_type(fe_type: str) -> None:
    api = to_api_question_type(fe_type)
    restored = from_api_question_type(
        api.question_type,
        allow_na=api.allow_na,
        max_score=api.max_score,
        max_value=api.max_value,
    )
    assert restored == fe_type


# API types that appear in the palette forward map → canonical FE type.
_API_TO_FE_CASES: list[tuple[str, dict[str, object], str]] = [
    ("yes_no", {}, "yes_no"),
    ("yes_no", {"allow_na": True}, "yes_no_na"),
    ("pass_fail", {}, "pass_fail"),
    ("rating", {"max_score": 5.0}, "scale_1_5"),
    ("rating", {"max_score": 10.0}, "scale_1_10"),
    ("rating", {"max_value": 5.0}, "scale_1_5"),
    ("rating", {"max_value": 10.0}, "scale_1_10"),
    ("rating", {}, "scale_1_5"),
    ("radio", {}, "multi_choice"),
    ("checkbox", {}, "checklist"),
    ("text", {}, "text_short"),
    ("textarea", {}, "text_long"),
    ("number", {}, "numeric"),
    ("date", {}, "date"),
    ("photo", {}, "photo"),
    ("signature", {}, "signature"),
    ("user_select", {}, "user_select"),
    ("location_select", {}, "location_select"),
    ("customer_select", {}, "customer_select"),
]


@pytest.mark.parametrize(("api_type", "kwargs", "expected_fe"), _API_TO_FE_CASES)
def test_from_api_question_type_for_palette_api_types(
    api_type: str, kwargs: dict[str, object], expected_fe: str
) -> None:
    allow_na = bool(kwargs.get("allow_na", False))
    max_score = kwargs.get("max_score")
    max_value = kwargs.get("max_value")
    assert (
        from_api_question_type(
            api_type,
            allow_na=allow_na,
            max_score=float(max_score) if isinstance(max_score, (int, float)) else None,
            max_value=float(max_value) if isinstance(max_value, (int, float)) else None,
        )
        == expected_fe
    )


def test_palette_api_types_covered_by_reverse_cases() -> None:
    covered = {case[0] for case in _API_TO_FE_CASES}
    assert covered == PALETTE_API_TYPES


def test_api_allowlist_matches_schema_pattern() -> None:
    assert API_QUESTION_TYPES == frozenset(
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


def test_fe_builder_types_match_palette_order() -> None:
    assert FE_BUILDER_QUESTION_TYPES == frozenset(FE_PALETTE_ORDER)


def test_to_api_rejects_unknown_fe_type() -> None:
    with pytest.raises(ValueError, match="Unknown frontend builder question type"):
        to_api_question_type("not_a_real_type")


@pytest.mark.parametrize(
    ("api_type", "kwargs", "expected_fe"),
    [
        ("datetime", {}, "date"),
        ("dropdown", {}, "multi_choice"),
        ("file", {}, "text_short"),
        ("score", {"max_score": 10.0}, "scale_1_10"),
        ("score", {"max_score": 3.0}, "scale_1_5"),
        ("unknown_custom", {}, "text_short"),
    ],
)
def test_from_api_documented_unavoidable_collapses(api_type: str, kwargs: dict[str, object], expected_fe: str) -> None:
    allow_na = bool(kwargs.get("allow_na", False))
    max_score = kwargs.get("max_score")
    max_value = kwargs.get("max_value")
    assert (
        from_api_question_type(
            api_type,
            allow_na=allow_na,
            max_score=float(max_score) if isinstance(max_score, (int, float)) else None,
            max_value=float(max_value) if isinstance(max_value, (int, float)) else None,
        )
        == expected_fe
    )
