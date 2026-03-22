import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.routes.wdp_analytics import get_engineer_competency_matrix, get_wdp_summary
from src.domain.models.engineer import CompetencyLifecycleState


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def all(self):
        return self._value


@pytest.mark.asyncio
async def test_wdp_summary_denies_non_manager_user():
    db = types.SimpleNamespace()
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await get_wdp_summary(db, user)

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_engineer_matrix_uses_latest_record_per_asset_type():
    older = types.SimpleNamespace(
        id=1,
        asset_type_id=7,
        state=CompetencyLifecycleState.EXPIRED,
        assessed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    newer = types.SimpleNamespace(
        id=2,
        asset_type_id=7,
        state=CompetencyLifecycleState.ACTIVE,
        assessed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    engineer = types.SimpleNamespace(id=10, user_id=42, employee_number="E001")
    asset_type = types.SimpleNamespace(id=7, name="Transformer", category="network")
    db = types.SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _FakeResult([engineer]),
                _FakeResult([asset_type]),
                _FakeResult([older, newer]),
            ]
        )
    )
    user = types.SimpleNamespace(
        id=7,
        tenant_id=1,
        is_superuser=False,
        roles=[types.SimpleNamespace(name="supervisor")],
    )

    result = await get_engineer_competency_matrix(db, user)

    assert len(result["engineers"]) == 1
    assert result["engineers"][0]["competencies"][7] == "active"


@pytest.mark.asyncio
async def test_engineer_matrix_uses_effective_expired_state():
    expired_active = types.SimpleNamespace(
        id=3,
        asset_type_id=7,
        state=CompetencyLifecycleState.ACTIVE,
        assessed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        expires_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    engineer = types.SimpleNamespace(id=10, user_id=42, employee_number="E001")
    asset_type = types.SimpleNamespace(id=7, name="Transformer", category="network")
    db = types.SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _FakeResult([engineer]),
                _FakeResult([asset_type]),
                _FakeResult([expired_active]),
            ]
        )
    )
    user = types.SimpleNamespace(
        id=7,
        tenant_id=1,
        is_superuser=False,
        roles=[types.SimpleNamespace(name="supervisor")],
    )

    result = await get_engineer_competency_matrix(db, user)

    assert result["engineers"][0]["competencies"][7] == "expired"


@pytest.mark.asyncio
async def test_wdp_summary_counts_latest_competency_state_only():
    stale_expired = types.SimpleNamespace(
        id=1,
        engineer_id=10,
        asset_type_id=7,
        state=CompetencyLifecycleState.EXPIRED,
        assessed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    latest_active = types.SimpleNamespace(
        id=2,
        engineer_id=10,
        asset_type_id=7,
        state=CompetencyLifecycleState.ACTIVE,
        assessed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    db = types.SimpleNamespace(
        scalar=AsyncMock(side_effect=[1, 5, 4, 3, 2]),
        execute=AsyncMock(return_value=_FakeResult([stale_expired, latest_active])),
    )
    user = types.SimpleNamespace(
        id=7,
        tenant_id=1,
        is_superuser=False,
        roles=[types.SimpleNamespace(name="supervisor")],
    )

    result = await get_wdp_summary(db, user)

    assert result["engineers"]["total"] == 1
    assert result["competencies"]["active"] == 1
    assert result["competencies"]["expired"] == 0


@pytest.mark.asyncio
async def test_wdp_summary_uses_effective_expired_state():
    expired_active = types.SimpleNamespace(
        id=3,
        engineer_id=10,
        asset_type_id=7,
        state=CompetencyLifecycleState.ACTIVE,
        assessed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        expires_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    db = types.SimpleNamespace(
        scalar=AsyncMock(side_effect=[1, 5, 4, 3, 2]),
        execute=AsyncMock(return_value=_FakeResult([expired_active])),
    )
    user = types.SimpleNamespace(
        id=7,
        tenant_id=1,
        is_superuser=False,
        roles=[types.SimpleNamespace(name="supervisor")],
    )

    result = await get_wdp_summary(db, user)

    assert result["competencies"]["active"] == 0
    assert result["competencies"]["expired"] == 1
