import types
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.routes.governance import (
    _assert_governance_engineer_access,
    check_competency_gate,
    check_template_approval,
    get_scheduling_suggestions,
    validate_supervisor,
)


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_governance_engineer_access_allows_self():
    engineer = types.SimpleNamespace(id=10, user_id=42)
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(engineer)))
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    await _assert_governance_engineer_access(db, user, 10)


@pytest.mark.asyncio
async def test_governance_engineer_access_denies_unrelated_user():
    engineer = types.SimpleNamespace(id=10, user_id=99)
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(engineer)))
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await _assert_governance_engineer_access(db, user, 10)

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_validate_supervisor_denies_non_manager_user():
    db = types.SimpleNamespace()
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await validate_supervisor(db, user, supervisor_id=7, engineer_id=10)

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_check_template_approval_denies_non_manager_user():
    db = types.SimpleNamespace()
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        await check_template_approval(7, db, user)

    assert exc.value.status_code == 403
    assert exc.value.detail["code"] == "PERMISSION_DENIED"


@pytest.mark.asyncio
async def test_governance_routes_allow_manager_queries():
    service_result = {"cleared": True, "reason": None, "records": [], "active_count": 1}
    suggestion_result = []
    db = types.SimpleNamespace()
    user = types.SimpleNamespace(
        id=7,
        tenant_id=1,
        is_superuser=False,
        roles=[types.SimpleNamespace(name="supervisor")],
    )

    from src.api.routes import governance as governance_routes

    original_gate = governance_routes.GovernanceService.check_competency_gate
    original_suggestions = governance_routes.GovernanceService.get_scheduling_suggestions
    governance_routes.GovernanceService.check_competency_gate = AsyncMock(return_value=service_result)
    governance_routes.GovernanceService.get_scheduling_suggestions = AsyncMock(return_value=suggestion_result)
    try:
        gate = await check_competency_gate(db, user, engineer_id=10, asset_type_id=20)
        suggestions = await get_scheduling_suggestions(10, db, user)
    finally:
        governance_routes.GovernanceService.check_competency_gate = original_gate
        governance_routes.GovernanceService.get_scheduling_suggestions = original_suggestions

    assert gate["cleared"] is True
    assert suggestions == []
