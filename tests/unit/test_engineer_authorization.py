import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.api.routes.engineers import get_engineer, list_engineers, update_engineer
from src.api.schemas.engineer import EngineerUpdate
from src.domain.exceptions import AuthorizationError


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value


@pytest.mark.asyncio
async def test_get_engineer_allows_self_read():
    engineer = types.SimpleNamespace(
        id=10,
        user_id=42,
        external_id="eng-1",
        employee_number=None,
        job_title=None,
        department=None,
        site=None,
        start_date=None,
        specialisations_json=None,
        certifications_json=None,
        is_active=True,
        notes=None,
        tenant_id=1,
        competency_records=[],
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(engineer)))
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    result = await get_engineer(10, db, user)

    assert result.id == 10


@pytest.mark.asyncio
async def test_update_engineer_denies_non_manager_user():
    engineer = types.SimpleNamespace(id=10, user_id=99)
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(engineer)),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(AuthorizationError) as exc_info:
        await update_engineer(10, EngineerUpdate(notes="test"), db, user)

    assert exc_info.value.http_status == 403
    assert exc_info.value.code == "PERMISSION_DENIED"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_engineers_scopes_non_manager_to_self():
    engineer = types.SimpleNamespace(
        id=10,
        user_id=42,
        external_id="eng-1",
        employee_number=None,
        job_title=None,
        department=None,
        site=None,
        start_date=None,
        specialisations_json=None,
        certifications_json=None,
        is_active=True,
        notes=None,
        tenant_id=1,
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    db = types.SimpleNamespace(
        scalar=AsyncMock(return_value=1),
        execute=AsyncMock(return_value=_FakeResult([engineer])),
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    result = await list_engineers(db, user, page=1, page_size=20)

    assert result.total == 1
    assert len(result.items) == 1
    assert result.items[0].user_id == 42


@pytest.mark.asyncio
async def test_skills_matrix_uses_latest_record_per_asset_type():
    from src.api.routes.engineers import get_skills_matrix
    from src.domain.models.engineer import CompetencyLifecycleState

    engineer = types.SimpleNamespace(id=10, user_id=42)
    older = types.SimpleNamespace(
        id=1,
        engineer_id=10,
        asset_type_id=7,
        template_id=100,
        state=CompetencyLifecycleState.FAILED,
        outcome="fail",
        assessed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        expires_at=None,
    )
    newer = types.SimpleNamespace(
        id=2,
        engineer_id=10,
        asset_type_id=7,
        template_id=100,
        state=CompetencyLifecycleState.ACTIVE,
        outcome="pass",
        assessed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        expires_at=None,
    )
    asset_type = types.SimpleNamespace(id=7, name="Transformer")
    db = types.SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _FakeResult(engineer),
                _FakeResult([older, newer]),
                _FakeResult([asset_type]),
            ]
        )
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    result = await get_skills_matrix(10, db, user)

    assert len(result.matrix) == 1
    assert result.matrix[0].asset_type_id == 7
    assert result.matrix[0].state == "active"
    assert result.matrix[0].outcome == "pass"


@pytest.mark.asyncio
async def test_skills_matrix_uses_effective_expired_state():
    from src.api.routes.engineers import get_skills_matrix
    from src.domain.models.engineer import CompetencyLifecycleState

    engineer = types.SimpleNamespace(id=10, user_id=42)
    expired_active = types.SimpleNamespace(
        id=3,
        engineer_id=10,
        asset_type_id=7,
        template_id=100,
        state=CompetencyLifecycleState.ACTIVE,
        outcome="pass",
        assessed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        expires_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    asset_type = types.SimpleNamespace(id=7, name="Transformer")
    db = types.SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _FakeResult(engineer),
                _FakeResult([expired_active]),
                _FakeResult([asset_type]),
            ]
        )
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    result = await get_skills_matrix(10, db, user)

    assert len(result.matrix) == 1
    assert result.matrix[0].state == "expired"


@pytest.mark.asyncio
async def test_skills_matrix_applies_tenant_scope_to_asset_types():
    from src.api.routes.engineers import get_skills_matrix
    from src.domain.models.engineer import CompetencyLifecycleState

    engineer = types.SimpleNamespace(id=10, user_id=42)
    record = types.SimpleNamespace(
        id=3,
        engineer_id=10,
        asset_type_id=7,
        template_id=100,
        state=CompetencyLifecycleState.ACTIVE,
        outcome="pass",
        assessed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        expires_at=None,
    )
    asset_type = types.SimpleNamespace(id=7, name="Transformer")
    db = types.SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _FakeResult(engineer),
                _FakeResult([record]),
                _FakeResult([asset_type]),
            ]
        )
    )
    user = types.SimpleNamespace(id=42, tenant_id=5, is_superuser=False, roles=[])

    await get_skills_matrix(10, db, user)

    asset_type_query = db.execute.await_args_list[2].args[0]
    assert "asset_types.tenant_id" in str(asset_type_query)
