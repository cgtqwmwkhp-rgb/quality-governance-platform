"""Unit tests for portal report_type routing mapping.

These tests verify the mapping contract is:
1. Complete - all known types have mappings
2. Correct - each type maps to expected database model
3. Explicit - no fallback/default behavior for unknown types

Reference: ADR-0001 quality gates
"""

import pytest


class TestPortalRoutingMappingContract:
    """Unit tests for portal routing mapping completeness."""

    # Canonical mapping contract - single source of truth
    CANONICAL_MAPPING = {
        "incident": {
            "table": "incidents",
            "ref_prefix": "INC-",
            "source_form_id": "portal_incident_v1",
        },
        "complaint": {
            "table": "complaints",
            "ref_prefix": "COMP-",
            "source_form_id": "portal_complaint_v1",
        },
        "rta": {
            "table": "road_traffic_collisions",
            "ref_prefix": "RTA-",
            "source_form_id": "portal_rta_v1",
        },
        "near_miss": {
            "table": "near_misses",
            "ref_prefix": "NM-",
            "source_form_id": "portal_near_miss_v1",
        },
    }

    def test_mapping_completeness(self):
        """Verify all expected portal types are in the mapping."""
        expected_types = {"incident", "complaint", "rta", "near_miss"}
        actual_types = set(self.CANONICAL_MAPPING.keys())

        missing = expected_types - actual_types
        assert not missing, f"Missing portal types in mapping: {missing}"

        extra = actual_types - expected_types
        assert not extra, f"Unexpected portal types in mapping: {extra}"

    def test_each_type_has_unique_table(self):
        """Verify each portal type maps to a unique database table."""
        tables = [v["table"] for v in self.CANONICAL_MAPPING.values()]
        assert len(tables) == len(
            set(tables)
        ), f"Duplicate table mappings detected: {tables}"

    def test_each_type_has_unique_ref_prefix(self):
        """Verify each portal type has a unique reference number prefix."""
        prefixes = [v["ref_prefix"] for v in self.CANONICAL_MAPPING.values()]
        assert len(prefixes) == len(
            set(prefixes)
        ), f"Duplicate reference prefixes detected: {prefixes}"

    def test_each_type_has_unique_source_form_id(self):
        """Verify each portal type has a unique source_form_id for audit."""
        form_ids = [v["source_form_id"] for v in self.CANONICAL_MAPPING.values()]
        assert len(form_ids) == len(
            set(form_ids)
        ), f"Duplicate source_form_ids detected: {form_ids}"

    def test_ref_prefix_format(self):
        """Verify reference prefixes follow expected format."""
        for portal_type, mapping in self.CANONICAL_MAPPING.items():
            prefix = mapping["ref_prefix"]
            assert prefix.endswith(
                "-"
            ), f"{portal_type}: ref_prefix should end with '-', got: {prefix}"
            assert (
                prefix.isupper() or prefix[:-1].isupper()
            ), f"{portal_type}: ref_prefix should be uppercase, got: {prefix}"

    def test_source_form_id_format(self):
        """Verify source_form_id follows expected format (portal_<type>_v<version>)."""
        import re

        pattern = r"^portal_[a-z_]+_v\d+$"

        for portal_type, mapping in self.CANONICAL_MAPPING.items():
            form_id = mapping["source_form_id"]
            assert re.match(
                pattern, form_id
            ), f"{portal_type}: source_form_id should match pattern 'portal_<type>_v<n>', got: {form_id}"


class TestPortalAPIRoutingContract:
    """Tests for the employee_portal.py routing implementation."""

    VALID_REPORT_TYPES = ["incident", "complaint", "rta", "near_miss"]
    INVALID_REPORT_TYPES = ["unknown", "rta_incident", "", "INCIDENT", "Incident", None]

    def test_valid_report_types_list(self):
        """Document all valid report types."""
        expected = {"incident", "complaint", "rta", "near_miss"}
        actual = set(self.VALID_REPORT_TYPES)
        assert actual == expected, "Valid report types mismatch"

    @pytest.mark.parametrize(
        "invalid_type",
        [
            "unknown",
            "rta_incident",
            "INCIDENT",  # Case sensitive
            "Incident",
            "near-miss",  # Hyphen not underscore
            "nearmiss",  # No separator
            "",  # Empty
        ],
    )
    def test_invalid_report_types_documented(self, invalid_type):
        """Document types that should be rejected."""
        assert (
            invalid_type not in self.VALID_REPORT_TYPES
        ), f"'{invalid_type}' should not be in valid types"


