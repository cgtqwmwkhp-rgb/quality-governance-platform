import types
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.routes.assessments import _assert_assessment_access
from src.api.routes.inductions import _assert_induction_access


@pytest.mark.asyncio
async def test_assessment_access_allows_assessed_engineer_read_only():
    db = types.SimpleNamespace(scalar=AsyncMock(return_value=42))
    user = types.SimpleNamespace(id=42, is_superuser=False, roles=[])
    run = types.SimpleNamespace(supervisor_id=7, engineer_id=99)

    await _assert_assessment_access(db, user, run, allow_engineer_read=True)


@pytest.mark.asyncio
async def test_assessment_access_denies_unrelated_user():
    db = types.SimpleNamespace(scalar=AsyncMock(return_value=100))
    user = types.SimpleNamespace(id=42, is_superuser=False, roles=[])
    run = types.SimpleNamespace(supervisor_id=7, engineer_id=99)

    with pytest.raises(HTTPException) as exc:
        await _assert_assessment_access(db, user, run, allow_engineer_read=True)

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_induction_access_allows_admin_role():
    db = types.SimpleNamespace(scalar=AsyncMock(return_value=None))
    user = types.SimpleNamespace(
        id=42,
        is_superuser=False,
        roles=[types.SimpleNamespace(name="admin")],
    )
    run = types.SimpleNamespace(supervisor_id=7, engineer_id=99)

    await _assert_induction_access(db, user, run)
