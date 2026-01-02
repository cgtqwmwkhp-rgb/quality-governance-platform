"""Unit tests for Audit schemas."""

import pytest
from datetime import datetime
from pydantic import ValidationError

from src.api.schemas.audit import (
    QuestionOptionBase,
    ConditionalLogicRule,
    EvidenceRequirement,
    AuditQuestionCreate,
    AuditSectionCreate,
    AuditTemplateCreate,
    AuditRunCreate,
    AuditResponseCreate,
    AuditFindingCreate,
)


class TestQuestionOptionBase:
    """Tests for QuestionOptionBase schema."""

    def test_valid_option(self):
        """Test creating a valid question option."""
        option = QuestionOptionBase(
            value="yes",
            label="Yes",
            score=1.0,
            is_correct=True,
            triggers_finding=False,
        )
        assert option.value == "yes"
        assert option.label == "Yes"
        assert option.score == 1.0
        assert option.is_correct is True

    def test_option_with_finding_trigger(self):
        """Test option that triggers a finding."""
        option = QuestionOptionBase(
            value="no",
            label="No",
            triggers_finding=True,
            finding_severity="high",
        )
        assert option.triggers_finding is True
        assert option.finding_severity == "high"

    def test_option_value_required(self):
        """Test that value is required."""
        with pytest.raises(ValidationError):
            QuestionOptionBase(label="Test")


class TestConditionalLogicRule:
    """Tests for ConditionalLogicRule schema."""

    def test_valid_rule(self):
        """Test creating a valid conditional logic rule."""
        rule = ConditionalLogicRule(
            source_question_id=1,
            operator="equals",
            value="yes",
            action="show",
        )
        assert rule.source_question_id == 1
        assert rule.operator == "equals"
        assert rule.action == "show"

    def test_invalid_operator(self):
        """Test that invalid operator is rejected."""
        with pytest.raises(ValidationError):
            ConditionalLogicRule(
                source_question_id=1,
                operator="invalid_op",
                action="show",
            )

    def test_invalid_action(self):
        """Test that invalid action is rejected."""
        with pytest.raises(ValidationError):
            ConditionalLogicRule(
                source_question_id=1,
                operator="equals",
                action="invalid_action",
            )


class TestEvidenceRequirement:
    """Tests for EvidenceRequirement schema."""

    def test_default_values(self):
        """Test default evidence requirement values."""
        req = EvidenceRequirement()
        assert req.required is False
        assert req.min_attachments == 0
        assert req.max_attachments == 10
        assert "image" in req.allowed_types

    def test_custom_requirements(self):
        """Test custom evidence requirements."""
        req = EvidenceRequirement(
            required=True,
            min_attachments=1,
            max_attachments=5,
            allowed_types=["image"],
            require_photo=True,
        )
        assert req.required is True
        assert req.min_attachments == 1
        assert req.require_photo is True


class TestAuditQuestionCreate:
    """Tests for AuditQuestionCreate schema."""

    def test_minimal_question(self):
        """Test creating a question with minimal fields."""
        question = AuditQuestionCreate(
            question_text="Is the area clean?",
            question_type="yes_no",
        )
        assert question.question_text == "Is the area clean?"
        assert question.question_type == "yes_no"
        assert question.is_required is True
        assert question.weight == 1.0

    def test_full_question(self):
        """Test creating a question with all fields."""
        question = AuditQuestionCreate(
            question_text="Rate the cleanliness",
            question_type="score",
            description="Rate from 1-5",
            help_text="1 = Poor, 5 = Excellent",
            is_required=True,
            allow_na=True,
            max_score=5.0,
            weight=2.0,
            min_value=1,
            max_value=5,
            clause_ids=[1, 2, 3],
            risk_category="safety",
        )
        assert question.max_score == 5.0
        assert question.weight == 2.0
        assert question.clause_ids == [1, 2, 3]

    def test_invalid_question_type(self):
        """Test that invalid question type is rejected."""
        with pytest.raises(ValidationError):
            AuditQuestionCreate(
                question_text="Test",
                question_type="invalid_type",
            )

    def test_question_with_options(self):
        """Test creating a question with options."""
        question = AuditQuestionCreate(
            question_text="Select condition",
            question_type="dropdown",
            options=[
                QuestionOptionBase(value="good", label="Good", score=3),
                QuestionOptionBase(value="fair", label="Fair", score=2),
                QuestionOptionBase(value="poor", label="Poor", score=1),
            ],
        )
        assert len(question.options) == 3


