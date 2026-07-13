"""CUJ-P10: GET /engineers/by-user/me thin self resolver."""

import types
from unittest.mock import AsyncMock

import pytest

from src.api.routes.engineers import get_engineer_by_user_me
from src.domain.exceptions import NotFoundError


class _FakeResult:
    def __init__(self, value):
        self._value = value

    def scalar_one_or_none(self):
        return self._value


@pytest.mark.asyncio
async def test_get_engineer_by_user_me_returns_linked_profile():
    engineer = types.SimpleNamespace(
        id=10,
        user_id=42,
        external_id="eng-1",
        employee_number="E-42",
        job_title="Field Engineer",
        department="Ops",
        site="North",
        start_date=None,
        specialisations_json=None,
        certifications_json=None,
        is_active=True,
        notes=None,
        tenant_id=1,
        competency_records=[],
        created_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(engineer)))
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    result = await get_engineer_by_user_me(db, user)

    assert result.id == 10
    assert result.user_id == 42
    assert result.job_title == "Field Engineer"


@pytest.mark.asyncio
async def test_get_engineer_by_user_me_404_when_unlinked():
    db = types.SimpleNamespace(execute=AsyncMock(return_value=_FakeResult(None)))
    user = types.SimpleNamespace(id=42, tenant_id=1, is_superuser=False, roles=[])

    with pytest.raises(NotFoundError) as exc_info:
        await get_engineer_by_user_me(db, user)

    assert exc_info.value.http_status == 404
    detail = str(exc_info.value).lower() + " " + str(getattr(exc_info.value, "message", "")).lower()
    assert "not linked" in detail or "not found" in detail
