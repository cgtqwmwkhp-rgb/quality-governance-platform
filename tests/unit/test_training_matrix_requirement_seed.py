"""Unit tests for Plantexpand 2024 requirement seed template matching."""

from types import SimpleNamespace

from src.domain.services.training_matrix_requirement_seed import match_module_to_course
from src.domain.training_matrix.plantexpand_matrix_2024 import PLANTEXPAND_MATRIX_2024, TEMPLATE_ID, expand_seed_rows


def test_expand_seed_rows_covers_all_role_marks():
    rows = expand_seed_rows()
    expected = sum(len(m["roles"]) for m in PLANTEXPAND_MATRIX_2024)
    assert len(rows) == expected
    assert expected >= 80
    assert all(r["template_id"] == TEMPLATE_ID for r in rows)
    asbestos = [r for r in rows if r["module"] == "Asbestos Awareness"]
    assert {r["match_department"] for r in asbestos} == {"Engineer", "Workshop"}
    assert asbestos[0]["frequency_years"] == 1


def test_match_module_prefers_atlas_course():
    courses = [
        SimpleNamespace(course_key="asbestos_awareness", display_name="Asbestos Awareness"),
        SimpleNamespace(course_key="gdpr", display_name="GDPR"),
    ]
    hit = match_module_to_course("Asbestos Awareness", courses)
    assert hit.matched_atlas is True
    assert hit.course_key == "asbestos_awareness"


def test_match_module_alias_hand_hygiene():
    courses = [
        SimpleNamespace(course_key="hand_hygeine", display_name="Hand Hygeine"),
    ]
    hit = match_module_to_course("Hand Hygiene", courses)
    assert hit.matched_atlas is True
    assert hit.course_key == "hand_hygeine"


def test_match_module_fallback_normalized_key():
    hit = match_module_to_course("Brand New Course XYZ", [])
    assert hit.matched_atlas is False
    assert hit.course_key == "brand_new_course_xyz"
    assert hit.display_name == "Brand New Course XYZ"
