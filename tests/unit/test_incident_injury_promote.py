"""Unit tests for portal injury field promotion."""

from src.domain.services.incident_injury_promote import (
    extract_body_parts_from_injuries,
    promote_injury_fields_from_submission,
)


def test_extract_body_parts_from_region_dicts() -> None:
    injuries = [
        {"regions": [{"id": "head-front"}, {"id": "left-hand"}]},
        {"body_part": "Legs"},
    ]
    assert extract_body_parts_from_injuries(injuries) == ["head-front", "left-hand", "Legs"]


def test_promote_injury_from_has_injuries_flag() -> None:
    result = promote_injury_fields_from_submission({"has_injuries": True, "injuries": []})
    assert result["is_injury"] is True
    assert result["body_parts"] is None


def test_promote_injury_from_body_map() -> None:
    result = promote_injury_fields_from_submission(
        {"injuries": [{"id": "cut", "regions": [{"id": "right-hand"}]}]}
    )
    assert result["is_injury"] is True
    assert result["body_parts"] == ["cut", "right-hand"]


def test_promote_no_injury() -> None:
    result = promote_injury_fields_from_submission({"medical_assistance": "none"})
    assert result["is_injury"] is False
    assert result["body_parts"] is None
