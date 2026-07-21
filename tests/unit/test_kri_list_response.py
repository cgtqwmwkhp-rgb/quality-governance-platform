"""ACT-022: GET /kri must not 500 on enum/null/legacy-table edge cases."""

from __future__ import annotations

import enum
import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import ProgrammingError

from src.api.routes.kri import list_kris
from src.api.schemas.kri import KRIResponse


class _Cat(str, enum.Enum):
    SAFETY = "safety"


class _Status(str, enum.Enum):
    GREEN = "green"


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalars(self):
        return self

    def all(self):
        return self._value


def test_kri_response_coerces_enums_and_linked_ids():
    row = types.SimpleNamespace(
        id=1,
        code="KRI-1",
        name="Incidents",
        description=None,
        category=_Cat.SAFETY,
        unit="count",
        measurement_frequency="monthly",
        data_source="incident_count",
        calculation_method=None,
        auto_calculate=True,
        lower_is_better=True,
        green_threshold=1.0,
        amber_threshold=3.0,
        red_threshold=5.0,
        linked_risk_ids=["10", 11, "x"],
        owner_id=None,
        department=None,
        is_active=True,
        current_value=2.0,
        current_status=_Status.GREEN,
        last_updated=None,
        trend_direction=None,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    resp = KRIResponse.model_validate(row)
    assert resp.category == "safety"
    assert resp.current_status == "green"
    assert resp.linked_risk_ids == [10, 11]


@pytest.mark.asyncio
async def test_list_kris_returns_empty_when_legacy_table_missing():
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=ProgrammingError("select", {}, Exception("undefined table"))),
        rollback=AsyncMock(),
    )
    user = types.SimpleNamespace(tenant_id=1)

    result = await list_kris(db=db, current_user=user)
    assert result.total == 0
    assert result.items == []
    db.rollback.assert_awaited()
