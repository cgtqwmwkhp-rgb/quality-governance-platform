"""Unit tests for the dual-shape investigation JSON writer (INV-C4).

The workspace writes flat keys; the closure walk and the pack read ``data.sections``. These
tests pin the merge that keeps both shapes agreeing without inventing or destroying a value.
"""

from __future__ import annotations

import copy

from src.domain.services.investigation_data_reader import (
    read_investigation_field,
    read_investigation_section_field,
)
from src.domain.services.investigation_data_writer import (
    WORKSPACE_FIELD_SECTIONS,
    merge_nested_workspace_fields,
)

FINDINGS_SECTION = "section_3_investigation_findings"
ROOT_CAUSE_SECTION = "section_4_root_cause"
LEGACY_RCA_SECTION = "rca"


class TestFlatToNested:
    def test_workspace_findings_land_in_the_findings_section(self) -> None:
        merged = merge_nested_workspace_fields(
            {"findings": "operator stepped behind the reversing loader", "conclusion": "no segregation"}
        )

        section = merged["sections"][FINDINGS_SECTION]
        assert section["findings"] == "operator stepped behind the reversing loader"
        assert section["conclusion"] == "no segregation"

    def test_lead_investigator_lands_in_the_findings_section(self) -> None:
        merged = merge_nested_workspace_fields({"lead_investigator": "ada@example.com"})

        assert merged["sections"][FINDINGS_SECTION]["lead_investigator"] == "ada@example.com"

    def test_rca_fields_land_in_both_the_contract_section_and_the_legacy_alias(self) -> None:
        merged = merge_nested_workspace_fields(
            {
                "problem_statement": "loader reversed into the walkway",
                "root_cause": "no banksman on site",
                "contributing_factors": "poor lighting",
                "why_1": "the driver could not see",
                "why_5": "the traffic plan was never reviewed",
            }
        )

        for section_key in (ROOT_CAUSE_SECTION, LEGACY_RCA_SECTION):
            section = merged["sections"][section_key]
            assert section["problem_statement"] == "loader reversed into the walkway"
            assert section["root_cause"] == "no banksman on site"
            assert section["contributing_factors"] == "poor lighting"
            assert section["why_1"] == "the driver could not see"
            assert section["why_5"] == "the traffic plan was never reviewed"

    def test_every_mapped_field_is_readable_by_the_c3_section_reader_after_a_merge(self) -> None:
        flat = {field: f"value for {field}" for field in WORKSPACE_FIELD_SECTIONS}

        merged = merge_nested_workspace_fields(flat)

        for field, target_sections in WORKSPACE_FIELD_SECTIONS.items():
            for section_key in target_sections:
                assert read_investigation_section_field(merged, section_key, field) == f"value for {field}"

    def test_the_walk_the_closure_gate_uses_can_see_the_workspace_findings(self) -> None:
        from src.domain.services.investigation_structure_normalize import iter_run_section_values

        merged = merge_nested_workspace_fields({"findings": "guard was removed"})

        assert (FINDINGS_SECTION, "findings", "guard was removed") in list(iter_run_section_values(merged))


class TestNestedToFlat:
    def test_a_nested_finding_is_copied_onto_the_missing_flat_key(self) -> None:
        merged = merge_nested_workspace_fields({"sections": {FINDINGS_SECTION: {"findings": "from the template run"}}})

        assert merged["findings"] == "from the template run"

    def test_a_nested_value_fills_an_empty_flat_key(self) -> None:
        merged = merge_nested_workspace_fields(
            {"why_1": "", "sections": {ROOT_CAUSE_SECTION: {"why_1": "the interlock was bypassed"}}}
        )

        assert merged["why_1"] == "the interlock was bypassed"

    def test_a_legacy_alias_value_reaches_the_flat_key_and_the_contract_section(self) -> None:
        merged = merge_nested_workspace_fields({"sections": {LEGACY_RCA_SECTION: {"root_cause": "no traffic plan"}}})

        assert merged["root_cause"] == "no traffic plan"
        assert merged["sections"][ROOT_CAUSE_SECTION]["root_cause"] == "no traffic plan"
        assert merged["sections"][LEGACY_RCA_SECTION]["root_cause"] == "no traffic plan"


