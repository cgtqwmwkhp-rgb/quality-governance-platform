import types
from unittest.mock import AsyncMock, Mock

import pytest

from src.api.routes.assessments import complete_assessment
from src.domain.models.assessment import AssessmentStatus, CompetencyVerdict
from src.domain.models.engineer import CompetencyLifecycleState
from src.domain.services.capa_auto_service import CAPAAutoService


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_complete_assessment_reuses_existing_competency_record(monkeypatch):
    response = types.SimpleNamespace(
        question_id=101,
        verdict=CompetencyVerdict.COMPETENT,
        feedback="done",
    )
    existing_competency = types.SimpleNamespace(
        engineer_id=9,
        asset_type_id=5,
        template_id=8,
        source_type="assessment",
        source_run_id="asm-run-5",
        state=CompetencyLifecycleState.FAILED,
        outcome="fail",
        assessed_at=None,
        assessed_by_id=None,
        expires_at=None,
        tenant_id=1,
    )
    run = types.SimpleNamespace(
        id="asm-run-5",
        reference_number="ASM-2026-0005",
        supervisor_id=42,
        engineer_id=9,
        template_id=8,
        template_version=1,
        asset_type_id=5,
        asset_id=None,
        title="Assessment",
        location=None,
        notes=None,
        status=AssessmentStatus.IN_PROGRESS,
        scheduled_date=None,
        started_at=None,
        completed_at=None,
        outcome=None,
        overall_notes=None,
        debrief_notes=None,
        debrief_signature=None,
        debrief_signed_at=None,
        tenant_id=1,
        responses=[response],
        created_at=None,
        updated_at=None,
    )
    template = types.SimpleNamespace(
        questions=[types.SimpleNamespace(id=101, is_active=True, criticality="good_to_have")]
    )
    engineer = types.SimpleNamespace(id=9, user_id=77)
    db = types.SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _FakeResult(run),
                _FakeResult(template),
                _FakeResult(engineer),
                _FakeResult(existing_competency),
            ]
        ),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    monkeypatch.setattr(
        "src.api.routes.assessments._assert_assessment_access",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "src.api.routes.assessments.CompetencyScoringService.score_assessment",
        lambda responses, questions: types.SimpleNamespace(outcome="pass", scorable_items=1),
    )
    monkeypatch.setattr(
        "src.api.routes.assessments.NotificationService.notify_assessment_complete",
        AsyncMock(),
    )
    monkeypatch.setattr(
        "src.api.routes.assessments.AssessmentRunResponse.model_validate",
        lambda run_obj: run_obj,
    )

    result = await complete_assessment("asm-run-5", db, user)

    assert result is run
    assert existing_competency.state == CompetencyLifecycleState.ACTIVE
    assert existing_competency.outcome == "pass"
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_capa_auto_service_skips_existing_assessment_action():
    existing_action = types.SimpleNamespace(reference_number="CAPA-2026-0001")
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(existing_action)),
        add=Mock(),
    )

    created = await CAPAAutoService.create_from_assessment(
        db=db,
        assessment_run_id="asm-run-6",
        engineer_id=9,
        supervisor_id=42,
        outcome="fail",
        failed_questions=[
            {
                "question_id": 101,
                "question_text": "Isolation procedure",
                "criticality": "essential",
                "feedback": "Needs retraining",
            }
        ],
        tenant_id=1,
    )

    assert created == [existing_action]
    db.add.assert_not_called()
