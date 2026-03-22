import types
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.routes.auditor_competence import (
    _assert_auditor_access,
    create_auditor_profile,
    CreateProfileRequest,
)
from src.services.auditor_competence import AuditorCompetenceService


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value

    def scalars(self):
        return self

    def all(self):
        return self._value


@pytest.mark.asyncio
async def test_auditor_access_allows_self_read():
    user = types.SimpleNamespace(id=42, tenant_id=3, is_superuser=False, roles=[])

    _assert_auditor_access(user, 42)


@pytest.mark.asyncio
async def test_auditor_access_denies_unrelated_non_manager():
    user = types.SimpleNamespace(id=42, tenant_id=3, is_superuser=False, roles=[])

    with pytest.raises(HTTPException) as exc:
        _assert_auditor_access(user, 77)

    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_create_profile_persists_tenant_id():
    db = types.SimpleNamespace(add=lambda _: None, commit=AsyncMock(), refresh=AsyncMock())
    service = AuditorCompetenceService(db, tenant_id=7)

    profile = await service.create_profile(user_id=11, job_title="Auditor", department="QA", years_experience=5)

    assert profile.tenant_id == 7
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_profile_scopes_to_service_tenant():
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(None)))
    service = AuditorCompetenceService(db, tenant_id=7)

    await service.get_profile(11)

    statement = db.execute.await_args.args[0]
    assert "auditor_profiles.tenant_id" in str(statement)


@pytest.mark.asyncio
async def test_get_expiring_certifications_scopes_to_service_tenant():
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeResult([])))
    service = AuditorCompetenceService(db, tenant_id=7)

    await service.get_expiring_certifications(30)

    statement = db.execute.await_args.args[0]
    assert "auditor_certifications.tenant_id" in str(statement)


@pytest.mark.asyncio
async def test_create_profile_rejects_cross_tenant_user(monkeypatch):
    target_user = types.SimpleNamespace(id=11, tenant_id=9, is_active=True)
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(target_user)))
    current_user = types.SimpleNamespace(id=42, tenant_id=7, is_superuser=False, roles=[types.SimpleNamespace(name="admin")])

    create_profile = AsyncMock()
    monkeypatch.setattr(
        "src.api.routes.auditor_competence._auditor_service",
        lambda _db, _current_user: types.SimpleNamespace(create_profile=create_profile),
    )

    with pytest.raises(HTTPException) as exc:
        await create_auditor_profile(CreateProfileRequest(user_id=11), current_user=current_user, db=db)

    assert exc.value.status_code == 400
    create_profile.assert_not_awaited()
