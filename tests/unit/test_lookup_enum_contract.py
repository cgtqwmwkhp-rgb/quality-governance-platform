"""Unit coverage for the enum-backed lookup registry and admin write guard."""

from __future__ import annotations

import pytest

from src.domain.exceptions import ValidationError
from src.domain.services.lookup_enum_contract import ENUM_BACKED_CATEGORIES, ensure_enum_backed_code, rejected_codes


def test_free_form_categories_are_unconstrained() -> None:
    ensure_enum_backed_code("customers", "anything_goes")
    assert rejected_codes("customers", ["anything_goes"]) == ()


def test_enum_member_is_accepted() -> None:
    ensure_enum_backed_code("complaint_types", "service")
    ensure_enum_backed_code("incident_types", "injury")


def test_rogue_code_is_rejected_with_allowed_list() -> None:
    with pytest.raises(ValidationError, match="workmanship") as exc_info:
        ensure_enum_backed_code("complaint_types", "workmanship")
    assert exc_info.value.details["category"] == "complaint_types"
    assert "service" in exc_info.value.details["allowed"]


def test_rejection_is_case_insensitive() -> None:
    ensure_enum_backed_code("complaint_types", "SERVICE")
    with pytest.raises(ValidationError):
        ensure_enum_backed_code("incident_types", "ILL_HEALTH")


def test_registered_categories_are_the_1_to_1_pairings() -> None:
    assert set(ENUM_BACKED_CATEGORIES) == {"complaint_types", "incident_types"}
