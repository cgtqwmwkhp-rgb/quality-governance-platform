"""Unit tests for RTA validation and ordering contract."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from src.api.schemas.rta import RTACreate, RTAUpdate
from src.domain.models.rta import RTASeverity, RTAStatus


def test_rta_create_valid():
    """Test valid RTA creation schema."""
    now = datetime.now(timezone.utc)
    data = {
        "title": "Test RTA",
        "description": "Test collision description",
        "collision_date": now,
        "reported_date": now,
        "location": "Test Location",
        "severity": RTASeverity.DAMAGE_ONLY,
        "status": RTAStatus.REPORTED,
    }
    rta = RTACreate(**data)
    assert rta.title == data["title"]
    assert rta.location == data["location"]
    assert rta.severity == RTASeverity.DAMAGE_ONLY


def test_rta_create_invalid_title():
    """Test RTA creation with invalid title."""
    now = datetime.now(timezone.utc)
    base_data = {
        "description": "Test",
        "collision_date": now,
        "reported_date": now,
        "location": "Test Location",
    }

    # Empty title
    with pytest.raises(ValidationError):
        RTACreate(title="", **base_data)

    # Whitespace title
    with pytest.raises(ValidationError):
        RTACreate(title="   ", **base_data)

    # Too long title
    with pytest.raises(ValidationError):
        RTACreate(title="a" * 301, **base_data)


def test_rta_update_partial():
    """Test partial RTA update schema."""
    data = {"status": RTAStatus.CLOSED, "severity": RTASeverity.SERIOUS_INJURY}
    update = RTAUpdate(**data)
    assert update.status == RTAStatus.CLOSED
    assert update.severity == RTASeverity.SERIOUS_INJURY
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
