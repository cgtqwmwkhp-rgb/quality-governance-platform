"""Unit tests for investigation template/run structure normalization (W2 spine)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.domain.services.investigation_structure_normalize import (
    iter_run_section_values,
    parse_structure_json,
    run_values_to_data_json,
    structure_specs_to_json,
)

SAMPLE_STRUCTURE = {
    "sections": [
        {
            "id": "rca",
            "name": "Root Cause Analysis",
            "fields": [
                {
                    "id": "problem_statement",
                    "label": "Problem",
                    "type": "text",
                    "question_type": "text",
                    "required": True,
                },
                {
                    "id": "score",
                    "label": "Score",
                    "type": "score_0_5",
                    "question_type": "score_0_5",
                    "required": False,
                    "max_score": 5,
                    "max_value": 5,
                },
            ],
        }
    ]
}


def test_parse_structure_json_extracts_sections_and_fields():
    specs = parse_structure_json(SAMPLE_STRUCTURE)
    assert len(specs) == 1
    assert specs[0].section_key == "rca"
    assert specs[0].title == "Root Cause Analysis"
    assert len(specs[0].fields) == 2
    assert specs[0].fields[0].field_key == "problem_statement"
    assert specs[0].fields[0].required is True
    assert specs[0].fields[1].field_type == "score_0_5"
    assert specs[0].fields[1].config_json["max_score"] == 5
    assert specs[0].fields[1].config_json["max_value"] == 5


def test_structure_specs_round_trip_preserves_builder_shape():
    specs = parse_structure_json(SAMPLE_STRUCTURE)
    rebuilt = structure_specs_to_json(specs)
    assert rebuilt["sections"][0]["id"] == "rca"
    assert rebuilt["sections"][0]["name"] == "Root Cause Analysis"
    assert rebuilt["sections"][0]["fields"][0]["question_type"] == "text"
    assert rebuilt["sections"][0]["fields"][1]["max_score"] == 5


def test_iter_run_section_values_supports_wrapped_sections():
    data = {"sections": {"rca": {"problem_statement": "Oil leak", "score": 4}}}
    values = list(iter_run_section_values(data))
    assert values == [("rca", "problem_statement", "Oil leak"), ("rca", "score", 4)]


def test_iter_run_section_values_supports_flat_legacy_shape():
    data = {"rca": {"problem_statement": "Oil leak"}}
    values = list(iter_run_section_values(data))
    assert values == [("rca", "problem_statement", "Oil leak")]


def test_run_values_to_data_json_wraps_sections_by_default():
    payload = run_values_to_data_json([("rca", "problem_statement", "Oil leak")])
    assert payload == {"sections": {"rca": {"problem_statement": "Oil leak"}}}


def test_run_values_to_data_json_can_emit_flat_shape():
    payload = run_values_to_data_json(
        [("rca", "problem_statement", "Oil leak")],
        wrap_sections=False,
    )
    assert payload == {"rca": {"problem_statement": "Oil leak"}}


def test_parse_structure_json_tolerates_empty_or_invalid_input():
    assert parse_structure_json(None) == []
    assert parse_structure_json({}) == []
    specs = parse_structure_json({"sections": [None, {"fields": []}]})
    assert len(specs) == 1
    assert specs[0].section_key == "section_1"
    assert specs[0].display_order == 1


def test_investigation_service_exposes_dual_write_helpers():
    from src.domain.services.investigation_service import InvestigationService

    assert hasattr(InvestigationService, "dual_write_template_structure")
    assert hasattr(InvestigationService, "dual_write_run_responses")
    assert hasattr(InvestigationService, "dual_read_template_structure")
    assert hasattr(InvestigationService, "dual_read_run_data")
