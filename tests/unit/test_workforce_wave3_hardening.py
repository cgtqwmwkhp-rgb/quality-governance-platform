import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError

from src.api.routes.assets import create_asset_type
from src.api.routes.assessments import create_assessment_run
from src.api.routes.inductions import create_induction_run
from src.api.schemas.asset import AssetTypeCreate
from src.api.schemas.assessment import AssessmentRunCreate
from src.api.schemas.induction import InductionRunCreate


def _reference_conflict(table_name: str) -> IntegrityError:
    return IntegrityError(
        statement="insert",
        params={},
        orig=Exception(f"UNIQUE constraint failed: {table_name}.reference_number"),
    )


@pytest.mark.asyncio
async def test_create_asset_type_denies_non_manager_user():
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])
    db = types.SimpleNamespace()

    with pytest.raises(HTTPException) as exc:
        await create_asset_type(
            AssetTypeCreate(category="power", name="Transformer"),
            db,
            user,
        )

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_create_assessment_run_retries_reference_conflict(monkeypatch):
    references = iter(["ASM-2026-0001", "ASM-2026-0002"])

    async def _fake_reference(_db):
        return next(references)

    monkeypatch.setattr(
        "src.api.routes.assessments._generate_assessment_reference_number",
        _fake_reference,
    )
    monkeypatch.setattr(
        "src.api.routes.assessments.GovernanceService.validate_supervisor",
        AsyncMock(return_value={"valid": True, "reason": None}),
    )
    monkeypatch.setattr(
        "src.api.routes.assessments.GovernanceService.check_template_approval",
        AsyncMock(return_value={"approved": True, "reason": None}),
    )

    async def _refresh(run):
        run.id = "assessment-run-1"
        run.template_version = 1
        run.created_at = datetime.now(timezone.utc)
        run.updated_at = datetime.now(timezone.utc)

    db = types.SimpleNamespace(
        add=lambda _: None,
        commit=AsyncMock(side_effect=[_reference_conflict("assessment_runs"), None]),
        refresh=AsyncMock(side_effect=_refresh),
        rollback=AsyncMock(),
    )
    user = types.SimpleNamespace(id=7, tenant_id=1)

    result = await create_assessment_run(
        AssessmentRunCreate(template_id=10, engineer_id=11, scheduled_date=datetime.now(timezone.utc)),
        db,
        user,
    )

    assert result.reference_number == "ASM-2026-0002"
    assert db.rollback.await_count == 1
    assert db.commit.await_count == 2


@pytest.mark.asyncio
async def test_create_induction_run_retries_reference_conflict(monkeypatch):
    references = iter(["IND-2026-0001", "IND-2026-0002"])

    async def _fake_reference(_db):
        return next(references)

    monkeypatch.setattr(
        "src.api.routes.inductions._generate_induction_reference_number",
        _fake_reference,
    )
    monkeypatch.setattr(
        "src.api.routes.inductions.GovernanceService.validate_supervisor",
        AsyncMock(return_value={"valid": True, "reason": None}),
    )
    monkeypatch.setattr(
        "src.api.routes.inductions.GovernanceService.check_template_approval",
        AsyncMock(return_value={"approved": True, "reason": None}),
    )

    async def _refresh(run):
        run.id = "induction-run-1"
        run.template_version = 1
        run.total_items = 0
        run.competent_count = 0
        run.not_yet_competent_count = 0
        run.created_at = datetime.now(timezone.utc)
        run.updated_at = datetime.now(timezone.utc)

    db = types.SimpleNamespace(
        add=lambda _: None,
        commit=AsyncMock(side_effect=[_reference_conflict("induction_runs"), None]),
        refresh=AsyncMock(side_effect=_refresh),
        rollback=AsyncMock(),
    )
    user = types.SimpleNamespace(id=7, tenant_id=1)

    result = await create_induction_run(
        InductionRunCreate(template_id=10, engineer_id=11, scheduled_date=datetime.now(timezone.utc)),
        db,
        user,
    )

    assert result.reference_number == "IND-2026-0002"
    assert db.rollback.await_count == 1
    assert db.commit.await_count == 2
