import types
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.routes.assessments import complete_assessment, update_assessment_response
from src.api.routes.inductions import complete_induction, update_induction_response
from src.api.schemas.assessment import AssessmentResponseUpdate
from src.api.schemas.induction import InductionResponseUpdate
from src.domain.models.assessment import AssessmentStatus, CompetencyVerdict
from src.domain.models.induction import InductionStatus


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_complete_assessment_rejects_empty_responses():
    run = types.SimpleNamespace(
        id="asm-run-001",
        supervisor_id=42,
        template_id=10,
        status=AssessmentStatus.DRAFT,
        responses=[],
    )
    template = types.SimpleNamespace(questions=[])
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(run), _FakeResult(template)]),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await complete_assessment("asm-run-001", db, user)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "VALIDATION_ERROR"
    assert exc.value.detail["details"]["scorable_items"] == 0
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_assessment_rejects_all_na_responses():
    response = types.SimpleNamespace(
        question_id=101,
        verdict=CompetencyVerdict.NA,
        feedback="Not applicable",
    )
    run = types.SimpleNamespace(
        id="asm-run-002",
        supervisor_id=42,
        template_id=10,
        status=AssessmentStatus.IN_PROGRESS,
        responses=[response],
    )
    template = types.SimpleNamespace(questions=[types.SimpleNamespace(id=101, criticality="good_to_have")])
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(run), _FakeResult(template)]),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await complete_assessment("asm-run-002", db, user)

    assert exc.value.status_code == 400
    assert exc.value.detail["details"]["response_count"] == 1
    assert exc.value.detail["details"]["scorable_items"] == 0
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_assessment_response_rejects_completed_run():
    response = types.SimpleNamespace(id="resp-1", run_id="asm-run-003")
    run = types.SimpleNamespace(id="asm-run-003", supervisor_id=42, status=AssessmentStatus.COMPLETED)
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(response), _FakeResult(run)]),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await update_assessment_response("resp-1", AssessmentResponseUpdate(feedback="late edit"), db, user)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "INVALID_STATE_TRANSITION"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_induction_response_rejects_completed_run():
    response = types.SimpleNamespace(id="resp-2", run_id="ind-run-003")
    run = types.SimpleNamespace(id="ind-run-003", supervisor_id=42, status=InductionStatus.COMPLETED)
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(response), _FakeResult(run)]),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await update_induction_response("resp-2", InductionResponseUpdate(supervisor_notes="late edit"), db, user)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "INVALID_STATE_TRANSITION"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_assessment_rejects_missing_template_answers():
    response = types.SimpleNamespace(
        question_id=101,
        verdict=CompetencyVerdict.COMPETENT,
        feedback="done",
    )
    run = types.SimpleNamespace(
        id="asm-run-004",
        supervisor_id=42,
        template_id=10,
        status=AssessmentStatus.IN_PROGRESS,
        responses=[response],
    )
    template = types.SimpleNamespace(
        questions=[
            types.SimpleNamespace(id=101, is_active=True, criticality="good_to_have"),
            types.SimpleNamespace(id=102, is_active=True, criticality="good_to_have"),
        ]
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(run), _FakeResult(template)]),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await complete_assessment("asm-run-004", db, user)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "VALIDATION_ERROR"
    assert exc.value.detail["details"]["missing_question_ids"] == [102]
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_induction_rejects_missing_template_answers():
    response = types.SimpleNamespace(
        question_id=101,
        understanding="competent",
        supervisor_notes="done",
    )
    run = types.SimpleNamespace(
        id="ind-run-004",
        supervisor_id=42,
        template_id=10,
        status=InductionStatus.IN_PROGRESS,
        responses=[response],
    )
    template = types.SimpleNamespace(
        questions=[
            types.SimpleNamespace(id=101, is_active=True),
            types.SimpleNamespace(id=102, is_active=True),
        ]
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(run), _FakeResult(template)]),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await complete_induction("ind-run-004", db, user)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "VALIDATION_ERROR"
    assert exc.value.detail["details"]["missing_question_ids"] == [102]
    db.commit.assert_not_awaited()
