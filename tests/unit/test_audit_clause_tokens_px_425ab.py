"""PX-425a/b — clause tokens survive the builder write path onto findings.

W0 UAT LIVE-01 found 0 of 37 question-generated findings carrying a clause
token, so the live matrix could not join any of them to a cell. Two defects:

* the write schemas typed ``clause_ids`` as ``List[int]``, which no clause token
  ("7.2", "9001-8.5.1") can be coerced into, and
* the builder never sent the ISO Clause field at all.

These tests cover the backend half: the schemas accept tokens without losing
``extra="forbid"``, the read schemas do not 500 on them, and auto-create copies
the question's tokens onto the finding in a form the PX-425c matcher joins.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.api.schemas.audit import (
    AuditFindingCreate,
    AuditFindingUpdate,
    AuditQuestionCreate,
    AuditQuestionResponse,
    AuditQuestionUpdate,
)
from src.domain.models.audit import AuditFinding, AuditQuestion
from src.domain.services.audit_service import AuditService
from src.domain.services.standards_cell_aggregate_service import clause_match_keys, token_matches_clause


def _question_kwargs(**overrides: object) -> dict:
    payload = {"question_text": "Is design change control evidenced?", "question_type": "yes_no"}
    payload.update(overrides)
    return payload


class TestQuestionWriteSchemaAcceptsClauseTokens:
    def test_create_keeps_clause_tokens_as_strings(self):
        question = AuditQuestionCreate(**_question_kwargs(clause_ids=["9001-8.5.1", "7.2"]))
        assert question.clause_ids == ["9001-8.5.1", "7.2"]
        assert all(isinstance(value, str) for value in question.clause_ids)

    def test_create_does_not_coerce_a_numeric_token_into_a_catalogue_id(self):
        """ "8" is clause 8, not catalogue row 8; the distinction is the whole bug."""
        question = AuditQuestionCreate(**_question_kwargs(clause_ids=["8"]))
        assert question.clause_ids == ["8"]
        assert isinstance(question.clause_ids[0], str)

    def test_create_still_accepts_integer_catalogue_ids(self):
        question = AuditQuestionCreate(**_question_kwargs(clause_ids=[1, 2, 3]))
        assert question.clause_ids == [1, 2, 3]
        assert all(isinstance(value, int) for value in question.clause_ids)

    def test_create_accepts_a_mixed_list(self):
        question = AuditQuestionCreate(**_question_kwargs(clause_ids=[4, "9001-8.5.1"]))
        assert question.clause_ids == [4, "9001-8.5.1"]

    def test_create_still_forbids_unknown_fields(self):
        with pytest.raises(ValidationError) as exc:
            AuditQuestionCreate(**_question_kwargs(iso_clause="7.2"))
        assert exc.value.errors()[0]["type"] == "extra_forbidden"

    def test_update_accepts_tokens_and_clears_with_an_explicit_null(self):
        assert AuditQuestionUpdate(clause_ids=["9001-8.5.1"]).clause_ids == ["9001-8.5.1"]
        cleared = AuditQuestionUpdate(clause_ids=None)
        assert cleared.model_dump(exclude_unset=True) == {"clause_ids": None}

    def test_update_still_forbids_unknown_fields(self):
        with pytest.raises(ValidationError) as exc:
            AuditQuestionUpdate(clause_tokens=["7.2"])
        assert exc.value.errors()[0]["type"] == "extra_forbidden"

    def test_update_caps_regulatory_reference_at_the_column_width(self):
        """The builder now sends this on every save; 201 chars must 422, not 500."""
        assert AuditQuestionUpdate(regulatory_reference="9" * 200).regulatory_reference == "9" * 200
        with pytest.raises(ValidationError) as exc:
            AuditQuestionUpdate(regulatory_reference="9" * 201)
        assert exc.value.errors()[0]["type"] == "string_too_long"


def _persisted_question(clause_ids_json: object) -> AuditQuestion:
    """A question as the route reads it back. Column defaults are applied by the
    database, so a transient instance has to spell out the non-nullable ones."""
    return AuditQuestion(
        id=11,
        template_id=5,
        question_text="Is design change control evidenced?",
        question_type="yes_no",
        is_required=True,
        allow_na=False,
        weight=1.0,
        sign_off_required=False,
        failure_triggers_action=False,
        positive_answer="yes",
        sort_order=0,
        is_active=True,
        clause_ids_json=clause_ids_json,
        created_at=datetime(2026, 8, 19),
        updated_at=datetime(2026, 8, 19),
    )


class TestQuestionResponseReadsClauseTokens:
    """A token written by the builder must be readable, not a 500 on GET template."""

    def test_response_validates_string_tokens_from_the_orm_column(self):
        question = _persisted_question(["9001-8.5.1"])
        assert AuditQuestionResponse.model_validate(question).clause_ids == ["9001-8.5.1"]

    def test_response_still_validates_integer_catalogue_ids(self):
        question = _persisted_question([7, 12])
        assert AuditQuestionResponse.model_validate(question).clause_ids == [7, 12]


class TestFindingWriteSchemaAcceptsClauseTokens:
    def test_create_keeps_tokens(self):
        finding = AuditFindingCreate(
            title="Design change not evidenced",
            description="No record of the change review",
            clause_ids=["9001-8.5.1"],
        )
        assert finding.clause_ids == ["9001-8.5.1"]

    def test_update_keeps_tokens(self):
        assert AuditFindingUpdate(clause_ids=["7.2", 3]).clause_ids == ["7.2", 3]

    def test_create_still_forbids_unknown_fields(self):
        with pytest.raises(ValidationError) as exc:
            AuditFindingCreate(title="t", description="d", clause_tokens=["7.2"])
        assert exc.value.errors()[0]["type"] == "extra_forbidden"


def _failing_response(question_id: int) -> SimpleNamespace:
    return SimpleNamespace(
        question_id=question_id,
        is_na=False,
        response_value="no",
        response_text=None,
        response_number=None,
        response_bool=None,
        response_date=None,
        score=None,
        max_score=None,
        notes=None,
    )


class _QuestionResult:
    def __init__(self, questions: list[AuditQuestion]) -> None:
        self._questions = questions

    def scalars(self):
        return SimpleNamespace(all=lambda: self._questions)


@pytest.mark.asyncio
async def test_auto_create_copies_question_clause_tokens_onto_the_finding(
    monkeypatch: pytest.MonkeyPatch,
):
    question = AuditQuestion(
        id=41,
        template_id=5,
        question_text="Is design change control evidenced?",
        question_type="yes_no",
        is_active=True,
        clause_ids_json=["9001-8.5.1"],
    )
    run = SimpleNamespace(
        id=7,
        tenant_id=3,
        template_id=5,
        findings=[],
        responses=[_failing_response(question.id)],
        assurance_scheme=None,
        external_reference=None,
        external_body_name=None,
    )
    added: list = []
    service = AuditService(
        db=SimpleNamespace(
            execute=AsyncMock(return_value=_QuestionResult([question])),
            add=added.append,
            flush=AsyncMock(),
        )
    )
    service._ensure_action_for_finding = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service._ensure_risk_for_finding = AsyncMock(return_value=None)  # type: ignore[method-assign]
    monkeypatch.setattr(
        "src.domain.services.audit_service.ReferenceNumberService.generate",
        AsyncMock(return_value="FND-2026-0001"),
    )

    await service._auto_generate_findings_actions_and_risks(
        run=run,
        template=SimpleNamespace(auto_create_findings=True),
        actor_user_id=1,
    )

    assert len(added) == 1
    finding = added[0]
    assert isinstance(finding, AuditFinding)
    assert finding.question_id == question.id
    assert finding.clause_ids_json_legacy == ["9001-8.5.1"]

    # The copied token is what the PX-425c matcher joins to a matrix cell; an
    # unmapped question still produces an unjoinable finding, which is honest.
    assert token_matches_clause(finding.clause_ids_json_legacy[0], clause_match_keys("9001", "8"), "8")
    assert token_matches_clause(finding.clause_ids_json_legacy[0], clause_match_keys("9001", "8.5"), "8.5")


@pytest.mark.asyncio
async def test_auto_create_leaves_clause_tokens_null_when_the_question_is_unmapped(
    monkeypatch: pytest.MonkeyPatch,
):
    question = AuditQuestion(
        id=42,
        template_id=5,
        question_text="Unmapped question",
        question_type="yes_no",
        is_active=True,
    )
    run = SimpleNamespace(
        id=7,
        tenant_id=3,
        template_id=5,
        findings=[],
        responses=[_failing_response(question.id)],
        assurance_scheme=None,
        external_reference=None,
        external_body_name=None,
    )
    added: list = []
    service = AuditService(
        db=SimpleNamespace(
            execute=AsyncMock(return_value=_QuestionResult([question])),
            add=added.append,
            flush=AsyncMock(),
        )
    )
    service._ensure_action_for_finding = AsyncMock(return_value=None)  # type: ignore[method-assign]
    service._ensure_risk_for_finding = AsyncMock(return_value=None)  # type: ignore[method-assign]
    monkeypatch.setattr(
        "src.domain.services.audit_service.ReferenceNumberService.generate",
        AsyncMock(return_value="FND-2026-0002"),
    )

    await service._auto_generate_findings_actions_and_risks(
        run=run,
        template=SimpleNamespace(auto_create_findings=True),
        actor_user_id=1,
    )

    assert len(added) == 1
    assert added[0].clause_ids_json_legacy is None
