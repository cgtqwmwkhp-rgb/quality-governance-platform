"""TEN2 isolation suite slice: cross-tenant denial on FORCE-RLS near misses.

Near misses are in the original FORCE RLS catalog (`RLS_TABLES`). This suite proves
the application layer also fails closed on get/list/update/delete for another
tenant's near miss id — continuing Preferred S9 after the RTAs slice (#842), on a
different domain file (near misses, not road_traffic_collisions/incidents).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.api.schemas.near_miss import NearMissUpdate
from src.core.pagination import PaginationInput
from src.domain.models.near_miss import NearMiss
from src.domain.services.near_miss_service import NearMissService
from src.infrastructure.middleware.tenant_context import RLS_TABLES


class _Result:
    def __init__(self, value=None):
        self.value = value

    def scalar(self):
        return self.value

    def scalar_one(self):
        return self.value

    def scalar_one_or_none(self):
        return self.value

    def scalars(self):
        return self

    def all(self):
        return [] if self.value is None else list(self.value)


def _sql(statement) -> str:
    return str(statement.compile(compile_kwargs={"literal_binds": True})).lower()


def test_near_misses_are_force_rls_covered():
    """Guardrail: this slice targets an already-FORCE-RLS module."""
    assert "near_misses" in RLS_TABLES
    assert NearMiss.__table__.c.tenant_id.nullable is False


@pytest.mark.asyncio
async def test_get_near_miss_scopes_sql_to_caller_tenant():
    statements = []

    async def execute(statement):
        statements.append(statement)
        return _Result(None)

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
    svc = NearMissService(db)

    with pytest.raises(LookupError) as exc:
        await svc.get_near_miss(99, tenant_id=17)

    assert "99" in str(exc.value)
    sql = _sql(statements[0])
    assert "near_misses.id = 99" in sql or "nearmiss.id = 99" in sql or "id = 99" in sql
    assert "tenant_id = 17" in sql
    assert "tenant_id is null" not in sql.replace(" is not null", "")


@pytest.mark.asyncio
async def test_cross_tenant_near_miss_lookup_is_indistinguishable_from_missing():
    """Cross-tenant get must raise LookupError (no existence leak) when filtered out."""
    db = SimpleNamespace(execute=AsyncMock(return_value=_Result(None)))
    svc = NearMissService(db)

    with pytest.raises(LookupError) as exc:
        await svc.get_near_miss(501, tenant_id=23)

    assert "501" in str(exc.value)
    assert "not found" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_list_near_misses_uses_exact_tenant_scope():
    statements = []

    async def execute(statement):
        statements.append(statement)
        if len(statements) == 1:
            return _Result(0)
        return _Result([])

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
    svc = NearMissService(db)

    response = await svc.list_near_misses(
        tenant_id=41,
        params=PaginationInput(page=1, page_size=20),
    )

    assert response.total == 0
    assert response.items == []
    assert len(statements) == 2
    for statement in statements:
        sql = _sql(statement)
        assert "tenant_id = 41" in sql
        compact = " ".join(sql.split())
        assert "tenant_id is null" not in compact


@pytest.mark.asyncio
async def test_update_near_miss_denies_cross_tenant_target():
    statements = []

    async def execute(statement):
        statements.append(statement)
        return _Result(None)

    db = SimpleNamespace(
        execute=AsyncMock(side_effect=execute),
        flush=AsyncMock(),
        refresh=AsyncMock(),
        commit=AsyncMock(),
    )
    svc = NearMissService(db)

    with pytest.raises(LookupError) as exc:
        await svc.update_near_miss(
            9001,
            NearMissUpdate(description="should-not-apply"),
            user_id=7,
            tenant_id=55,
            request_id="req-isolation",
        )

    assert "9001" in str(exc.value)
    sql = _sql(statements[0])
    assert "tenant_id = 55" in sql
    assert "9001" in sql


@pytest.mark.asyncio
async def test_delete_near_miss_denies_cross_tenant_target():
    statements = []

    async def execute(statement):
        statements.append(statement)
        return _Result(None)

    db = SimpleNamespace(
        execute=AsyncMock(side_effect=execute),
        delete=AsyncMock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
    )
    svc = NearMissService(db)

    with pytest.raises(LookupError) as exc:
        await svc.delete_near_miss(
            9002,
            user_id=8,
            tenant_id=66,
            request_id="req-isolation-del",
        )

    assert "9002" in str(exc.value)
    sql = _sql(statements[0])
    assert "tenant_id = 66" in sql
    assert "9002" in sql
