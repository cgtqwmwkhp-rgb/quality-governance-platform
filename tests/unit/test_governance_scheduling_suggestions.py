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
async def test_scheduling_suggestions_ignore_stale_expired_when_latest_is_active():
    stale_expired = types.SimpleNamespace(
        id=1,
        engineer_id=10,
        asset_type_id=20,
        template_id=30,
        state=CompetencyLifecycleState.EXPIRED,
        assessed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        expires_at=datetime(2026, 1, 31, tzinfo=timezone.utc),
    )
    newer_active = types.SimpleNamespace(
        id=2,
        engineer_id=10,
        asset_type_id=20,
        template_id=30,
        state=CompetencyLifecycleState.ACTIVE,
        assessed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        expires_at=datetime(2027, 2, 1, tzinfo=timezone.utc),
    )
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult([stale_expired, newer_active])))

    result = await GovernanceService.get_scheduling_suggestions(db, engineer_id=10)

    assert result == []


@pytest.mark.asyncio
async def test_scheduling_suggestions_return_latest_due_record_per_asset_type():
    older_due = types.SimpleNamespace(
        id=1,
        engineer_id=10,
        asset_type_id=20,
        template_id=30,
        state=CompetencyLifecycleState.DUE,
        assessed_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
        expires_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
    )
    latest_expired = types.SimpleNamespace(
        id=2,
        engineer_id=10,
        asset_type_id=20,
        template_id=30,
        state=CompetencyLifecycleState.EXPIRED,
        assessed_at=datetime(2026, 2, 1, tzinfo=timezone.utc),
        expires_at=datetime(2026, 2, 28, tzinfo=timezone.utc),
    )
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_ScalarResult([older_due, latest_expired])))

    result = await GovernanceService.get_scheduling_suggestions(db, engineer_id=10)

    assert result == [
        {
            "competency_record_id": 2,
            "engineer_id": 10,
            "asset_type_id": 20,
            "template_id": 30,
            "state": "expired",
            "expires_at": "2026-02-28T00:00:00+00:00",
            "priority": "high",
            "suggested_action": "Reassessment required",
        }
    ]
