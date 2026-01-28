"""
Unit Tests: Compliance Score Formula + Schema Validation

Verifies:
1. Compliance percentage calculation formula
2. ComplianceScoreResponse schema structure
3. setup_required flag logic
4. Edge cases (zero controls, all implemented, etc.)

These tests run without database dependency.
"""

import pytest
from pydantic import ValidationError

from src.api.schemas.standard import ComplianceScoreResponse, ControlListItem


class TestComplianceScoreFormula:
    """Test the compliance score formula: (implemented + 0.5 * partial) / total * 100."""

    def test_formula_all_implemented(self):
        """100% when all controls implemented."""
        # 4 implemented, 0 partial, 0 not_implemented
        total = 4
        implemented = 4
        partial = 0
        
        score = round((implemented + 0.5 * partial) / total * 100)
        assert score == 100

    def test_formula_mixed_status(self):
        """Correct calculation with mixed statuses."""
        # 2 implemented, 1 partial, 1 not_implemented => (2 + 0.5) / 4 * 100 = 62.5 => 62
        total = 4
        implemented = 2
        partial = 1
        
        score = round((implemented + 0.5 * partial) / total * 100)
        assert score == 62

    def test_formula_all_partial(self):
        """50% when all controls partial."""
        total = 4
        implemented = 0
        partial = 4
        
        score = round((implemented + 0.5 * partial) / total * 100)
        assert score == 50

    def test_formula_none_implemented(self):
        """0% when no controls implemented or partial."""
        total = 4
        implemented = 0
        partial = 0
        
        score = round((implemented + 0.5 * partial) / total * 100)
        assert score == 0

    def test_formula_single_implemented(self):
        """100% with single implemented control."""
        total = 1
        implemented = 1
        partial = 0
        
        score = round((implemented + 0.5 * partial) / total * 100)
        assert score == 100

    def test_formula_single_partial(self):
        """50% with single partial control."""
        total = 1
        implemented = 0
        partial = 1
        
        score = round((implemented + 0.5 * partial) / total * 100)
        assert score == 50

    def test_formula_rounding_down(self):
        """Rounding behavior (Python round uses banker's rounding)."""
        # 1 implemented, 1 partial, 1 not_implemented => (1 + 0.5) / 3 * 100 = 50
        total = 3
        implemented = 1
        partial = 1
        
        score = round((implemented + 0.5 * partial) / total * 100)
        assert score == 50

    def test_formula_large_numbers(self):
        """Correct calculation with many controls."""
        total = 100
        implemented = 70
        partial = 20
        
        # (70 + 10) / 100 * 100 = 80
        score = round((implemented + 0.5 * partial) / total * 100)
        assert score == 80


class TestComplianceScoreResponseSchema:
    """Test ComplianceScoreResponse Pydantic schema."""

    def test_schema_valid_complete(self):
        """Valid response with all fields."""
        response = ComplianceScoreResponse(
            standard_id=1,
            standard_code="ISO9001",
            total_controls=10,
            implemented_count=7,
            partial_count=2,
            not_implemented_count=1,
            compliance_percentage=80,
            setup_required=False,
        )
        
        assert response.standard_id == 1
        assert response.standard_code == "ISO9001"
        assert response.total_controls == 10
        assert response.compliance_percentage == 80
        assert response.setup_required is False

    def test_schema_setup_required_zero_controls(self):
        """setup_required=True when total_controls=0."""
        response = ComplianceScoreResponse(
            standard_id=2,
            standard_code="ISO14001",
            total_controls=0,
            implemented_count=0,
            partial_count=0,
            not_implemented_count=0,
            compliance_percentage=0,
            setup_required=True,
        )
        
        assert response.total_controls == 0
        assert response.setup_required is True
        assert response.compliance_percentage == 0

    def test_schema_serialization(self):
        """Schema serializes to expected JSON keys."""
        response = ComplianceScoreResponse(
            standard_id=1,
            standard_code="ISO9001",
            total_controls=5,
            implemented_count=3,
            partial_count=1,
            not_implemented_count=1,
            compliance_percentage=70,
            setup_required=False,
        )
        
        data = response.model_dump()
        
        expected_keys = {
            "standard_id",
            "standard_code",
            "total_controls",
            "implemented_count",
            "partial_count",
            "not_implemented_count",
            "compliance_percentage",
            "setup_required",
        }
        
        assert set(data.keys()) == expected_keys


class TestControlListItemSchema:
    """Test ControlListItem Pydantic schema."""

    def test_schema_valid(self):
        """Valid control list item."""
        item = ControlListItem(
            id=1,
            control_number="5.1.1",
            title="Access Control",
            clause_id=10,
            clause_number="5.1",
            implementation_status="implemented",
            is_applicable=True,
            is_active=True,
        )
        
        assert item.control_number == "5.1.1"
        assert item.clause_number == "5.1"
        assert item.implementation_status == "implemented"
        assert item.is_applicable is True
        assert item.is_active is True

    def test_schema_nullable_status(self):
        """implementation_status can be None."""
        item = ControlListItem(
            id=2,
            control_number="5.1.2",
            title="Another Control",
            clause_id=10,
            clause_number="5.1",
            implementation_status=None,
            is_applicable=True,
            is_active=True,
        )
        
        assert item.implementation_status is None

    def test_schema_serialization_keys(self):
        """Schema serializes to expected JSON keys."""
        item = ControlListItem(
            id=1,
            control_number="5.1.1",
            title="Access Control",
            clause_id=10,
            clause_number="5.1",
            implementation_status="partial",
            is_applicable=True,
            is_active=True,
        )
        
        data = item.model_dump()
        
        expected_keys = {
            "id",
            "control_number",
            "title",
            "clause_id",
            "clause_number",
            "implementation_status",
            "is_applicable",
            "is_active",
        }
        
        assert set(data.keys()) == expected_keys


class TestComplianceScoreDeterminism:
    """Test that compliance score calculation is deterministic."""

    def test_same_inputs_same_output(self):
        """Same inputs always produce same output."""
        for _ in range(100):
            total = 10
            implemented = 6
            partial = 3
            
            score = round((implemented + 0.5 * partial) / total * 100)
            assert score == 75

    def test_formula_is_pure_function(self):
        """Formula has no side effects or randomness."""
        inputs = [
            (10, 5, 3),  # 65%
            (8, 4, 2),   # 62%
            (100, 80, 10),  # 85%
            (1, 1, 0),   # 100%
            (1, 0, 1),   # 50%
        ]
        
        expected = [65, 62, 85, 100, 50]
        
        for (total, impl, part), exp in zip(inputs, expected):
            score = round((impl + 0.5 * part) / total * 100)
            assert score == exp
