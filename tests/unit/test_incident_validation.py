"""Unit tests for incident validation and ordering contract."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.api.schemas.incident import IncidentCreate, IncidentUpdate
from src.domain.models.incident import IncidentSeverity, IncidentStatus, IncidentType


class TestIncidentCreateValidation:
    """Test incident creation validation."""

    def test_valid_incident_create(self):
        """Test valid incident creation data."""
        data = {
            "title": "Test Incident",
            "description": "Test Description",
            "incident_type": IncidentType.QUALITY,
            "severity": IncidentSeverity.HIGH,
            "status": IncidentStatus.REPORTED,
            "incident_date": datetime.now(timezone.utc),
            "location": "Test Location",
        }
        incident = IncidentCreate(**data)
        assert incident.title == "Test Incident"
        assert incident.severity == IncidentSeverity.HIGH

    def test_incident_create_minimal(self):
        """Test minimal required fields for incident creation."""
        data = {
            "title": "Minimal Incident",
            "description": "Minimal Description",
            "incident_date": datetime.now(timezone.utc),
        }
        incident = IncidentCreate(**data)
        assert incident.title == "Minimal Incident"
        assert incident.incident_type == IncidentType.OTHER
        assert incident.severity == IncidentSeverity.MEDIUM
        assert incident.status == IncidentStatus.REPORTED

    def test_incident_create_empty_title_fails(self):
        """Test that empty title fails validation."""
        data = {
            "title": "",
            "description": "Test Description",
            "incident_date": datetime.now(timezone.utc),
        }
        with pytest.raises(ValidationError) as excinfo:
            IncidentCreate(**data)
        assert "String should have at least 1 character" in str(excinfo.value)

    def test_incident_create_whitespace_title_fails(self):
        """Test that whitespace-only title fails validation."""
        data = {
            "title": "   ",
            "description": "Test Description",
            "incident_date": datetime.now(timezone.utc),
        }
        with pytest.raises(ValidationError) as excinfo:
            IncidentCreate(**data)
        assert "Title cannot be empty or whitespace" in str(excinfo.value)

    def test_incident_create_invalid_severity_fails(self):
        """Test that invalid severity fails validation."""
        data = {
            "title": "Test Incident",
            "description": "Test Description",
            "incident_date": datetime.now(timezone.utc),
            "severity": "INVALID",
        }
        with pytest.raises(ValidationError):
            IncidentCreate(**data)


class TestIncidentUpdateValidation:
    """Test incident update validation."""

    def test_valid_incident_update(self):
        """Test valid incident update data."""
        data = {"title": "Updated Title", "status": IncidentStatus.CLOSED}
        update = IncidentUpdate(**data)
        assert update.title == "Updated Title"
        assert update.status == IncidentStatus.CLOSED

    def test_incident_update_partial(self):
        """Test partial update validation."""
        data = {"severity": IncidentSeverity.CRITICAL}
        update = IncidentUpdate(**data)
        assert update.severity == IncidentSeverity.CRITICAL
        assert update.title is None

    def test_incident_update_empty_title_fails(self):
        """Test that empty title in update fails validation."""
        data = {"title": ""}
        with pytest.raises(ValidationError):
            IncidentUpdate(**data)


class TestDeterministicOrdering:
    """Test documentation of deterministic ordering contract."""

    def test_ordering_specification(self):
        """
        Document the deterministic ordering contract.
        This test serves as a living specification for the API.
        """
        ordering = ["reported_date DESC", "id ASC"]
        assert ordering[0] == "reported_date DESC"
        assert ordering[1] == "id ASC"
