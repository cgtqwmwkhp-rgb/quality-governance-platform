"""TEN2 isolation suite slice: cross-tenant denial on FORCE-RLS RTAs.

Road traffic collisions are in the original FORCE RLS catalog (`RLS_TABLES`).
This suite proves the application layer also fails closed on get/list/update/delete
for another tenant's RTA id — continuing Preferred S9 after the incidents slice
(#830), on a different domain file (RTAs, not incidents/CAPA).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.api.schemas.rta import RTAUpdate
from src.core.pagination import PaginationInput
from src.domain.models.rta import RoadTrafficCollision
from src.domain.services.rta_service import RTAService
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


def test_rtas_are_force_rls_covered():
    """Guardrail: this slice targets an already-FORCE-RLS module."""
    assert "road_traffic_collisions" in RLS_TABLES
    assert RoadTrafficCollision.__table__.c.tenant_id.nullable is False


@pytest.mark.asyncio
async def test_get_rta_scopes_sql_to_caller_tenant():
    statements = []

    async def execute(statement):
        statements.append(statement)
        return _Result(None)

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
    svc = RTAService(db)

    with pytest.raises(LookupError) as exc:
        await svc.get_rta(99, tenant_id=17)

    assert "99" in str(exc.value)
    sql = _sql(statements[0])
    assert "road_traffic_collisions.id = 99" in sql or "roadtrafficcollision.id = 99" in sql or "id = 99" in sql
    assert "tenant_id = 17" in sql
    assert "tenant_id is null" not in sql.replace(" is not null", "")


@pytest.mark.asyncio
async def test_cross_tenant_rta_lookup_is_indistinguishable_from_missing():
    """Cross-tenant get must raise LookupError (no existence leak) when filtered out."""
    db = SimpleNamespace(execute=AsyncMock(return_value=_Result(None)))
    svc = RTAService(db)

    with pytest.raises(LookupError) as exc:
        await svc.get_rta(501, tenant_id=23)

    assert "501" in str(exc.value)
    assert "not found" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_list_rtas_uses_exact_tenant_scope():
    statements = []

    async def execute(statement):
        statements.append(statement)
        # count query then page query
        if len(statements) == 1:
            return _Result(0)
        return _Result([])

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
    svc = RTAService(db)

    response = await svc.list_rtas(
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
async def test_update_rta_denies_cross_tenant_target():
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
    svc = RTAService(db)

    with pytest.raises(LookupError) as exc:
        await svc.update_rta(
            9001,
            RTAUpdate(title="should-not-apply"),
            user_id=7,
            tenant_id=55,
            request_id="req-isolation",
        )

    assert "9001" in str(exc.value)
    sql = _sql(statements[0])
    assert "tenant_id = 55" in sql
    assert "9001" in sql


@pytest.mark.asyncio
async def test_delete_rta_denies_cross_tenant_target():
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
    svc = RTAService(db)

    with pytest.raises(LookupError) as exc:
        await svc.delete_rta(
            9002,
            user_id=8,
            tenant_id=66,
            request_id="req-isolation-del",
        )

    assert "9002" in str(exc.value)
    sql = _sql(statements[0])
    assert "tenant_id = 66" in sql
    assert "9002" in sql
