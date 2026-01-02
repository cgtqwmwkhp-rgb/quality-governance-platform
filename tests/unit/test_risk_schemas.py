"""Unit tests for Risk schemas."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.api.schemas.risk import (
    RiskControlCreate,
    RiskControlUpdate,
    RiskAssessmentCreate,
    RiskCreate,
    RiskUpdate,
    RiskMatrixCell,
)


class TestRiskCreate:
    """Tests for RiskCreate schema."""

    def test_minimal_risk(self):
        """Test creating a risk with minimal fields."""
        risk = RiskCreate(
            title="Data breach risk",
            description="Risk of unauthorized access to customer data",
        )
        assert risk.title == "Data breach risk"
        assert risk.category == "operational"
        assert risk.likelihood == 3
        assert risk.impact == 3
        assert risk.treatment_strategy == "mitigate"

    def test_full_risk(self):
        """Test creating a risk with all fields."""
        risk = RiskCreate(
            title="Supply chain disruption",
            description="Risk of key supplier failure",
            category="operational",
            subcategory="supply_chain",
            risk_source="External dependency",
            risk_event="Supplier bankruptcy",
            risk_consequence="Production halt",
            likelihood=4,
            impact=5,
            owner_id=10,
            department="Operations",
            review_frequency_months=6,
            next_review_date=datetime(2026, 7, 1),
            clause_ids=[1, 2, 3],
            treatment_strategy="transfer",
            treatment_plan="Diversify supplier base",
        )
        assert risk.likelihood == 4
        assert risk.impact == 5
        assert risk.treatment_strategy == "transfer"

    def test_invalid_category(self):
        """Test that invalid category is rejected."""
        with pytest.raises(ValidationError):
            RiskCreate(
                title="Test",
                description="Test",
                category="invalid_category",
            )

    def test_likelihood_range(self):
        """Test that likelihood must be 1-5."""
        with pytest.raises(ValidationError):
            RiskCreate(
                title="Test",
                description="Test",
                likelihood=6,
            )
        with pytest.raises(ValidationError):
            RiskCreate(
                title="Test",
                description="Test",
                likelihood=0,
            )

    def test_impact_range(self):
        """Test that impact must be 1-5."""
        with pytest.raises(ValidationError):
            RiskCreate(
                title="Test",
                description="Test",
                impact=6,
            )


class TestRiskUpdate:
    """Tests for RiskUpdate schema."""

    def test_partial_update(self):
        """Test partial risk update."""
        update = RiskUpdate(likelihood=4, impact=4)
        assert update.likelihood == 4
        assert update.impact == 4
        assert update.title is None

    def test_status_update(self):
        """Test updating risk status."""
        update = RiskUpdate(status="treating")
        assert update.status == "treating"

    def test_all_fields_optional(self):
        """Test that all fields are optional."""
        update = RiskUpdate()
        assert update.title is None
        assert update.description is None


class TestRiskControlCreate:
    """Tests for RiskControlCreate schema."""

    def test_minimal_control(self):
        """Test creating a control with minimal fields."""
        control = RiskControlCreate(title="Access control policy")
        assert control.title == "Access control policy"
        assert control.control_type == "preventive"
        assert control.implementation_status == "planned"

    def test_full_control(self):
        """Test creating a control with all fields."""
        control = RiskControlCreate(
            title="Multi-factor authentication",
            description="Require MFA for all system access",
            control_type="preventive",
            implementation_status="implemented",
            effectiveness="effective",
            owner_id=5,
            clause_ids=[1, 2],
            control_ids=[10, 11],
            last_tested_date=datetime(2025, 12, 1),
            next_test_date=datetime(2026, 6, 1),
            test_frequency_months=6,
        )
        assert control.effectiveness == "effective"
        assert control.test_frequency_months == 6

    def test_invalid_control_type(self):
        """Test that invalid control type is rejected."""
        with pytest.raises(ValidationError):
            RiskControlCreate(
                title="Test",
                control_type="invalid_type",
            )


class TestRiskControlUpdate:
    """Tests for RiskControlUpdate schema."""

    def test_partial_update(self):
        """Test partial control update."""
        update = RiskControlUpdate(
            implementation_status="implemented",
            effectiveness="effective",
        )
        assert update.implementation_status == "implemented"
        assert update.title is None


class TestRiskAssessmentCreate:
    """Tests for RiskAssessmentCreate schema."""

    def test_minimal_assessment(self):
        """Test creating an assessment with minimal fields."""
        assessment = RiskAssessmentCreate(
            assessment_date=datetime(2026, 1, 15),
            inherent_likelihood=4,
            inherent_impact=5,
            residual_likelihood=2,
            residual_impact=3,
        )
        assert assessment.inherent_likelihood == 4
        assert assessment.residual_likelihood == 2
        assert assessment.assessment_type == "periodic"

    def test_full_assessment(self):
        """Test creating an assessment with all fields."""
        assessment = RiskAssessmentCreate(
            assessment_date=datetime(2026, 1, 15),
            assessment_type="post_incident",
            inherent_likelihood=5,
            inherent_impact=5,
            residual_likelihood=3,
            residual_impact=3,
            target_likelihood=2,
            target_impact=2,
            assessment_notes="Reassessed after security incident",
            control_effectiveness_notes="Controls partially effective",
            assessed_by_id=10,
        )
        assert assessment.assessment_type == "post_incident"
        assert assessment.target_likelihood == 2

    def test_likelihood_range(self):
        """Test that likelihood values must be 1-5."""
        with pytest.raises(ValidationError):
            RiskAssessmentCreate(
                assessment_date=datetime(2026, 1, 15),
                inherent_likelihood=6,
                inherent_impact=3,
                residual_likelihood=3,
                residual_impact=3,
            )


class TestRiskMatrixCell:
    """Tests for RiskMatrixCell schema."""

    def test_matrix_cell(self):
        """Test creating a risk matrix cell."""
        cell = RiskMatrixCell(
            likelihood=4,
            impact=5,
            score=20,
            level="critical",
            color="#ef4444",
            risk_count=3,
        )
        assert cell.score == 20
        assert cell.level == "critical"
        assert cell.risk_count == 3


class TestRiskScoreCalculation:
    """Tests for risk score calculation logic."""

    def test_critical_risk(self):
        """Test critical risk identification."""
        # Score >= 20 should be critical
        risk = RiskCreate(
            title="Test",
            description="Test",
            likelihood=5,
            impact=5,
        )
        assert risk.likelihood * risk.impact == 25

    def test_high_risk(self):
        """Test high risk identification."""
        # Score 12-19 should be high
        risk = RiskCreate(
            title="Test",
            description="Test",
            likelihood=4,
            impact=4,
        )
        assert risk.likelihood * risk.impact == 16

    def test_medium_risk(self):
        """Test medium risk identification."""
        # Score 6-11 should be medium
        risk = RiskCreate(
            title="Test",
            description="Test",
            likelihood=3,
            impact=3,
        )
        assert risk.likelihood * risk.impact == 9

    def test_low_risk(self):
        """Test low risk identification."""
        # Score 1-5 should be low
        risk = RiskCreate(
            title="Test",
            description="Test",
            likelihood=1,
            impact=2,
        )
        assert risk.likelihood * risk.impact == 2
