import types
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from src.api.routes.engineers import create_engineer, update_engineer
from src.api.schemas.engineer import EngineerCreate, EngineerUpdate


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_create_engineer_rejects_user_from_other_tenant():
    target_user = types.SimpleNamespace(id=55, tenant_id=999, is_active=True)
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(target_user), _FakeResult(None)]),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    manager = types.SimpleNamespace(id=7, tenant_id=1, is_superuser=False, roles=[types.SimpleNamespace(name="admin")])
    payload = EngineerCreate(user_id=55)

    with pytest.raises(HTTPException) as exc:
        await create_engineer(payload, db, manager)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "TENANT_ACCESS_DENIED"
    db.add.assert_not_called()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_engineer_rejects_duplicate_profile_for_user():
    target_user = types.SimpleNamespace(id=55, tenant_id=1, is_active=True)
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(target_user), _FakeResult(101)]),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    manager = types.SimpleNamespace(id=7, tenant_id=1, is_superuser=False, roles=[types.SimpleNamespace(name="admin")])
    payload = EngineerCreate(user_id=55)

    with pytest.raises(HTTPException) as exc:
        await create_engineer(payload, db, manager)

    assert exc.value.status_code == 409
    assert exc.value.detail["code"] == "DUPLICATE_ENTITY"
    assert exc.value.detail["details"]["engineer_id"] == 101
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_create_engineer_rejects_null_tenant_user_for_tenant_scoped_manager():
    target_user = types.SimpleNamespace(id=55, tenant_id=None, is_active=True)
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(target_user), _FakeResult(None)]),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    manager = types.SimpleNamespace(id=7, tenant_id=1, is_superuser=False, roles=[types.SimpleNamespace(name="admin")])
    payload = EngineerCreate(user_id=55)

    with pytest.raises(HTTPException) as exc:
        await create_engineer(payload, db, manager)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "TENANT_ACCESS_DENIED"
    db.add.assert_not_called()


@pytest.mark.asyncio
async def test_update_engineer_rejects_user_reassignment():
    engineer = types.SimpleNamespace(id=10, user_id=42)
    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(engineer)),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    manager = types.SimpleNamespace(id=7, tenant_id=1, is_superuser=False, roles=[types.SimpleNamespace(name="admin")])

    with pytest.raises(HTTPException) as exc:
        await update_engineer(10, EngineerUpdate(user_id=99), db, manager)

    assert exc.value.status_code == 400
    assert exc.value.detail["code"] == "VALIDATION_ERROR"
    db.commit.assert_not_awaited()
