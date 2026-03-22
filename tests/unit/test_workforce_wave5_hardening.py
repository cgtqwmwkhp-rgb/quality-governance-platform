import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from src.api.routes.assessments import create_assessment_response, get_assessment_run, update_assessment_response
from src.api.routes.inductions import create_induction_response, get_induction_run, update_induction_response
from src.api.schemas.assessment import AssessmentResponseCreate, AssessmentResponseUpdate
from src.api.schemas.induction import InductionResponseCreate, InductionResponseUpdate
from src.domain.models.assessment import AssessmentStatus
from src.domain.models.induction import InductionStatus
from src.domain.services.governance_service import GovernanceService


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_validate_supervisor_rejects_null_tenant_supervisor_for_tenant_run():
    engineer = types.SimpleNamespace(id=8, user_id=99, tenant_id=7)
    supervisor = types.SimpleNamespace(
        id=42,
        tenant_id=None,
        is_active=True,
        is_superuser=False,
        roles=[types.SimpleNamespace(name="supervisor")],
    )
    db = types.SimpleNamespace(execute=AsyncMock(side_effect=[_FakeResult(engineer), _FakeResult(supervisor)]))

    result = await GovernanceService.validate_supervisor(db, supervisor_id=42, engineer_id=8, tenant_id=7)

    assert result == {"valid": False, "reason": "Supervisor not in tenant scope"}


@pytest.mark.asyncio
async def test_validate_supervisor_allows_superuser_override_for_tenant_run():
    engineer = types.SimpleNamespace(id=8, user_id=99, tenant_id=7)
    supervisor = types.SimpleNamespace(
        id=42,
        tenant_id=None,
        is_active=True,
        is_superuser=True,
        roles=[],
    )
    db = types.SimpleNamespace(execute=AsyncMock(side_effect=[_FakeResult(engineer), _FakeResult(supervisor)]))

    result = await GovernanceService.validate_supervisor(db, supervisor_id=42, engineer_id=8, tenant_id=7)

    assert result == {"valid": True, "reason": None}


@pytest.mark.asyncio
async def test_create_assessment_response_persists_run_tenant(monkeypatch):
    run = types.SimpleNamespace(
        id="asm-run-1",
        template_id=10,
        status=AssessmentStatus.IN_PROGRESS,
        tenant_id=7,
        engineer_id=12,
        supervisor_id=42,
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(run), _FakeResult(None)]),
        scalar=AsyncMock(return_value=101),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=7, is_superuser=False, roles=[])
    monkeypatch.setattr("src.api.routes.assessments._assert_assessment_access", AsyncMock())
    monkeypatch.setattr(
        "src.api.routes.assessments.AssessmentResponseResponse.model_validate",
        lambda response: response,
    )

    result = await create_assessment_response(
        "asm-run-1",
        AssessmentResponseCreate(question_id=101, verdict="competent", feedback="ok"),
        db,
        user,
    )

    assert result.tenant_id == 7


@pytest.mark.asyncio
async def test_update_assessment_response_allows_engineer_signature_only(monkeypatch):
    timestamp = datetime.now(timezone.utc)
    response = types.SimpleNamespace(id="resp-1", run_id="asm-run-2", tenant_id=None)
    run = types.SimpleNamespace(
        id="asm-run-2", engineer_id=12, supervisor_id=42, status=AssessmentStatus.IN_PROGRESS, tenant_id=7
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(response), _FakeResult(run)]),
        scalar=AsyncMock(return_value=55),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=55, tenant_id=7, is_superuser=False, roles=[])
    monkeypatch.setattr(
        "src.api.routes.assessments.AssessmentResponseResponse.model_validate",
        lambda updated: updated,
    )

    result = await update_assessment_response(
        "resp-1",
        AssessmentResponseUpdate(engineer_signature="signed", engineer_signed_at=timestamp),
        db,
        user,
    )

    assert result.engineer_signature == "signed"
    assert result.engineer_signed_at == timestamp
    assert result.tenant_id == 7


