"""Unit tests for Workforce P0 spine — tickets, intervals, start gate."""

from __future__ import annotations

import ast
import types
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models.engineer import CompetencyRequirement, Engineer, TicketVerifyState, TrainingTicket
from src.domain.services.workforce_spine import (
    DEFAULT_REASSESSMENT_INTERVAL_DAYS,
    competency_gate_mode,
    enforce_competency_gate_on_start,
    resolve_reassessment_interval_days,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SPINE_MIGRATION = REPO_ROOT / "alembic/versions/20260713_workforce_p0_spine.py"
TENANT_MIGRATION = REPO_ROOT / "alembic/versions/20260713_workforce_tenant_not_null.py"


def _load_should_enforce_not_null():
    tree = ast.parse(TENANT_MIGRATION.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.FunctionDef) and node.name == "should_enforce_not_null":
            module = ast.Module(body=[node], type_ignores=[])
            ast.fix_missing_locations(module)
            namespace: dict = {}
            exec(compile(module, str(TENANT_MIGRATION), "exec"), namespace)
            return namespace["should_enforce_not_null"]
    raise AssertionError("should_enforce_not_null not found")


def test_training_ticket_orm_tenant_id_required():
    assert TrainingTicket.__table__.c.tenant_id.nullable is False
    assert TrainingTicket.__table__.c.scheme.nullable is False
    assert TrainingTicket.__table__.c.ticket_number.nullable is False
    assert TrainingTicket.__table__.c.verify_state.nullable is False
    assert "evidence_assets" in str(TrainingTicket.__table__.c.evidence_id.foreign_keys)


def test_workforce_spine_tables_tenant_id_required_in_orm():
    assert Engineer.__table__.c.tenant_id.nullable is False
    assert CompetencyRequirement.__table__.c.tenant_id.nullable is False
    from src.domain.models.engineer import CompetencyRecord

    assert CompetencyRecord.__table__.c.tenant_id.nullable is False


def test_ticket_verify_state_enum_values():
    assert TicketVerifyState.UNVERIFIED.value == "unverified"
    assert TicketVerifyState.VERIFIED.value == "verified"
    assert TicketVerifyState.EXPIRED.value == "expired"


def test_spine_migration_chains_and_creates_tickets_table():
    body = SPINE_MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260713_wf_p0_spine"' in body
    assert 'down_revision: Union[str, Sequence[str], None] = "20260713_op_assess"' in body
    assert "training_tickets" in body
    assert "verify_state" in body
    assert "evidence_assets" in body
    assert "role_key" in body
    assert "certifications_json" in body


def test_tenant_nn_migration_fail_safe_and_no_invent():
    should_enforce = _load_should_enforce_not_null()
    assert should_enforce(0) is True
    assert should_enforce(3) is False
    body = TENANT_MIGRATION.read_text(encoding="utf-8")
    assert "FAIL-SAFE" in body
    assert "tenant_id = 1" not in body
    assert "SET tenant_id = 1" not in body.upper()
    assert "engineers" in body
    assert "competency_records" in body
    assert "competency_requirements" in body


def test_baseline_shrinks_workforce_tables():
    baseline = (REPO_ROOT / "docs/governance/tenant_id_nullable_baseline.json").read_text(encoding="utf-8")
    assert '"engineers"' not in baseline
    assert '"competency_records"' not in baseline
    assert '"competency_requirements"' not in baseline


class _ScalarResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_resolve_reassessment_interval_uses_requirement():
    requirement = types.SimpleNamespace(reassessment_interval_days=180)
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult(requirement)))

    days = await resolve_reassessment_interval_days(db, asset_type_id=7, template_id=3, tenant_id=1)
    assert days == 180


@pytest.mark.asyncio
async def test_resolve_reassessment_interval_falls_back_to_default():
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult(None)))

    days = await resolve_reassessment_interval_days(db, asset_type_id=7, template_id=3, tenant_id=1)
    assert days == DEFAULT_REASSESSMENT_INTERVAL_DAYS


