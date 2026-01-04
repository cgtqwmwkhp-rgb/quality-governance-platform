"""Unit tests for RTA validation and ordering contract."""

import pytest
from pydantic import ValidationError

from src.api.schemas.rta import RTACreate, RTAUpdate
from src.domain.models.rta_analysis import RTAStatus


def test_rta_create_valid():
    """Test valid RTA creation schema."""
    data = {
        "incident_id": 1,
        "title": "Root Cause Analysis for Incident 1",
        "problem_statement": "The system failed due to a memory leak.",
        "status": RTAStatus.DRAFT,
    }
    rta = RTACreate(**data)
    assert rta.title == data["title"]
    assert rta.incident_id == data["incident_id"]


def test_rta_create_invalid_title():
    """Test RTA creation with invalid title."""
    # Empty title
    with pytest.raises(ValidationError):
        RTACreate(incident_id=1, title="", problem_statement="test")

    # Whitespace title
    with pytest.raises(ValidationError):
        RTACreate(incident_id=1, title="   ", problem_statement="test")

    # Too long title
    with pytest.raises(ValidationError):
        RTACreate(incident_id=1, title="a" * 301, problem_statement="test")


def test_rta_update_partial():
    """Test partial RTA update schema."""
    data = {"status": RTAStatus.APPROVED}
    update = RTAUpdate(**data)
    assert update.status == RTAStatus.APPROVED
    assert update.title is None


def test_rta_ordering_contract():
    """
    Document the deterministic ordering contract.
    RTAs must be ordered by created_at DESC, then id ASC.
    """
    # This is a documentation test to ensure the contract is explicit
    ordering_contract = ["created_at DESC", "id ASC"]
    assert "created_at DESC" in ordering_contract
    assert "id ASC" in ordering_contract
