"""Unit tests for portal injury field promotion."""

import pytest

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


def test_extract_body_parts_from_portal_injury_selection() -> None:
    injuries = [
        {
            "regionId": "left-hand",
            "regionLabel": "Left hand",
            "injuryType": "cut",
            "injuryLabel": "Cut / laceration",
            "view": "front",
        }
    ]
    assert extract_body_parts_from_injuries(injuries) == ["Left hand"]


def test_promote_injury_from_has_injuries_flag() -> None:
    result = promote_injury_fields_from_submission({"has_injuries": True, "injuries": []})
    assert result["is_injury"] is True
    assert result["body_parts"] is None


def test_promote_injury_from_body_map() -> None:
    result = promote_injury_fields_from_submission({"injuries": [{"id": "cut", "regions": [{"id": "right-hand"}]}]})
    assert result["is_injury"] is True
    assert result["body_parts"] == ["cut", "right-hand"]


def test_promote_no_injury() -> None:
    result = promote_injury_fields_from_submission({"medical_assistance": "none"})
    assert result["is_injury"] is False
    assert result["body_parts"] is None


# The payload below is copied from INC-2026-0049, submitted through the staging
# employee portal on 28/07/2026 answering "No" to "Any injuries sustained?".
# The portal sends the answer as a string, which is why bool() got it backwards.
PORTAL_SUBMISSION_ANSWERED_NO = {
    "contract": "ukpn",
    "location": "UKPN Depot, Bury St Edmunds - Bay 3",
    "description": "Hydraulic hose coupling failed during a pre-start check.",
    "person_name": "UX Employee",
    "person_role": "mobile-engineer",
    "has_injuries": "no",
    "was_involved": "yes",
    "has_witnesses": "no",
    "incident_date": "2026-07-28",
    "incident_time": "20:41",
}


def test_portal_answer_no_is_not_an_injury() -> None:
    result = promote_injury_fields_from_submission(PORTAL_SUBMISSION_ANSWERED_NO)
    assert result["is_injury"] is False
    assert result["body_parts"] is None


def test_portal_answer_yes_is_an_injury() -> None:
    submission = dict(PORTAL_SUBMISSION_ANSWERED_NO, has_injuries="yes")
    assert promote_injury_fields_from_submission(submission)["is_injury"] is True


def test_answering_no_and_omitting_the_question_agree() -> None:
    """Answering "no" must not differ from never being asked."""
    answered_no = promote_injury_fields_from_submission({"has_injuries": "no"})
    never_asked = promote_injury_fields_from_submission({})
    assert answered_no["is_injury"] == never_asked["is_injury"] is False


def test_tapped_body_part_outranks_a_no_answer() -> None:
    """Recorded evidence of an injury wins over the yes/no answer."""
    submission = {"has_injuries": "no", "injuries": [{"regionLabel": "Left hand"}]}
    result = promote_injury_fields_from_submission(submission)
    assert result["is_injury"] is True
    assert result["body_parts"] == ["Left hand"]


@pytest.mark.parametrize("answer", ["no", "No", "NO", " no ", "false", "0", "n"])
def test_negative_answer_spellings(answer: str) -> None:
    assert promote_injury_fields_from_submission({"has_injuries": answer})["is_injury"] is False


@pytest.mark.parametrize("answer", ["yes", "Yes", "YES", " yes ", "true", "1", "y"])
def test_affirmative_answer_spellings(answer: str) -> None:
    assert promote_injury_fields_from_submission({"has_injuries": answer})["is_injury"] is True


def test_unrecognised_answer_is_treated_as_an_injury() -> None:
    """An answer nobody anticipated must not quietly downgrade an injury."""
    assert promote_injury_fields_from_submission({"has_injuries": "maybe"})["is_injury"] is True


def test_real_booleans_still_honoured() -> None:
    assert promote_injury_fields_from_submission({"has_injuries": False})["is_injury"] is False
    assert promote_injury_fields_from_submission({"has_injuries": True})["is_injury"] is True
