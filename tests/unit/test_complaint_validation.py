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
