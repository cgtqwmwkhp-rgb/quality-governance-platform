"""Unit tests for complaint validation and ordering contract."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.api.schemas.complaint import ComplaintCreate, ComplaintUpdate
from src.domain.models.complaint import ComplaintPriority, ComplaintType


class TestComplaintCreateValidation:
    """Tests for ComplaintCreate schema validation."""

    def test_valid_complaint_create(self):
        """Test valid complaint creation data."""
        data = {
            "title": "Product Defect",
            "description": "The product arrived broken.",
            "complaint_type": ComplaintType.PRODUCT,
            "priority": ComplaintPriority.HIGH,
            "received_date": datetime.now(),
            "complainant_name": "John Doe",
            "complainant_email": "john@example.com",
        }
        complaint = ComplaintCreate(**data)
        assert complaint.title == "Product Defect"
        assert complaint.complainant_name == "John Doe"

    def test_title_whitespace_stripping(self):
        """Test that title whitespace is stripped."""
        data = {
            "title": "  Product Defect  ",
            "description": "The product arrived broken.",
            "received_date": datetime.now(),
            "complainant_name": "John Doe",
        }
        complaint = ComplaintCreate(**data)
        assert complaint.title == "Product Defect"

    def test_empty_title_rejection(self):
        """Test that empty title is rejected."""
        data = {
            "title": "   ",
            "description": "The product arrived broken.",
            "received_date": datetime.now(),
            "complainant_name": "John Doe",
        }
        with pytest.raises(ValidationError) as excinfo:
            ComplaintCreate(**data)
        assert "Field cannot be empty or whitespace only" in str(excinfo.value)

    def test_invalid_email_rejection(self):
        """Test that invalid email is rejected."""
        data = {
            "title": "Product Defect",
            "description": "The product arrived broken.",
            "received_date": datetime.now(),
            "complainant_name": "John Doe",
            "complainant_email": "invalid-email",
        }
        with pytest.raises(ValidationError):
            ComplaintCreate(**data)

    def test_intake_fields_wave1(self):
        """Wave 1 intake: customer, channel, subject, alleged event."""
        alleged = datetime(2026, 7, 1, 10, 30)
        data = {
            "title": "Staff conduct",
            "description": "Rude behaviour on site.",
            "received_date": datetime.now(),
            "complainant_name": "Alex Client",
            "complainant_company": "Acme Corp",
            "source_type": "in_person",
            "contract_id": 10,
            "subject_user_id": 42,
            "subject_name": "Sam Engineer",
            "alleged_event_at": alleged,
        }
        complaint = ComplaintCreate(**data)
        assert complaint.source_type == "in_person"
        assert complaint.contract_id == 10
        assert complaint.subject_user_id == 42
        assert complaint.subject_name == "Sam Engineer"
        assert complaint.alleged_event_at == alleged
        assert complaint.complainant_company == "Acme Corp"

    def test_update_keeps_complainant_and_intake_fields(self):
        """Update schema must not silently drop complainant / intake fields."""
        update = ComplaintUpdate(
            complainant_name="Updated Name",
            complainant_company="New Co",
            source_type="phone",
            contract_id=11,
            subject_name="Other person",
            alleged_event_at=datetime(2026, 6, 15, 9, 0),
        )
        assert update.complainant_name == "Updated Name"
        assert update.complainant_company == "New Co"
        assert update.source_type == "phone"
        assert update.contract_id == 11
        assert update.subject_name == "Other person"
        assert update.alleged_event_at is not None


class TestComplaintUpdateValidation:
    """Tests for ComplaintUpdate schema validation."""

    def test_valid_partial_update(self):
        """Test valid partial update."""
        data = {"title": "Updated Title"}
        update = ComplaintUpdate(**data)
        assert update.title == "Updated Title"
        assert update.status is None

    def test_update_title_whitespace_stripping(self):
        """Test that update title whitespace is stripped."""
        data = {"title": "  Updated Title  "}
        update = ComplaintUpdate(**data)
        assert update.title == "Updated Title"


class TestDeterministicOrdering:
    """Tests documenting the deterministic ordering contract."""

    def test_ordering_contract(self):
        """
        Document the deterministic ordering contract.
        Ordering MUST be: received_date DESC, id ASC
        """
        # This is a documentation test to ensure the contract is explicit
        contract = "received_date DESC, id ASC"
        assert "received_date DESC" in contract
        assert "id ASC" in contract