class TestConflicts:
    def test_nested_wins_when_both_shapes_hold_content(self) -> None:
        merged = merge_nested_workspace_fields(
            {"findings": "flat leftover", "sections": {FINDINGS_SECTION: {"findings": "nested finding"}}}
        )

        assert merged["findings"] == "flat leftover"
        assert merged["sections"][FINDINGS_SECTION]["findings"] == "nested finding"
        # The C3 reader is the arbiter, and it still prefers the nested value.
        assert read_investigation_field(merged, "findings") == "nested finding"

    def test_a_second_nested_value_is_never_overwritten_by_the_first(self) -> None:
        merged = merge_nested_workspace_fields(
            {
                "sections": {
                    ROOT_CAUSE_SECTION: {"root_cause": "contract section value"},
                    LEGACY_RCA_SECTION: {"root_cause": "legacy alias value"},
                }
            }
        )

        assert merged["sections"][ROOT_CAUSE_SECTION]["root_cause"] == "contract section value"
        assert merged["sections"][LEGACY_RCA_SECTION]["root_cause"] == "legacy alias value"
        assert merged["root_cause"] == "contract section value"

    def test_content_beats_an_empty_string_in_either_direction(self) -> None:
        from_flat = merge_nested_workspace_fields(
            {"conclusion": "unsafe system of work", "sections": {FINDINGS_SECTION: {"conclusion": ""}}}
        )
        assert from_flat["sections"][FINDINGS_SECTION]["conclusion"] == "unsafe system of work"

        from_nested = merge_nested_workspace_fields(
            {"conclusion": "   ", "sections": {FINDINGS_SECTION: {"conclusion": "unsafe system of work"}}}
        )
        assert from_nested["conclusion"] == "unsafe system of work"


class TestNothingIsInvented:
    def test_an_empty_string_on_both_sides_stays_empty_and_creates_no_section(self) -> None:
        merged = merge_nested_workspace_fields({"findings": "", "conclusion": None})

        assert merged["findings"] == ""
        assert merged["conclusion"] is None
        assert "sections" not in merged

    def test_a_blob_with_no_workspace_fields_is_returned_unchanged(self) -> None:
        payload = {"source_snapshot": {"reference_number": "NM-1"}, "mapping_log": [{"result": "SUCCESS"}]}

        assert merge_nested_workspace_fields(copy.deepcopy(payload)) == payload

    def test_unrelated_keys_and_sections_are_preserved(self) -> None:
        payload = {
            "findings": "guard missing",
            "source_snapshot": {"reference_number": "NM-1"},
            "customer_pack_visibility": {"section_1_details": {"omit_requested": True}},
            "mapping_log": [{"source_field": "description", "result": "SUCCESS"}],
            "sections": {
                "section_1_details": {"description": "loader reversed"},
                "addendum_rta": {"road_name": "A5"},
            },
        }

        merged = merge_nested_workspace_fields(payload)

        assert merged["source_snapshot"] == {"reference_number": "NM-1"}
        assert merged["customer_pack_visibility"] == {"section_1_details": {"omit_requested": True}}
        assert merged["mapping_log"] == [{"source_field": "description", "result": "SUCCESS"}]
        assert merged["sections"]["section_1_details"] == {"description": "loader reversed"}
        assert merged["sections"]["addendum_rta"] == {"road_name": "A5"}
        assert merged["sections"][FINDINGS_SECTION] == {"findings": "guard missing"}

    def test_the_input_payload_is_not_mutated(self) -> None:
        payload = {"findings": "guard missing", "sections": {"section_1_details": {"description": "loader reversed"}}}
        before = copy.deepcopy(payload)

        merge_nested_workspace_fields(payload)

        assert payload == before

    def test_a_non_dict_payload_is_returned_unchanged(self) -> None:
        assert merge_nested_workspace_fields(None) is None
        assert merge_nested_workspace_fields("not-a-dict") == "not-a-dict"
        assert merge_nested_workspace_fields([1, 2]) == [1, 2]

    def test_an_empty_array_field_keeps_its_type_instead_of_taking_the_text(self) -> None:
        merged = merge_nested_workspace_fields(
            {"contributing_factors": "poor lighting", "sections": {ROOT_CAUSE_SECTION: {"contributing_factors": []}}}
        )

        assert merged["sections"][ROOT_CAUSE_SECTION]["contributing_factors"] == []
        assert merged["contributing_factors"] == "poor lighting"

    def test_a_malformed_sections_payload_is_left_alone(self) -> None:
        assert merge_nested_workspace_fields({"findings": "x", "sections": "broken"}) == {
            "findings": "x",
            "sections": "broken",
        }

        merged = merge_nested_workspace_fields({"findings": "x", "sections": {FINDINGS_SECTION: "broken"}})
        assert merged["sections"][FINDINGS_SECTION] == "broken"