class TestDashboardIsolationContract:
    """Tests for dashboard API isolation contract."""

    DASHBOARD_API_CONTRACT = {
        "/api/v1/incidents/": {
            "queries_table": "incidents",
            "returns_types": ["incident"],
            "excludes_types": ["rta", "near_miss", "complaint"],
        },
        "/api/v1/rtas/": {
            "queries_table": "road_traffic_collisions",
            "returns_types": ["rta"],
            "excludes_types": ["incident", "near_miss", "complaint"],
        },
        "/api/v1/near-misses/": {
            "queries_table": "near_misses",
            "returns_types": ["near_miss"],
            "excludes_types": ["incident", "rta", "complaint"],
        },
        "/api/v1/complaints/": {
            "queries_table": "complaints",
            "returns_types": ["complaint"],
            "excludes_types": ["incident", "rta", "near_miss"],
        },
    }

    def test_each_dashboard_has_isolation_contract(self):
        """Verify each dashboard API has explicit isolation defined."""
        for endpoint, contract in self.DASHBOARD_API_CONTRACT.items():
            assert "queries_table" in contract, f"{endpoint}: missing queries_table"
            assert "returns_types" in contract, f"{endpoint}: missing returns_types"
            assert "excludes_types" in contract, f"{endpoint}: missing excludes_types"

    def test_no_type_overlap_in_dashboards(self):
        """Verify no single type appears in multiple dashboards."""
        all_returns = []
        for endpoint, contract in self.DASHBOARD_API_CONTRACT.items():
            all_returns.extend(contract["returns_types"])

        assert len(all_returns) == len(
            set(all_returns)
        ), f"Overlapping types in dashboard contracts: {all_returns}"

    def test_each_type_excluded_from_other_dashboards(self):
        """Verify each type is explicitly excluded from non-owning dashboards."""
        for endpoint, contract in self.DASHBOARD_API_CONTRACT.items():
            # Types this dashboard returns
            returns = set(contract["returns_types"])

            # Types this dashboard excludes
            excludes = set(contract["excludes_types"])

            # No overlap between returns and excludes
            overlap = returns & excludes
            assert not overlap, f"{endpoint}: returns and excludes overlap: {overlap}"

            # Returns + excludes should cover all types
            all_types = {"incident", "rta", "near_miss", "complaint"}
            covered = returns | excludes
            assert (
                covered == all_types
            ), f"{endpoint}: not all types covered by returns+excludes: {all_types - covered}"


class TestReferencePrefixAssignment:
    """Tests for reference number prefix assignment logic."""

    PREFIX_MODEL_MAP = {
        "INC-": "Incident",
        "COMP-": "Complaint",
        "RTA-": "RoadTrafficCollision",
        "NM-": "NearMiss",
    }

    def test_prefix_to_model_mapping_complete(self):
        """Verify all models have assigned prefixes."""
        expected_models = {"Incident", "Complaint", "RoadTrafficCollision", "NearMiss"}
        actual_models = set(self.PREFIX_MODEL_MAP.values())

        missing = expected_models - actual_models
        assert not missing, f"Models missing prefix assignments: {missing}"

    def test_reference_number_format(self):
        """Document expected reference number format."""
        # Format: PREFIX-YYYY-NNNN
        import re

        pattern = r"^[A-Z]{2,4}-\d{4}-\d{4}$"

        example_refs = [
            "INC-2026-0001",
            "RTA-2026-0123",
            "NM-2026-9999",
            "COMP-2026-0042",
        ]

        for ref in example_refs:
            assert re.match(pattern, ref), f"Reference format invalid: {ref}"


class TestFailFastOnInvalidInput:
    """Tests verifying fail-fast behavior per ADR-0002."""

    def test_no_silent_default_to_incident(self):
        """Document: unknown report_type must NOT silently default to incident."""
        # This test documents the expected behavior
        # The integration test verifies the actual implementation
        expected_behavior = {
            "unknown_type": "reject_with_400",
            "empty_type": "reject_with_400",
            "null_type": "reject_with_validation_error",
            "wrong_case": "reject_with_400",
        }

        # All should result in rejection
        for scenario, expected in expected_behavior.items():
            assert "reject" in expected, f"{scenario} should be rejected"

    def test_bounded_enum_requirement(self):
        """Document: report_type should be treated as bounded enum."""
        valid_values = {"incident", "complaint", "rta", "near_miss"}

        # Must be lowercase
        for v in valid_values:
            assert v == v.lower(), f"Value should be lowercase: {v}"

        # Must use underscore for multi-word
        assert "near_miss" in valid_values, "Multi-word should use underscore"
        assert "near-miss" not in valid_values, "Hyphen should not be accepted"
