import types
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.routes.inductions import complete_induction
from src.domain.models.induction import InductionStatus, UnderstandingVerdict


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_complete_induction_rejects_empty_responses():
    run = types.SimpleNamespace(
        id="run-001",
        supervisor_id=42,
        template_id=77,
        status=InductionStatus.DRAFT,
        responses=[],
    )
    template = types.SimpleNamespace(questions=[])
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(run), _FakeResult(template)]),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await complete_induction("run-001", db, user)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "VALIDATION_ERROR"
    assert "must be assessed" in exc.value.detail["message"]
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_complete_induction_rejects_all_na_responses():
    response = types.SimpleNamespace(
        question_id=101,
        understanding=UnderstandingVerdict.NA,
        supervisor_notes="Not applicable",
    )
    run = types.SimpleNamespace(
        id="run-002",
        supervisor_id=42,
        template_id=77,
        status=InductionStatus.IN_PROGRESS,
        responses=[response],
    )
    template = types.SimpleNamespace(questions=[types.SimpleNamespace(id=101, is_active=True)])
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(run), _FakeResult(template)]),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await complete_induction("run-002", db, user)

    assert exc.value.status_code == 400
    assert exc.value.detail["details"]["response_count"] == 1
    assert exc.value.detail["details"]["scorable_items"] == 0
    db.commit.assert_not_awaited()
