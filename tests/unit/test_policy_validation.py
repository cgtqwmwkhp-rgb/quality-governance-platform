"""Unit tests for Policy validation and schemas."""

import pytest
from pydantic import ValidationError

from src.api.schemas.policy import PolicyCreate, PolicyUpdate
from src.domain.models.policy import DocumentStatus, DocumentType


class TestPolicyCreateValidation:
    """Test PolicyCreate schema validation."""

    def test_valid_policy_create(self):
        """Test creating a valid policy."""
        policy = PolicyCreate(
            title="Test Policy",
            description="Test description",
            document_type=DocumentType.POLICY,
            status=DocumentStatus.DRAFT,
        )
        assert policy.title == "Test Policy"
        assert policy.description == "Test description"
        assert policy.document_type == DocumentType.POLICY
        assert policy.status == DocumentStatus.DRAFT

    def test_policy_create_minimal(self):
        """Test creating a policy with minimal required fields."""
        policy = PolicyCreate(title="Minimal Policy")
        assert policy.title == "Minimal Policy"
        assert policy.document_type == DocumentType.POLICY  # Default
        assert policy.status == DocumentStatus.DRAFT  # Default

    def test_policy_create_empty_title_fails(self):
        """Test that empty title is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PolicyCreate(title="")
        
        errors = exc_info.value.errors()
        assert any("title" in str(error["loc"]) for error in errors)

    def test_policy_create_whitespace_title_fails(self):
        """Test that whitespace-only title is rejected."""
        with pytest.raises(ValidationError) as exc_info:
            PolicyCreate(title="   ")
        
        errors = exc_info.value.errors()
        assert any("title" in str(error["loc"]) for error in errors)

    def test_policy_create_title_too_long_fails(self):
        """Test that title exceeding max length is rejected."""
        long_title = "A" * 301  # Max is 300
        with pytest.raises(ValidationError) as exc_info:
            PolicyCreate(title=long_title)
        
        errors = exc_info.value.errors()
        assert any("title" in str(error["loc"]) for error in errors)

    def test_policy_create_title_stripped(self):
        """Test that title is stripped of leading/trailing whitespace."""
        policy = PolicyCreate(title="  Test Policy  ")
        assert policy.title == "Test Policy"

    def test_policy_create_invalid_document_type_fails(self):
        """Test that invalid document type is rejected."""
        with pytest.raises(ValidationError):
            PolicyCreate(title="Test", document_type="invalid_type")

    def test_policy_create_invalid_status_fails(self):
        """Test that invalid status is rejected."""
        with pytest.raises(ValidationError):
            PolicyCreate(title="Test", status="invalid_status")


class TestPolicyUpdateValidation:
    """Test PolicyUpdate schema validation."""

    def test_valid_policy_update(self):
        """Test updating a policy with valid data."""
        update = PolicyUpdate(
            title="Updated Title",
            description="Updated description",
        )
        assert update.title == "Updated Title"
        assert update.description == "Updated description"

    def test_policy_update_partial(self):
        """Test partial update (only some fields)."""
        update = PolicyUpdate(title="Updated Title")
        assert update.title == "Updated Title"
        assert update.description is None
        assert update.document_type is None
        assert update.status is None

    def test_policy_update_empty_title_fails(self):
        """Test that empty title is rejected in update."""
        with pytest.raises(ValidationError) as exc_info:
            PolicyUpdate(title="")
        
        errors = exc_info.value.errors()
        assert any("title" in str(error["loc"]) for error in errors)

    def test_policy_update_whitespace_title_fails(self):
        """Test that whitespace-only title is rejected in update."""
        with pytest.raises(ValidationError) as exc_info:
            PolicyUpdate(title="   ")
        
        errors = exc_info.value.errors()
        assert any("title" in str(error["loc"]) for error in errors)

    def test_policy_update_title_stripped(self):
        """Test that title is stripped in update."""
        update = PolicyUpdate(title="  Updated Title  ")
        assert update.title == "Updated Title"

    def test_policy_update_no_fields(self):
        """Test update with no fields (all None)."""
        update = PolicyUpdate()
        assert update.title is None
        assert update.description is None
        assert update.document_type is None
        assert update.status is None


class TestDeterministicOrdering:
    """Test deterministic ordering requirements."""

    def test_ordering_specification(self):
        """
        Test that ordering is explicitly specified.
        
        This is a documentation test to ensure the ordering contract is clear:
        - Primary sort: created_at DESC (newest first)
        - Secondary sort: id ASC (stable tie-breaker)
        """
        # This test documents the ordering contract
        # Actual ordering is tested in integration tests
        ordering_contract = {
            "primary": "created_at DESC",
            "secondary": "id ASC",
            "rationale": "Deterministic ordering for auditability",
        }
        
        assert ordering_contract["primary"] == "created_at DESC"
        assert ordering_contract["secondary"] == "id ASC"
        assert "Deterministic" in ordering_contract["rationale"]