@pytest.mark.asyncio
async def test_update_assessment_response_rejects_engineer_verdict_changes():
    response = types.SimpleNamespace(id="resp-1", run_id="asm-run-2", tenant_id=None)
    run = types.SimpleNamespace(
        id="asm-run-2", engineer_id=12, supervisor_id=42, status=AssessmentStatus.IN_PROGRESS, tenant_id=7
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(response), _FakeResult(run)]),
        scalar=AsyncMock(return_value=55),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=55, tenant_id=7, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await update_assessment_response(
            "resp-1",
            AssessmentResponseUpdate(verdict="competent"),
            db,
            user,
        )

    assert exc.value.status_code == 403
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_induction_response_persists_run_tenant(monkeypatch):
    run = types.SimpleNamespace(
        id="ind-run-1",
        template_id=10,
        status=InductionStatus.IN_PROGRESS,
        tenant_id=7,
        engineer_id=12,
        supervisor_id=42,
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(run), _FakeResult(None)]),
        scalar=AsyncMock(return_value=101),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=7, is_superuser=False, roles=[])
    monkeypatch.setattr("src.api.routes.inductions._assert_induction_access", AsyncMock())
    monkeypatch.setattr(
        "src.api.routes.inductions.InductionResponseResponse.model_validate",
        lambda response: response,
    )

    result = await create_induction_response(
        "ind-run-1",
        InductionResponseCreate(question_id=101, shown_explained=True, understanding="competent"),
        db,
        user,
    )

    assert result.tenant_id == 7


@pytest.mark.asyncio
async def test_update_induction_response_allows_engineer_signature_only(monkeypatch):
    timestamp = datetime.now(timezone.utc)
    response = types.SimpleNamespace(id="resp-2", run_id="ind-run-2", tenant_id=None)
    run = types.SimpleNamespace(
        id="ind-run-2", engineer_id=12, supervisor_id=42, status=InductionStatus.IN_PROGRESS, tenant_id=7
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(response), _FakeResult(run)]),
        scalar=AsyncMock(return_value=55),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=55, tenant_id=7, is_superuser=False, roles=[])
    monkeypatch.setattr(
        "src.api.routes.inductions.InductionResponseResponse.model_validate",
        lambda updated: updated,
    )

    result = await update_induction_response(
        "resp-2",
        InductionResponseUpdate(engineer_signature="signed", engineer_signed_at=timestamp),
        db,
        user,
    )

    assert result.engineer_signature == "signed"
    assert result.engineer_signed_at == timestamp
    assert result.tenant_id == 7


@pytest.mark.asyncio
async def test_update_induction_response_rejects_engineer_understanding_changes():
    response = types.SimpleNamespace(id="resp-2", run_id="ind-run-2", tenant_id=None)
    run = types.SimpleNamespace(
        id="ind-run-2", engineer_id=12, supervisor_id=42, status=InductionStatus.IN_PROGRESS, tenant_id=7
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(response), _FakeResult(run)]),
        scalar=AsyncMock(return_value=55),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=55, tenant_id=7, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await update_induction_response(
            "resp-2",
            InductionResponseUpdate(understanding="competent"),
            db,
            user,
        )

    assert exc.value.status_code == 403
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_assessment_run_does_not_lock_read_query(monkeypatch):
    run = types.SimpleNamespace(id="asm-run-3", responses=[])
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(run)))
    user = types.SimpleNamespace(id=42, tenant_id=7, is_superuser=False, roles=[])
    monkeypatch.setattr("src.api.routes.assessments._assert_assessment_access", AsyncMock())
    monkeypatch.setattr("src.api.routes.assessments.AssessmentRunResponse.model_validate", lambda run_obj: run_obj)

    await get_assessment_run("asm-run-3", db, user)

    assert "FOR UPDATE" not in str(db.execute.await_args.args[0])


@pytest.mark.asyncio
async def test_get_induction_run_does_not_lock_read_query(monkeypatch):
    run = types.SimpleNamespace(id="ind-run-3", responses=[])
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(run)))
    user = types.SimpleNamespace(id=42, tenant_id=7, is_superuser=False, roles=[])
    monkeypatch.setattr("src.api.routes.inductions._assert_induction_access", AsyncMock())
    monkeypatch.setattr("src.api.routes.inductions.InductionRunResponse.model_validate", lambda run_obj: run_obj)

    await get_induction_run("ind-run-3", db, user)

    assert "FOR UPDATE" not in str(db.execute.await_args.args[0])
