"""PX-054 — assessment create/execute 500 + phantom drafts + DELETE 405."""

from __future__ import annotations

import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from src.api.routes import assessments as assessments_routes
from src.api.routes.assessments import (
    _loaded_collection,
    _to_assessment_run_response,
    create_assessment_run,
    delete_assessment_run,
    start_assessment,
)
from src.api.schemas.assessment import AssessmentRunCreate
from src.domain.models.assessment import AssessmentStatus


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


def test_loaded_collection_does_not_touch_unloaded_relationship():
    """Simulate an ORM instance where responses is not in __dict__ (unloaded)."""

    class _Run:
        def __init__(self):
            # Intentionally omit responses from __dict__; a property would raise
            # if accessed (standing in for MissingGreenlet).
            self.id = "r1"

        @property
        def responses(self):
            raise RuntimeError("lazy load would raise MissingGreenlet")

    assert _loaded_collection(_Run(), "responses") == []


def test_to_assessment_run_response_serializes_without_lazy_responses():
    now = datetime.now(timezone.utc)
    run = types.SimpleNamespace(
        id="run-1",
        reference_number="ASM-2026-0001",
        template_id=10,
        template_version=1,
        engineer_id=11,
        supervisor_id=7,
        asset_type_id=None,
        asset_id=None,
        title="Probe",
        location=None,
        notes=None,
        latitude=None,
        longitude=None,
        status=AssessmentStatus.DRAFT,
        scheduled_date=None,
        started_at=None,
        completed_at=None,
        outcome=None,
        overall_notes=None,
        debrief_notes=None,
        debrief_signature=None,
        debrief_signed_at=None,
        tenant_id=1,
        created_at=now,
        updated_at=now,
    )
    # responses absent from __dict__ — must not raise
    payload = _to_assessment_run_response(run)
    assert payload.id == "run-1"
    assert payload.reference_number == "ASM-2026-0001"
    assert payload.responses == []
    assert payload.status == "draft"


@pytest.mark.asyncio
async def test_create_assessment_run_rolls_back_when_serialize_fails(monkeypatch):
    monkeypatch.setattr(
        "src.api.routes.assessments._generate_assessment_reference_number",
        AsyncMock(return_value="ASM-2026-0099"),
    )
    monkeypatch.setattr(
        "src.api.routes.assessments.GovernanceService.validate_supervisor",
        AsyncMock(return_value={"valid": True, "reason": None}),
    )
    monkeypatch.setattr(
        "src.api.routes.assessments.GovernanceService.check_template_approval",
        AsyncMock(return_value={"approved": True, "reason": None}),
    )
    monkeypatch.setattr(
        "src.api.routes.assessments._to_assessment_run_response",
        lambda *_a, **_k: (_ for _ in ()).throw(RuntimeError("serialize boom")),
    )

    db = types.SimpleNamespace(
        add=lambda _run: None,
        flush=AsyncMock(),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    user = types.SimpleNamespace(id=7, tenant_id=1)

    with pytest.raises(RuntimeError, match="serialize boom"):
        await create_assessment_run(
            AssessmentRunCreate(template_id=10, engineer_id=11),
            db,
            user,
        )

    db.flush.assert_awaited()
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_create_assessment_run_maps_integrity_error_to_422(monkeypatch):
    monkeypatch.setattr(
        "src.api.routes.assessments._generate_assessment_reference_number",
        AsyncMock(return_value="ASM-2026-0100"),
    )
    monkeypatch.setattr(
        "src.api.routes.assessments.GovernanceService.validate_supervisor",
        AsyncMock(return_value={"valid": True, "reason": None}),
    )
    monkeypatch.setattr(
        "src.api.routes.assessments.GovernanceService.check_template_approval",
        AsyncMock(return_value={"approved": True, "reason": None}),
    )

    db = types.SimpleNamespace(
        add=lambda _run: None,
        flush=AsyncMock(
            side_effect=IntegrityError("insert", {}, Exception("FOREIGN KEY constraint failed: engineer_id"))
        ),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    user = types.SimpleNamespace(id=7, tenant_id=1)

    with pytest.raises(HTTPException) as exc:
        await create_assessment_run(
            AssessmentRunCreate(template_id=10, engineer_id=99999),
            db,
            user,
        )

    assert exc.value.status_code == 422
    assert exc.value.detail["code"] == "VALIDATION_ERROR"
    db.commit.assert_not_awaited()
    db.rollback.assert_awaited()


@pytest.mark.asyncio
async def test_create_assessment_run_validation_failures_are_422(monkeypatch):
    monkeypatch.setattr(
        "src.api.routes.assessments.GovernanceService.validate_supervisor",
        AsyncMock(return_value={"valid": False, "reason": "Not a supervisor"}),
    )
    db = types.SimpleNamespace(add=lambda _r: None, flush=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock())
    user = types.SimpleNamespace(id=7, tenant_id=1)

    with pytest.raises(HTTPException) as exc:
        await create_assessment_run(AssessmentRunCreate(template_id=10, engineer_id=11), db, user)

    assert exc.value.status_code == 422
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_start_assessment_commits_serialized_payload(monkeypatch):
    now = datetime.now(timezone.utc)
    run = types.SimpleNamespace(
        id="run-1",
        reference_number="ASM-2026-0001",
        template_id=1,
        template_version=1,
        engineer_id=10,
        supervisor_id=2,
        asset_type_id=None,
        asset_id=None,
        title=None,
        location=None,
        notes=None,
        latitude=None,
        longitude=None,
        status=AssessmentStatus.DRAFT,
        scheduled_date=None,
        started_at=None,
        completed_at=None,
        outcome=None,
        overall_notes=None,
        debrief_notes=None,
        debrief_signature=None,
        debrief_signed_at=None,
        responses=[],
        tenant_id=1,
        created_at=now,
        updated_at=now,
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(run)),
        flush=AsyncMock(),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    user = types.SimpleNamespace(id=2, tenant_id=1, roles=[types.SimpleNamespace(name="supervisor")])
    monkeypatch.setattr(assessments_routes, "_assert_assessment_access", AsyncMock())
    monkeypatch.setattr(
        assessments_routes,
        "enforce_competency_gate_on_start",
        AsyncMock(return_value=None),
    )

    result = await start_assessment("run-1", db, user)

    assert result.status == "in_progress"
    assert result.started_at is not None
    db.flush.assert_awaited()
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_delete_assessment_run_soft_cancels(monkeypatch):
    run = types.SimpleNamespace(id="run-1", supervisor_id=7, status=AssessmentStatus.DRAFT)
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(run)),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    user = types.SimpleNamespace(id=7, tenant_id=1, is_superuser=False, roles=[])
    monkeypatch.setattr(assessments_routes, "_assert_assessment_access", AsyncMock())

    result = await delete_assessment_run("run-1", db, user)

    assert result is None
    assert run.status == AssessmentStatus.CANCELLED
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_delete_assessment_run_idempotent_when_already_cancelled(monkeypatch):
    run = types.SimpleNamespace(id="run-1", supervisor_id=7, status=AssessmentStatus.CANCELLED)
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(run)),
        commit=AsyncMock(),
        rollback=AsyncMock(),
    )
    user = types.SimpleNamespace(id=7, tenant_id=1, is_superuser=True, roles=[])
    monkeypatch.setattr(assessments_routes, "_assert_assessment_access", AsyncMock())

    result = await delete_assessment_run("run-1", db, user)

    assert result is None
    db.commit.assert_not_awaited()
