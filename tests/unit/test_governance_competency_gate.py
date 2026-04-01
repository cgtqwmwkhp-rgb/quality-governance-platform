import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.domain.models.engineer import CompetencyLifecycleState
from src.domain.services.governance_service import GovernanceService


class _ScalarResult:
    def __init__(self, values):
        self._values = values

    def scalars(self):
        return self

    def all(self):
        return self._values


@pytest.mark.asyncio
async def test_competency_gate_uses_latest_record_not_stale_failure():
    older_failed = types.SimpleNamespace(
        id=1,
        state=CompetencyLifecycleState.FAILED,
        assessed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    newer_active = types.SimpleNamespace(
        id=2,
        state=CompetencyLifecycleState.ACTIVE,
        assessed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult([older_failed, newer_active])))

    result = await GovernanceService.check_competency_gate(db, engineer_id=10, asset_type_id=20)

    assert result["cleared"] is True
    assert result["records"] == [{"id": 2, "state": "active"}]
    assert result["active_count"] == 1


@pytest.mark.asyncio
async def test_competency_gate_blocks_when_latest_record_failed():
    older_active = types.SimpleNamespace(
        id=1,
        state=CompetencyLifecycleState.ACTIVE,
        assessed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    newer_failed = types.SimpleNamespace(
        id=2,
        state=CompetencyLifecycleState.FAILED,
        assessed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
    )
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult([older_active, newer_failed])))

    result = await GovernanceService.check_competency_gate(db, engineer_id=10, asset_type_id=20)

    assert result["cleared"] is False
    assert result["records"] == [{"id": 2, "state": "failed"}]
    assert "latest competency assessment" in result["reason"]


@pytest.mark.asyncio
async def test_competency_gate_treats_expired_active_record_as_not_cleared():
    expired_active = types.SimpleNamespace(
        id=3,
        state=CompetencyLifecycleState.ACTIVE,
        assessed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        expires_at=datetime(2026, 2, 2, tzinfo=timezone.utc),
    )
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult([expired_active])))

    result = await GovernanceService.check_competency_gate(db, engineer_id=10, asset_type_id=20)

    assert result["cleared"] is False
    assert result["records"] == [{"id": 3, "state": "expired"}]


@pytest.mark.asyncio
async def test_competency_gate_blocks_when_latest_record_due():
    due_record = types.SimpleNamespace(
        id=4,
        state=CompetencyLifecycleState.DUE,
        assessed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        expires_at=datetime(2026, 12, 31, tzinfo=timezone.utc),
    )
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult([due_record])))

    result = await GovernanceService.check_competency_gate(db, engineer_id=10, asset_type_id=20)

    assert result["cleared"] is False
    assert result["records"] == [{"id": 4, "state": "due"}]
