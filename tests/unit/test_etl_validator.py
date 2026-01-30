"""
Unit Tests for ETL Validator - Quality Governance Platform
Stage 10: Data Foundation
"""

import pytest

from scripts.etl.config import INCIDENT_MAPPINGS, EntityType
from scripts.etl.validator import ValidationResult, ValidationSeverity, validate_record, validate_records


class TestValidateRecord:
    """Tests for single record validation."""

    def test_valid_record_passes(self):
        """Valid record should pass validation."""
        record = {
            "external_ref": "TEST-001",
            "title": "Test Incident",
            "incident_date": "2026-01-15",
        }
        result = validate_record(record, INCIDENT_MAPPINGS, row_number=1)

        assert result.is_valid
        assert result.error_count == 0

    def test_missing_required_field_fails(self):
        """Missing required field should fail validation."""
        record = {
            "external_ref": "TEST-001",
            # Missing title and incident_date
        }
        result = validate_record(record, INCIDENT_MAPPINGS, row_number=1)

        assert not result.is_valid
        assert result.error_count >= 1

    def test_empty_required_field_fails(self):
        """Empty required field should fail validation."""
        record = {
            "external_ref": "",  # Empty
            "title": "Test",
            "incident_date": "2026-01-15",
        }
        result = validate_record(record, INCIDENT_MAPPINGS, row_number=1)

        assert not result.is_valid

    def test_title_length_warning(self):
        """Long title should trigger warning."""
        record = {
            "external_ref": "TEST-001",
            "title": "x" * 350,  # Exceeds 300 chars
            "incident_date": "2026-01-15",
        }
        result = validate_record(record, INCIDENT_MAPPINGS, row_number=1)

        # Should have warning but still valid
        warnings = [i for i in result.issues if i.severity == ValidationSeverity.WARNING]
        assert len(warnings) >= 1


class TestValidateRecords:
    """Tests for batch validation."""

    def test_batch_validation_counts(self):
        """Batch validation should count valid/invalid correctly."""
        records = [
            {"external_ref": "TEST-001", "title": "Valid", "incident_date": "2026-01-15"},
            {"external_ref": "TEST-002", "title": "Also Valid", "incident_date": "2026-01-16"},
            {"external_ref": "", "title": "", "incident_date": ""},  # Invalid
        ]

        report = validate_records(records, INCIDENT_MAPPINGS, EntityType.INCIDENT, "test.csv")

        assert report.total_records == 3
        assert report.valid_records == 2
        assert report.invalid_records == 1

    def test_validation_report_serializable(self):
        """Validation report should be JSON serializable."""
        records = [
            {"external_ref": "TEST-001", "title": "Test", "incident_date": "2026-01-15"},
        ]

        report = validate_records(records, INCIDENT_MAPPINGS, EntityType.INCIDENT, "test.csv")
        result_dict = report.to_dict()

        assert "summary" in result_dict
        assert "entity_type" in result_dict
        assert result_dict["summary"]["total_records"] == 1
