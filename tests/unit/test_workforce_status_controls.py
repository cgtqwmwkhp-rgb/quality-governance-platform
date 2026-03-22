import types
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.routes.assessments import update_assessment_run
from src.api.routes.inductions import update_induction_run
from src.api.schemas.assessment import AssessmentRunUpdate
from src.api.schemas.induction import InductionRunUpdate


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_update_assessment_run_rejects_direct_status_change():
    run = types.SimpleNamespace(id="run-1", supervisor_id=11)
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(run)),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=11, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await update_assessment_run("run-1", AssessmentRunUpdate(status="completed"), db, user)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "INVALID_STATE_TRANSITION"
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_induction_run_rejects_direct_status_change():
    run = types.SimpleNamespace(id="run-2", supervisor_id=11)
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(run)),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = types.SimpleNamespace(id=11, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await update_induction_run("run-2", InductionRunUpdate(status="completed"), db, user)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "INVALID_STATE_TRANSITION"
    db.commit.assert_not_awaited()