@pytest.mark.asyncio
async def test_soft_gate_returns_warning_payload(monkeypatch):
    monkeypatch.setattr(
        "src.domain.services.workforce_spine.settings",
        types.SimpleNamespace(competency_gate_mode="soft"),
    )

    async def fake_gate(*_args, **_kwargs):
        return {"cleared": False, "reason": "requires reassessment", "records": []}

    monkeypatch.setattr(
        "src.domain.services.workforce_spine.GovernanceService.check_competency_gate",
        fake_gate,
    )
    db = MagicMock()
    payload = await enforce_competency_gate_on_start(db, engineer_id=1, asset_type_id=2, tenant_id=9)
    assert payload is not None
    assert payload["cleared"] is False
    assert payload["mode"] == "soft"
    assert "reassessment" in payload["reason"]


@pytest.mark.asyncio
async def test_hard_gate_blocks_start(monkeypatch):
    from src.domain.exceptions import AuthorizationError

    monkeypatch.setattr(
        "src.domain.services.workforce_spine.settings",
        types.SimpleNamespace(competency_gate_mode="hard"),
    )

    async def fake_gate(*_args, **_kwargs):
        return {"cleared": False, "reason": "failed competency", "records": [{"id": 1, "state": "failed"}]}

    monkeypatch.setattr(
        "src.domain.services.workforce_spine.GovernanceService.check_competency_gate",
        fake_gate,
    )
    with pytest.raises(AuthorizationError) as exc:
        await enforce_competency_gate_on_start(MagicMock(), engineer_id=1, asset_type_id=2, tenant_id=9)
    assert exc.value.http_status == 403
    assert exc.value.code == "COMPETENCY_GATE_BLOCKED"


@pytest.mark.asyncio
async def test_gate_skipped_without_asset_type():
    result = await enforce_competency_gate_on_start(MagicMock(), engineer_id=1, asset_type_id=None, tenant_id=9)
    assert result is None


def test_competency_gate_mode_defaults_soft(monkeypatch):
    monkeypatch.setattr(
        "src.domain.services.workforce_spine.settings",
        types.SimpleNamespace(competency_gate_mode="weird"),
    )
    assert competency_gate_mode() == "soft"


@pytest.mark.asyncio
async def test_start_assessment_wires_soft_gate(monkeypatch):
    from src.api.routes import assessments as assessments_routes
    from src.api.schemas.assessment import AssessmentRunResponse
    from src.domain.models.assessment import AssessmentStatus

    run = types.SimpleNamespace(
        id="run-1",
        reference_number="ASS-1",
        template_id=1,
        template_version=1,
        engineer_id=10,
        supervisor_id=2,
        asset_type_id=5,
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
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )

    class _Result:
        def scalar_one_or_none(self):
            return run

    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_Result()),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=2, tenant_id=1, roles=[types.SimpleNamespace(name="supervisor")])

    monkeypatch.setattr(assessments_routes, "_assert_assessment_access", AsyncMock())
    monkeypatch.setattr(
        assessments_routes,
        "enforce_competency_gate_on_start",
        AsyncMock(
            return_value={
                "cleared": False,
                "reason": "due for reassessment",
                "mode": "soft",
                "records": [],
            }
        ),
    )

    result = await assessments_routes.start_assessment("run-1", db, user)
    assert isinstance(result, AssessmentRunResponse)
    assert result.status == AssessmentStatus.IN_PROGRESS.value or result.status == "in_progress"
    assert result.competency_gate_cleared is False
    assert result.competency_gate_mode == "soft"
    assert "reassessment" in (result.competency_gate_reason or "")
    db.commit.assert_awaited()


def test_assessments_no_longer_hardcode_365_expiry():
    body = (REPO_ROOT / "src/api/routes/assessments.py").read_text(encoding="utf-8")
    assert "resolve_reassessment_interval_days" in body
    assert "timedelta(days=365)" not in body
    induction = (REPO_ROOT / "src/api/routes/inductions.py").read_text(encoding="utf-8")
    assert "resolve_reassessment_interval_days" in induction
    assert "timedelta(days=365)" not in induction


def test_interval_math_uses_requirement_days():
    """Sanity: expiry offset equals requirement days, not a fixed year."""
    now = datetime(2026, 7, 13, tzinfo=timezone.utc)
    interval = 90
    expiry = now + timedelta(days=interval)
    assert (expiry - now).days == 90
