"""Unit tests for the dual-shape investigation JSON reader."""

from __future__ import annotations

from src.domain.services.investigation_data_reader import (
    read_investigation_field,
    read_investigation_section_field,
)


class TestReadInvestigationField:
    def test_prefers_the_nested_section_value_when_both_shapes_exist(self) -> None:
        data = {
            "findings": "flat leftover",
            "sections": {"section_3_investigation_findings": {"findings": "nested finding"}},
        }

        assert read_investigation_field(data, "findings") == "nested finding"

    def test_reads_a_flat_key_when_sections_are_absent(self) -> None:
        assert read_investigation_field({"why_1": "because"}, "why_1") == "because"

    def test_reads_from_a_list_shaped_sections_payload(self) -> None:
        data = {
            "sections": [
                {"id": "section_1_details", "fields": {"description": "from-record"}},
            ]
        }

        assert read_investigation_field(data, "description") == "from-record"

    def test_returns_none_for_missing_or_malformed_payloads(self) -> None:
        assert read_investigation_field(None, "findings") is None
        assert read_investigation_field("not-a-dict", "findings") is None
        assert read_investigation_field({}, "findings") is None
        assert read_investigation_field({"sections": {}}, "") is None

    def test_empty_string_is_not_converted_to_none(self) -> None:
        assert read_investigation_field({"conclusion": ""}, "conclusion") == ""


class TestReadInvestigationSectionField:
    def test_reads_the_named_section_even_when_another_section_has_the_same_key(self) -> None:
        data = {
            "sections": {
                "section_1_details": {"description": "incident"},
                "section_3_investigation_findings": {"description": "investigation"},
            }
        }

        assert (
            read_investigation_section_field(data, "section_3_investigation_findings", "description")
            == "investigation"
        )

    def test_falls_back_to_the_flat_key_when_the_section_is_missing(self) -> None:
        assert read_investigation_section_field({"lead_investigator": "Ada"}, "summary", "lead_investigator") == "Ada"