class TestAuditSectionCreate:
    """Tests for AuditSectionCreate schema."""

    def test_minimal_section(self):
        """Test creating a section with minimal fields."""
        section = AuditSectionCreate(title="General")
        assert section.title == "General"
        assert section.sort_order == 0
        assert section.weight == 1.0

    def test_repeatable_section(self):
        """Test creating a repeatable section."""
        section = AuditSectionCreate(
            title="Equipment Check",
            is_repeatable=True,
            max_repeats=10,
        )
        assert section.is_repeatable is True
        assert section.max_repeats == 10


class TestAuditTemplateCreate:
    """Tests for AuditTemplateCreate schema."""

    def test_minimal_template(self):
        """Test creating a template with minimal fields."""
        template = AuditTemplateCreate(name="Daily Inspection")
        assert template.name == "Daily Inspection"
        assert template.audit_type == "inspection"
        assert template.scoring_method == "percentage"

    def test_full_template(self):
        """Test creating a template with all fields."""
        template = AuditTemplateCreate(
            name="ISO 9001 Audit",
            description="Quality management system audit",
            category="Quality",
            audit_type="audit",
            frequency="annually",
            scoring_method="weighted",
            passing_score=80.0,
            require_gps=True,
            require_signature=True,
            require_approval=True,
            auto_create_findings=True,
        )
        assert template.passing_score == 80.0
        assert template.require_approval is True

    def test_invalid_audit_type(self):
        """Test that invalid audit type is rejected."""
        with pytest.raises(ValidationError):
            AuditTemplateCreate(
                name="Test",
                audit_type="invalid_type",
            )


class TestAuditRunCreate:
    """Tests for AuditRunCreate schema."""

    def test_minimal_run(self):
        """Test creating a run with minimal fields."""
        run = AuditRunCreate(template_id=1)
        assert run.template_id == 1

    def test_full_run(self):
        """Test creating a run with all fields."""
        run = AuditRunCreate(
            template_id=1,
            title="Q1 2026 Audit",
            location="Building A",
            location_details="Floor 2, Room 201",
            scheduled_date=datetime(2026, 3, 15, 9, 0),
            due_date=datetime(2026, 3, 20, 17, 0),
            assigned_to_id=5,
            latitude=51.5074,
            longitude=-0.1278,
        )
        assert run.location == "Building A"
        assert run.latitude == 51.5074


class TestAuditResponseCreate:
    """Tests for AuditResponseCreate schema."""

    def test_text_response(self):
        """Test creating a text response."""
        response = AuditResponseCreate(
            question_id=1,
            response_text="All equipment in good condition",
        )
        assert response.question_id == 1
        assert response.response_text == "All equipment in good condition"

    def test_numeric_response(self):
        """Test creating a numeric response."""
        response = AuditResponseCreate(
            question_id=2,
            response_number=4.5,
            score=4.5,
        )
        assert response.response_number == 4.5
        assert response.score == 4.5

    def test_na_response(self):
        """Test creating an N/A response."""
        response = AuditResponseCreate(
            question_id=3,
            is_na=True,
            notes="Not applicable - equipment not present",
        )
        assert response.is_na is True


class TestAuditFindingCreate:
    """Tests for AuditFindingCreate schema."""

    def test_minimal_finding(self):
        """Test creating a finding with minimal fields."""
        finding = AuditFindingCreate(
            title="Missing fire extinguisher",
            description="Fire extinguisher not present in designated location",
        )
        assert finding.title == "Missing fire extinguisher"
        assert finding.severity == "medium"
        assert finding.corrective_action_required is True

    def test_full_finding(self):
        """Test creating a finding with all fields."""
        finding = AuditFindingCreate(
            title="Critical safety violation",
            description="Emergency exit blocked by equipment",
            severity="critical",
            finding_type="nonconformity",
            clause_ids=[1, 2],
            control_ids=[5],
            risk_ids=[10],
            corrective_action_required=True,
            corrective_action_due_date=datetime(2026, 1, 15),
        )
        assert finding.severity == "critical"
        assert finding.clause_ids == [1, 2]

    def test_invalid_severity(self):
        """Test that invalid severity is rejected."""
        with pytest.raises(ValidationError):
            AuditFindingCreate(
                title="Test",
                description="Test description",
                severity="invalid_severity",
            )