class TestIdempotence:
    def test_merging_twice_changes_nothing_the_second_time(self) -> None:
        once = merge_nested_workspace_fields(
            {
                "findings": "guard missing",
                "why_1": "",
                "sections": {ROOT_CAUSE_SECTION: {"why_1": "the interlock was bypassed"}},
            }
        )

        twice = merge_nested_workspace_fields(copy.deepcopy(once))

        assert twice == once

    def test_merging_an_already_merged_blob_is_stable_for_every_mapped_field(self) -> None:
        once = merge_nested_workspace_fields({field: f"value for {field}" for field in WORKSPACE_FIELD_SECTIONS})

        assert merge_nested_workspace_fields(copy.deepcopy(once)) == once


class TestListShapedSections:
    def test_a_flat_key_merges_into_the_matching_list_entry(self) -> None:
        merged = merge_nested_workspace_fields(
            {
                "findings": "guard missing",
                "sections": [
                    {"id": "section_1_details", "fields": {"description": "loader reversed"}},
                    {"id": FINDINGS_SECTION, "fields": {"what_happened": "reversing manoeuvre"}},
                ],
            }
        )

        assert isinstance(merged["sections"], list)
        entry = next(item for item in merged["sections"] if item["id"] == FINDINGS_SECTION)
        assert entry["fields"] == {"what_happened": "reversing manoeuvre", "findings": "guard missing"}
        assert merged["sections"][0]["fields"] == {"description": "loader reversed"}

    def test_a_missing_section_is_appended_and_the_list_shape_is_kept(self) -> None:
        merged = merge_nested_workspace_fields(
            {"findings": "guard missing", "sections": [{"id": "section_1_details", "fields": {"location": "yard"}}]}
        )

        assert [entry["id"] for entry in merged["sections"]] == ["section_1_details", FINDINGS_SECTION]
        assert merged["sections"][1]["fields"] == {"findings": "guard missing"}

    def test_an_inline_list_entry_is_read_and_written_in_place(self) -> None:
        merged = merge_nested_workspace_fields(
            {"sections": [{"id": FINDINGS_SECTION, "findings": "from the run", "conclusion": ""}]}
        )

        assert merged["findings"] == "from the run"
        assert merged["sections"][0]["findings"] == "from the run"
        assert merged["sections"][0]["conclusion"] == ""

    def test_a_nested_list_value_is_copied_onto_the_flat_key(self) -> None:
        merged = merge_nested_workspace_fields(
            {"sections": [{"section_id": ROOT_CAUSE_SECTION, "fields": {"root_cause": "no traffic plan"}}]}
        )

        assert merged["root_cause"] == "no traffic plan"
        assert read_investigation_field(merged, "root_cause") == "no traffic plan"

    def test_malformed_list_entries_are_skipped_without_raising(self) -> None:
        merged = merge_nested_workspace_fields({"findings": "guard missing", "sections": ["broken", 7, None]})

        assert merged["sections"][:3] == ["broken", 7, None]
        assert merged["sections"][3] == {"id": FINDINGS_SECTION, "fields": {"findings": "guard missing"}}
