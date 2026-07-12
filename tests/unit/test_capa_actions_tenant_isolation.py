"""TEN2 isolation suite slice: cross-tenant denial on FORCE-RLS capa_actions.

CAPA actions are in the original FORCE RLS catalog (`RLS_TABLES`). This suite proves
the application layer also fails closed on get/list/update/delete for another
tenant's CAPA id — continuing Preferred S9 after the incidents slice (#830), on a
different domain file (actions, not incidents).
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import BaseModel

from src.domain.models.capa import CAPAAction
from src.domain.services.capa_service import CAPAService
from src.infrastructure.middleware.tenant_context import RLS_TABLES


class _CAPATitleUpdate(BaseModel):
    title: str = "should-not-apply"


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


def test_capa_actions_are_force_rls_covered():
    """Guardrail: this slice targets an already-FORCE-RLS module."""
    assert "capa_actions" in RLS_TABLES
    assert CAPAAction.__table__.c.tenant_id.nullable is False


@pytest.mark.asyncio
async def test_get_capa_action_scopes_sql_to_caller_tenant():
    statements = []

    async def execute(statement):
        statements.append(statement)
        return _Result(None)

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
    svc = CAPAService(db)

    with pytest.raises(LookupError) as exc:
        await svc.get_capa_action(99, tenant_id=17)

    assert "99" in str(exc.value)
    sql = _sql(statements[0])
    assert "capa_actions.id = 99" in sql or "capaaction.id = 99" in sql or "id = 99" in sql
    assert "tenant_id = 17" in sql
    assert "tenant_id is null" not in sql.replace(" is not null", "")


@pytest.mark.asyncio
async def test_cross_tenant_capa_lookup_is_indistinguishable_from_missing():
    """Cross-tenant get must raise LookupError (no existence leak) when filtered out."""
    db = SimpleNamespace(execute=AsyncMock(return_value=_Result(None)))
    svc = CAPAService(db)

    with pytest.raises(LookupError) as exc:
        await svc.get_capa_action(501, tenant_id=23)

    assert "501" in str(exc.value)
    assert "not found" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_list_capa_actions_uses_exact_tenant_scope():
    statements = []

    async def execute(statement):
        statements.append(statement)
        # count query then page query
        if len(statements) == 1:
            return _Result(0)
        return _Result([])

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
    svc = CAPAService(db)

    response = await svc.list_capa_actions(tenant_id=41, page=1, page_size=20)

    assert response.total == 0
    assert response.items == []
    assert len(statements) == 2
    for statement in statements:
        sql = _sql(statement)
        assert "tenant_id = 41" in sql
        compact = " ".join(sql.split())
        assert "tenant_id is null" not in compact


@pytest.mark.asyncio
async def test_update_capa_action_denies_cross_tenant_target():
    statements = []

    async def execute(statement):
        statements.append(statement)
        return _Result(None)

    db = SimpleNamespace(
        execute=AsyncMock(side_effect=execute),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    svc = CAPAService(db)

    with pytest.raises(LookupError) as exc:
        await svc.update_capa_action(
            9001,
            _CAPATitleUpdate(title="should-not-apply"),
            tenant_id=55,
        )

    assert "9001" in str(exc.value)
    sql = _sql(statements[0])
    assert "tenant_id = 55" in sql
    assert "9001" in sql


@pytest.mark.asyncio
async def test_delete_capa_action_denies_cross_tenant_target():
    statements = []

    async def execute(statement):
        statements.append(statement)
        return _Result(None)

    db = SimpleNamespace(
        execute=AsyncMock(side_effect=execute),
        delete=AsyncMock(),
        commit=AsyncMock(),
    )
    svc = CAPAService(db)

    with pytest.raises(LookupError) as exc:
        await svc.delete_capa_action(
            9002,
            user_id=8,
            tenant_id=66,
        )

    assert "9002" in str(exc.value)
    sql = _sql(statements[0])
    assert "tenant_id = 66" in sql
    assert "9002" in sql
