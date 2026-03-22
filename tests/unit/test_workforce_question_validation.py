import types
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from src.api.routes.assessments import create_assessment_response
from src.api.routes.inductions import create_induction_response
from src.api.schemas.assessment import AssessmentResponseCreate
from src.api.schemas.induction import InductionResponseCreate
from src.domain.models.assessment import AssessmentStatus
from src.domain.models.induction import InductionStatus


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_create_assessment_response_rejects_question_outside_template():
    run = types.SimpleNamespace(
        id="asm-run-010",
        supervisor_id=42,
        template_id=501,
        status=AssessmentStatus.IN_PROGRESS,
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(run)),
        scalar=AsyncMock(return_value=None),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])
    payload = AssessmentResponseCreate(question_id=999, verdict="competent")

    with pytest.raises(HTTPException) as exc:
        await create_assessment_response("asm-run-010", payload, db, user)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "VALIDATION_ERROR"
    assert exc.value.detail["details"]["template_id"] == 501
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_induction_response_rejects_question_outside_template():
    run = types.SimpleNamespace(
        id="ind-run-010",
        supervisor_id=42,
        template_id=601,
        status=InductionStatus.IN_PROGRESS,
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(run)),
        scalar=AsyncMock(return_value=None),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])
    payload = InductionResponseCreate(question_id=999, shown_explained=True, understanding="competent")

    with pytest.raises(HTTPException) as exc:
        await create_induction_response("ind-run-010", payload, db, user)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "VALIDATION_ERROR"
    assert exc.value.detail["details"]["template_id"] == 601
    db.add.assert_not_called()
    db.commit.assert_not_awaited()
