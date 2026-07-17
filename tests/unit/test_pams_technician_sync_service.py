"""Unit tests for PAMS technician → engineer sync mapping and upsert logic."""

from __future__ import annotations

import types
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.exc import IntegrityError

from src.domain.exceptions import BadRequestError, ExternalServiceError
from src.domain.models.engineer import Engineer
from src.domain.models.user import User
from src.domain.services.pams_technician_sync_service import (
    apply_tenant_guc_sync,
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
    mapped = map_pams_technician_row({"id": 7, "firstname": "Sam", "surname": "Taylor", "active_technician": 0})
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
    def __init__(self, users, engineers, *, fail_commit: bool = False, fail_on_pams_id: int | None = None):
        self.users = users
        self.engineers = engineers
        self.added: list[Engineer] = []
        self.committed = False
        self.rolled_back = False
        self.guc_binds: list[str] = []
        self.fail_commit = fail_commit
        self.fail_on_pams_id = fail_on_pams_id
        self._dialect = types.SimpleNamespace(name="postgresql")

    def get_bind(self):
        return types.SimpleNamespace(dialect=self._dialect)

    def execute(self, statement, params=None):
        sql = str(statement)
        if "set_config" in sql and params:
            self.guc_binds.append(str(params.get("tid")))
        return None

    def query(self, model):
        if model is User:
            return _FakeQuery(self.users)
        if model is Engineer:
            return _FakeQuery(self.engineers)
        raise AssertionError(f"Unexpected model {model}")

    def add(self, obj):
        if self.fail_on_pams_id is not None and getattr(obj, "pams_technician_id", None) == self.fail_on_pams_id:
            raise IntegrityError("UNIQUE", {}, Exception("duplicate"))
        self.added.append(obj)
        self.engineers.append(obj)

    @contextmanager
    def begin_nested(self):
        yield

    def commit(self):
        if self.fail_commit:
            raise IntegrityError("COMMIT", {}, Exception("commit boom"))
        self.committed = True

    def rollback(self):
        self.rolled_back = True


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
    assert db.guc_binds == ["1"]


def test_apply_tenant_guc_sync_binds_postgres_session():
    db = _FakeSession(users=[], engineers=[])
    apply_tenant_guc_sync(db, 11)
    assert db.guc_binds == ["11"]


def test_sync_survives_row_integrity_error_without_poisoning_commit():
    """Per-row IntegrityError must increment errors and still commit siblings (session isolation)."""
    db = _FakeSession(users=[], engineers=[], fail_on_pams_id=7)
    rows = [
        {"id": 7, "display_name": "Boom", "active_technician": 1},
        {"id": 8, "display_name": "Ok Tech", "active_technician": 1},
    ]
    counts = sync_pams_technicians(db, tenant_id=1, rows=rows)
    assert counts.errors == 1
    assert counts.created == 1
    assert db.committed is True
    assert [e.pams_technician_id for e in db.added] == [8]


def test_sync_commit_failure_rolls_back_and_raises_bad_request():
    db = _FakeSession(users=[], engineers=[], fail_commit=True)
    with pytest.raises(BadRequestError) as exc_info:
        sync_pams_technicians(
            db,
            tenant_id=1,
            rows=[{"id": 1, "display_name": "A", "active_technician": 1}],
        )
    assert "could not be saved" in exc_info.value.message
    assert db.rolled_back is True


def test_fetch_pams_technicians_maps_connectivity_to_external_service_error(monkeypatch):
    from src.domain.services import pams_technician_sync_service as mod

    monkeypatch.setattr(mod.settings, "pams_database_url", "mysql+aiomysql://u:p@h/db")

    class _BoomEngine:
        def dispose(self):
            return None

    monkeypatch.setattr(mod, "_build_pams_engine", lambda: _BoomEngine())

    with patch.object(mod.MetaData, "reflect", side_effect=OSError("ssl handshake failed")):
        with pytest.raises(ExternalServiceError) as exc_info:
            mod.fetch_pams_technicians()
    assert "PAMS" in exc_info.value.message


@pytest.mark.asyncio
async def test_sync_from_pams_route_maps_unexpected_error_to_external_service():
    from src.api.routes.engineers import sync_engineers_from_pams

    user = types.SimpleNamespace(
        id=1,
        tenant_id=1,
        is_superuser=True,
        roles=[types.SimpleNamespace(name="admin")],
    )
    fake_db = MagicMock()
    with (
        patch("src.infrastructure.database.SessionLocal", return_value=fake_db),
        patch(
            "src.domain.services.pams_technician_sync_service.sync_pams_technicians",
            side_effect=RuntimeError("session poisoned"),
        ),
    ):
        with pytest.raises(ExternalServiceError) as exc_info:
            await sync_engineers_from_pams(user=user, tenant_id=None)
    assert "unexpectedly" in exc_info.value.message
    fake_db.close.assert_called_once()


@pytest.mark.asyncio
async def test_sync_from_pams_route_null_tenant_uses_default(monkeypatch):
    from src.api.routes.engineers import sync_engineers_from_pams
    from src.domain.services.pams_technician_sync_service import SyncCounts

    monkeypatch.setattr(
        "src.domain.services.pams_technician_sync_service.settings.default_tenant_id",
        42,
    )
    user = types.SimpleNamespace(
        id=1,
        tenant_id=None,
        is_superuser=True,
        roles=[types.SimpleNamespace(name="admin")],
    )
    fake_db = MagicMock()
    with (
        patch("src.infrastructure.database.SessionLocal", return_value=fake_db),
        patch(
            "src.domain.services.pams_technician_sync_service.sync_pams_technicians",
            return_value=SyncCounts(created=2),
        ) as sync_mock,
    ):
        result = await sync_engineers_from_pams(user=user, tenant_id=None)
    assert result.created == 2
    sync_mock.assert_called_once()
    assert sync_mock.call_args.kwargs["tenant_id"] == 42
