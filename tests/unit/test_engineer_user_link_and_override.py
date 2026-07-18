"""Engineer↔User link endpoints and PAMS sync QGP override protection."""

import types
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from src.api.routes.engineers import link_engineer_user, unlink_engineer_user, update_engineer
from src.api.schemas.engineer import EngineerLinkUserRequest, EngineerUpdate
from src.domain.services.pams_technician_sync_service import (
    MappedTechnician,
    apply_mapped_technician_to_engineer,
)

NOW = datetime(2026, 7, 18, tzinfo=timezone.utc)


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


def _engineer(**kwargs):
    base = dict(
        id=10,
        external_id="ext-10",
        user_id=None,
        display_name="Ann",
        pams_technician_id=None,
        employee_number=None,
        job_title=None,
        department=None,
        site=None,
        start_date=None,
        specialisations_json=None,
        certifications_json=None,
        is_active=True,
        notes=None,
        qgp_profile_override=False,
        tenant_id=1,
        created_at=NOW,
        updated_at=NOW,
    )
    base.update(kwargs)
    return types.SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_link_engineer_user_sets_user_id():
    engineer = _engineer(user_id=None, display_name=None)
    target_user = types.SimpleNamespace(
        id=55,
        tenant_id=1,
        is_active=True,
        email="a@b.com",
        first_name="Ann",
        last_name="Bee",
        full_name="Ann Bee",
    )
    db = types.SimpleNamespace(
        execute=AsyncMock(
            side_effect=[
                _FakeResult(engineer),
                _FakeResult(target_user),
                _FakeResult(None),
                _FakeResult(target_user),
            ]
        ),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    manager = types.SimpleNamespace(id=7, tenant_id=1, is_superuser=False, roles=[types.SimpleNamespace(name="admin")])

    result = await link_engineer_user(10, EngineerLinkUserRequest(user_id=55), db, manager)
    assert engineer.user_id == 55
    assert engineer.display_name == "Ann Bee"
    assert result.user_id == 55
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_unlink_engineer_user_clears_user_id():
    engineer = _engineer(user_id=55)
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(engineer), _FakeResult(None)]),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    manager = types.SimpleNamespace(id=7, tenant_id=1, is_superuser=False, roles=[types.SimpleNamespace(name="admin")])

    result = await unlink_engineer_user(10, db, manager)
    assert engineer.user_id is None
    assert result.user_id is None


@pytest.mark.asyncio
async def test_update_sets_qgp_profile_override_on_identity_edit():
    engineer = _engineer(display_name="Old", qgp_profile_override=False)
    db = types.SimpleNamespace(
        execute=AsyncMock(side_effect=[_FakeResult(engineer), _FakeResult(None)]),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    manager = types.SimpleNamespace(id=7, tenant_id=1, is_superuser=False, roles=[types.SimpleNamespace(name="admin")])

    await update_engineer(10, EngineerUpdate(display_name="QGP Name"), db, manager)
    assert engineer.display_name == "QGP Name"
    assert engineer.qgp_profile_override is True


def test_pams_sync_preserves_identity_when_override():
    engineer = types.SimpleNamespace(
        display_name="Local Name",
        job_title="Local Title",
        site="Local Site",
        employee_number="L1",
        notes="keep",
        is_active=True,
        pams_technician_id=1,
        external_id="old",
        user_id=9,
        qgp_profile_override=True,
    )
    mapped = MappedTechnician(
        pams_id=99,
        display_name="PAMS Name",
        job_title="PAMS Title",
        site="PAMS Site",
        employee_number="P99",
        is_active=False,
        email=None,
        notes="from pams",
        external_id="pams-99",
    )
    apply_mapped_technician_to_engineer(engineer, mapped, user_id=None, preserve_existing_user=True)
    assert engineer.display_name == "Local Name"
    assert engineer.job_title == "Local Title"
    assert engineer.site == "Local Site"
    assert engineer.employee_number == "L1"
    assert engineer.notes == "keep"
    assert engineer.is_active is False
    assert engineer.pams_technician_id == 99
    assert engineer.external_id == "pams-99"


def test_pams_sync_overwrites_when_no_override():
    engineer = types.SimpleNamespace(
        display_name="Local Name",
        job_title="Local Title",
        site="Local Site",
        employee_number="L1",
        notes=None,
        is_active=True,
        pams_technician_id=1,
        external_id="old",
        user_id=None,
        qgp_profile_override=False,
    )
    mapped = MappedTechnician(
        pams_id=99,
        display_name="PAMS Name",
        job_title="PAMS Title",
        site="PAMS Site",
        employee_number="P99",
        is_active=True,
        email=None,
        notes="from pams",
        external_id="pams-99",
    )
    apply_mapped_technician_to_engineer(engineer, mapped, user_id=12, preserve_existing_user=True)
    assert engineer.display_name == "PAMS Name"
    assert engineer.user_id == 12
