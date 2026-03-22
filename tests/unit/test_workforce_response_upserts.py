import types
from unittest.mock import AsyncMock, Mock

import pytest

from src.api.routes.assessments import create_assessment_response
from src.api.routes.inductions import create_induction_response
from src.domain.models.assessment import AssessmentStatus, CompetencyVerdict
from src.domain.models.induction import InductionStatus, UnderstandingVerdict
from src.api.schemas.assessment import AssessmentResponseCreate
from src.api.schemas.induction import InductionResponseCreate


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_create_assessment_response_updates_existing_response():
    run = types.SimpleNamespace(id="asm-run-1", supervisor_id=42, template_id=501, status=AssessmentStatus.IN_PROGRESS)
    existing = types.SimpleNamespace(
        id="resp-1",
        run_id="asm-run-1",
        question_id=55,
        verdict=CompetencyVerdict.COMPETENT,
        feedback="old feedback",
        supervisor_notes="old notes",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(run), _FakeResult(existing)]),
        scalar=AsyncMock(return_value=55),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])
    payload = AssessmentResponseCreate(
        question_id=55,
        verdict="not_competent",
        feedback="new feedback",
        supervisor_notes="new notes",
    )

    result = await create_assessment_response("asm-run-1", payload, db, user)

    assert result.id == "resp-1"
    assert existing.verdict == CompetencyVerdict.NOT_COMPETENT
    assert existing.feedback == "new feedback"
    assert existing.supervisor_notes == "new notes"
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_induction_response_updates_existing_response():
    run = types.SimpleNamespace(id="ind-run-1", supervisor_id=42, template_id=601, status=InductionStatus.IN_PROGRESS)
    existing = types.SimpleNamespace(
        id="resp-2",
        run_id="ind-run-1",
        question_id=77,
        shown_explained=False,
        understanding=UnderstandingVerdict.COMPETENT,
        supervisor_notes="old notes",
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(run), _FakeResult(existing)]),
        scalar=AsyncMock(return_value=77),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])
    payload = InductionResponseCreate(
        question_id=77,
        shown_explained=True,
        understanding="not_yet_competent",
        supervisor_notes="new notes",
    )

    result = await create_induction_response("ind-run-1", payload, db, user)

    assert result.id == "resp-2"
    assert existing.shown_explained is True
    assert existing.understanding == UnderstandingVerdict.NOT_YET_COMPETENT
    assert existing.supervisor_notes == "new notes"
    db.add.assert_not_called()
