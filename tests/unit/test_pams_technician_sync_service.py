"""Unit tests for PAMS technician → engineer sync mapping and upsert logic."""

from __future__ import annotations

import types
from unittest.mock import AsyncMock

import pytest

from src.domain.models.engineer import Engineer
from src.domain.models.user import User
from src.domain.exceptions import BadRequestError
from src.domain.services.pams_technician_sync_service import (
    map_pams_technician_row,
    pams_technician_external_id,
    resolve_tenant_id,
    resolve_user_id_for_email,
    sync_pams_technicians,
)


def test_map_pams_technician_row_uses_display_name_and_role():
    mapped = map_pams_technician_row(
        {
            "id": 42,
            "display_name": "Alex Technician",
            "role": "Field Engineer",
            "postcode": "SW1A 1AA",
            "short_name": "AT42",
            "email": "alex@example.com",
            "phone": "07000000000",
            "active_technician": 1,
        }
    )
    assert mapped is not None
    assert mapped.pams_id == 42
    assert mapped.display_name == "Alex Technician"
    assert mapped.job_title == "Field Engineer"
    assert mapped.site == "SW1A 1AA"
    assert mapped.employee_number == "AT42"
    assert mapped.is_active is True
    assert mapped.email == "alex@example.com"
    assert "alex@example.com" in (mapped.notes or "")
    assert mapped.external_id == pams_technician_external_id(42)


def test_map_pams_technician_row_falls_back_to_first_last_name():
    mapped = map_pams_technician_row(
        {"id": 7, "firstname": "Sam", "surname": "Taylor", "active_technician": 0}
    )
    assert mapped is not None
    assert mapped.display_name == "Sam Taylor"
    assert mapped.is_active is False
    assert mapped.employee_number == "7"


def test_map_pams_technician_row_skips_missing_id():
    assert map_pams_technician_row({"display_name": "No ID"}) is None


def test_resolve_user_id_for_email_case_insensitive_and_tenant_scoped():
    user = types.SimpleNamespace(id=9, tenant_id=1, is_active=True, email="Alex@Example.com")
    users_by_email = {"alex@example.com": user}
    assert (
        resolve_user_id_for_email(
            "ALEX@example.com",
            tenant_id=1,
            users_by_email=users_by_email,
            user_ids_taken=set(),
        )
        == 9
    )
    assert (
        resolve_user_id_for_email(
            "ALEX@example.com",
            tenant_id=2,
            users_by_email=users_by_email,
            user_ids_taken=set(),
        )
        is None
    )
    assert (
        resolve_user_id_for_email(
            "ALEX@example.com",
            tenant_id=1,
            users_by_email=users_by_email,
            user_ids_taken={9},
        )
        is None
    )


def test_resolve_tenant_id_requires_default(monkeypatch):
    monkeypatch.setattr("src.domain.services.pams_technician_sync_service.settings.default_tenant_id", None)
    with pytest.raises(BadRequestError) as exc_info:
        resolve_tenant_id()
    assert "DEFAULT_TENANT_ID" in str(exc_info.value.message)


class _FakeQuery:
    def __init__(self, items):
        self._items = items

    def filter(self, *args, **kwargs):
        return self

    def all(self):
        return self._items


class _FakeSession:
    def __init__(self, users, engineers):
        self.users = users
        self.engineers = engineers
        self.added: list[Engineer] = []
        self.committed = False

    def query(self, model):
        if model is User:
            return _FakeQuery(self.users)
        if model is Engineer:
            return _FakeQuery(self.engineers)
        raise AssertionError(f"Unexpected model {model}")

    def add(self, obj):
        self.added.append(obj)
        self.engineers.append(obj)

    def commit(self):
        self.committed = True


def test_sync_pams_technicians_creates_updates_and_deactivates():
    existing = Engineer(
        id=100,
        tenant_id=1,
        user_id=None,
        external_id=pams_technician_external_id(5),
        pams_technician_id=5,
        display_name="Old Name",
        is_active=True,
    )
    stale = Engineer(
        id=101,
        tenant_id=1,
        user_id=None,
        external_id=pams_technician_external_id(99),
        pams_technician_id=99,
        display_name="Removed From PAMS",
        is_active=True,
    )
    user = User(id=3, tenant_id=1, is_active=True, email="new@example.com")
    db = _FakeSession(users=[user], engineers=[existing, stale])

    rows = [
        {
            "id": 5,
            "display_name": "Updated Tech",
            "role": "Senior Engineer",
            "postcode": "AB1 2CD",
            "active_technician": 1,
        },
        {
            "id": 10,
            "display_name": "New Tech",
            "email": "new@example.com",
            "active_technician": 1,
        },
    ]

    counts = sync_pams_technicians(db, tenant_id=1, rows=rows)

    assert counts.created == 1
    assert counts.updated == 1
    assert counts.deactivated == 1
    assert counts.errors == 0
    assert existing.display_name == "Updated Tech"
    assert existing.job_title == "Senior Engineer"
    assert stale.is_active is False
    assert len(db.added) == 1
    assert db.added[0].pams_technician_id == 10
    assert db.added[0].user_id == 3
    assert db.committed is True
