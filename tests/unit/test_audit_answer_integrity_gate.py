"""Unit tests for audit answer-integrity gate helpers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.domain.exceptions import ValidationError
from src.domain.models.audit import AuditQuestion, AuditSection, AuditTemplate
from src.domain.services.audit_service import _UNSUPPORTED_PUBLISH_QUESTION_TYPES, AuditService


def test_missing_required_question_ids_flags_unanswered_and_evidence_gaps():
    questions = [
        SimpleNamespace(id=1, is_active=True, is_required=True, evidence_requirements_json=None),
        SimpleNamespace(
            id=2,
            is_active=True,
            is_required=True,
            evidence_requirements_json={"required": True, "require_photo": True, "min_attachments": 1},
        ),
        SimpleNamespace(id=3, is_active=True, is_required=False, evidence_requirements_json=None),
    ]
    responses = [
        SimpleNamespace(question_id=1, is_na=False, response_value="yes", response_json=None),
        SimpleNamespace(question_id=2, is_na=False, response_value=None, response_json={}),
    ]

    missing = AuditService._missing_required_question_ids(questions=questions, responses=responses)  # type: ignore[arg-type]

    assert missing == [2]


def test_validate_publishable_template_rejects_file_type():
    question = AuditQuestion(
        question_text="Upload doc",
        question_type="file",
        weight=1.0,
        options_json=None,
    )
    section = AuditSection(title="Section", questions=[question])
    template = AuditTemplate(name="Template", sections=[section], questions=[question])

    with pytest.raises(ValidationError, match="unsupported type"):
        AuditService._validate_publishable_template(template)


def test_unsupported_publish_question_types_contains_file():
    assert "file" in _UNSUPPORTED_PUBLISH_QUESTION_TYPES


def test_build_template_version_snapshot_includes_questions():
    question = AuditQuestion(
        id=10,
        section_id=5,
        question_text="Is PPE worn?",
        question_type="yes_no",
        is_required=True,
        weight=1.0,
    )
    section = AuditSection(
        id=5,
        title="PPE",
        description=None,
        sort_order=1,
        weight=1.0,
        questions=[question],
    )
    template = AuditTemplate(
        id=1,
        version=2,
        name="Safety",
        description=None,
        category="Safety",
        audit_type="inspection",
        scoring_method=None,
        passing_score=80,
        auto_create_findings=True,
        sections=[section],
        questions=[question],
    )

    snapshot = AuditService._build_template_version_snapshot(template)

    assert snapshot["template_id"] == 1
    assert snapshot["version"] == 2
    assert snapshot["questions"][0]["question_text"] == "Is PPE worn?"


def test_validate_publishable_ignores_inactive_empty_leftover_section():
    """Wickford: leftover 'Section 1' is_active=false must not block publish."""
    live_q = AuditQuestion(
        question_text="Fire exits clear?",
        question_type="yes_no",
        weight=1.0,
        is_active=True,
        options_json=None,
    )
    live_section = AuditSection(title="Fire", questions=[live_q], is_active=True)
    ghost = AuditSection(title="Section 1", questions=[], is_active=False)
    dead_checkbox = AuditQuestion(
        question_text="Select areas covered in this inspection",
        question_type="checkbox",
        weight=1.0,
        is_active=False,
        options_json=None,
    )
    template = AuditTemplate(
        name="Wickford HQ Daily Site Inspection",
        sections=[ghost, live_section],
        questions=[dead_checkbox, live_q],
    )

    AuditService._validate_publishable_template(template)


def test_validate_publishable_rejects_when_only_inactive_questions_remain():
    dead = AuditQuestion(
        question_text="Gone",
        question_type="yes_no",
        weight=1.0,
        is_active=False,
    )
    section = AuditSection(title="Empty live", questions=[dead], is_active=True)
    template = AuditTemplate(name="Draft", sections=[section], questions=[dead])

    with pytest.raises(ValidationError, match="at least one question"):
        AuditService._validate_publishable_template(template)


def test_snapshot_omits_inactive_sections_and_questions():
    live_q = AuditQuestion(
        id=12,
        section_id=4,
        question_text="Live",
        question_type="yes_no",
        is_required=True,
        weight=1.0,
        is_active=True,
    )
    dead_q = AuditQuestion(
        id=137,
        section_id=30,
        question_text="Ghost checkbox",
        question_type="checkbox",
        is_required=False,
        weight=1.0,
        is_active=False,
        options_json=None,
    )
    live_section = AuditSection(
        id=4,
        title="Fire",
        description=None,
        sort_order=1,
        weight=1.0,
        is_active=True,
        questions=[live_q],
    )
    ghost_section = AuditSection(
        id=30,
        title="Section 1",
        description=None,
        sort_order=0,
        weight=1.0,
        is_active=False,
        questions=[dead_q],
    )
    template = AuditTemplate(
        id=28,
        version=1,
        name="Wickford",
        description=None,
        category="Safety",
        audit_type="inspection",
        scoring_method=None,
        passing_score=None,
        auto_create_findings=True,
        sections=[ghost_section, live_section],
        questions=[dead_q, live_q],
    )

    snapshot = AuditService._build_template_version_snapshot(template)

    assert [s["id"] for s in snapshot["sections"]] == [4]
    assert [q["id"] for q in snapshot["questions"]] == [12]
    assert snapshot["sections"][0]["questions"][0]["id"] == 12
