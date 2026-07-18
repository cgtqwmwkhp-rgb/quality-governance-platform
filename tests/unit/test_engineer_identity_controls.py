import types
from unittest.mock import AsyncMock, Mock

import pytest

from src.api.routes.engineers import create_engineer, update_engineer
from src.api.schemas.engineer import EngineerCreate, EngineerUpdate
from src.domain.exceptions import BadRequestError, ConflictError


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

    with pytest.raises(BadRequestError) as exc_info:
        await create_engineer(payload, db, manager)

    assert exc_info.value.http_status == 400
    assert exc_info.value.code == "BAD_REQUEST"
    assert exc_info.value.message == "Assigned user is not in tenant scope"
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

    with pytest.raises(ConflictError) as exc_info:
        await create_engineer(payload, db, manager)

    assert exc_info.value.http_status == 409
    assert exc_info.value.code == "DUPLICATE_ENTITY"
    assert exc_info.value.details["engineer_id"] == 101
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

    with pytest.raises(BadRequestError) as exc_info:
        await create_engineer(payload, db, manager)

    assert exc_info.value.http_status == 400
    assert exc_info.value.code == "BAD_REQUEST"
    assert exc_info.value.message == "Assigned user is not in tenant scope"
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

    with pytest.raises(BadRequestError) as exc_info:
        await update_engineer(10, EngineerUpdate(user_id=99), db, manager)

    assert exc_info.value.http_status == 400
    assert exc_info.value.code == "BAD_REQUEST"
    assert "link-user" in exc_info.value.message
    db.commit.assert_not_awaited()


def test_engineer_create_requires_user_or_display_name():
    with pytest.raises(ValueError):
        EngineerCreate()


def test_engineer_create_accepts_display_name_only():
    payload = EngineerCreate(display_name="Roster Only")
    assert payload.user_id is None
    assert payload.display_name == "Roster Only"


def test_engineer_create_maps_role_to_job_title():
    payload = EngineerCreate(display_name="Roster Only", role="Technician")
    assert payload.job_title == "Technician"


@pytest.mark.asyncio
async def test_create_engineer_allows_display_name_without_user():
    from datetime import datetime, timezone

    db = types.SimpleNamespace(
        execute=AsyncMock(return_value=_FakeResult(None)),
        add=Mock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    manager = types.SimpleNamespace(id=7, tenant_id=1, is_superuser=False, roles=[types.SimpleNamespace(name="admin")])
    payload = EngineerCreate(display_name="Manual Employee", job_title="Technician")

    async def _refresh(engineer):
        engineer.id = 501
        engineer.external_id = "ext-501"
        engineer.is_active = True
        engineer.qgp_profile_override = False
        engineer.created_at = datetime.now(timezone.utc)
        engineer.updated_at = datetime.now(timezone.utc)

    db.refresh = AsyncMock(side_effect=_refresh)

    result = await create_engineer(payload, db, manager)

    db.add.assert_called_once()
    created = db.add.call_args[0][0]
    assert created.display_name == "Manual Employee"
    assert created.user_id is None
    db.commit.assert_awaited()
    assert result.display_name == "Manual Employee"
    assert result.user_id is None
