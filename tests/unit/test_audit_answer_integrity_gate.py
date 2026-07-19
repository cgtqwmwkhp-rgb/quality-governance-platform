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
