"""TEN2 isolation suite slice: cross-tenant denial on FORCE-RLS policies.

Policies are covered by ENABLE+FORCE RLS + tenant_isolation (USING + WITH CHECK)
via 20260711_rls_with_check_expand. This suite proves the application layer
also fails closed on get/list/update/delete for another tenant's policy id.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.routes.policies import delete_policy, get_policy, list_policies, update_policy
from src.api.schemas.policy import PolicyUpdate
from src.domain.models.policy import Policy
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


def test_policies_are_force_rls_covered():
    """Guardrail: this slice targets an already-FORCE-RLS module."""
    assert "policies" in RLS_TABLES
    assert Policy.__table__.c.tenant_id.nullable is False


@pytest.mark.asyncio
async def test_get_policy_scopes_sql_to_caller_tenant():
    statements = []

    async def execute(statement):
        statements.append(statement)
        return _Result(None)

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
    user = SimpleNamespace(tenant_id=17, is_superuser=False)

    with pytest.raises(HTTPException) as exc:
        await get_policy(policy_id=99, db=db, current_user=user)

    assert exc.value.status_code == 404
    sql = _sql(statements[0])
    assert "policies.id = 99" in sql or "policy.id = 99" in sql or "id = 99" in sql
    assert "tenant_id = 17" in sql
    assert "tenant_id is null" not in sql.replace(" is not null", "")


@pytest.mark.asyncio
async def test_cross_tenant_policy_lookup_is_indistinguishable_from_missing():
    """Cross-tenant get must 404 (no existence leak) when the row is filtered out."""
    db = SimpleNamespace(execute=AsyncMock(return_value=_Result(None)))
    user = SimpleNamespace(tenant_id=23, is_superuser=False)

    with pytest.raises(HTTPException) as exc:
        await get_policy(policy_id=501, db=db, current_user=user)

    assert exc.value.status_code == 404
    assert "501" in str(exc.value.detail)


@pytest.mark.asyncio
async def test_list_policies_uses_exact_tenant_scope():
    statements = []

    async def execute(statement):
        statements.append(statement)
        # count query then page query
        if len(statements) == 1:
            return _Result(0)
        return _Result([])

    db = SimpleNamespace(execute=AsyncMock(side_effect=execute))
    user = SimpleNamespace(tenant_id=41, is_superuser=False)

    response = await list_policies(db=db, current_user=user, page=1, page_size=50)

    assert response.total == 0
    assert response.items == []
    assert len(statements) == 2
    for statement in statements:
        sql = _sql(statement)
        assert "tenant_id = 41" in sql
        compact = " ".join(sql.split())
        assert "tenant_id is null" not in compact


@pytest.mark.asyncio
async def test_update_policy_denies_cross_tenant_target(monkeypatch):
    statements = []

    async def execute(statement):
        statements.append(statement)
        return _Result(None)

    db = SimpleNamespace(
        execute=AsyncMock(side_effect=execute),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = SimpleNamespace(
        id=7,
        tenant_id=55,
        is_superuser=False,
        has_permission=lambda _p: True,
    )
    monkeypatch.setattr(
        "src.api.routes.policies.record_audit_event",
        AsyncMock(),
    )

    with pytest.raises(HTTPException) as exc:
        await update_policy(
            policy_id=9001,
            policy_data=PolicyUpdate(title="should-not-apply"),
            db=db,
            current_user=user,
            request_id="req-isolation",
        )

    assert exc.value.status_code == 404
    sql = _sql(statements[0])
    assert "tenant_id = 55" in sql
    assert "9001" in sql


@pytest.mark.asyncio
async def test_delete_policy_denies_cross_tenant_target(monkeypatch):
    statements = []

    async def execute(statement):
        statements.append(statement)
        return _Result(None)

    db = SimpleNamespace(
        execute=AsyncMock(side_effect=execute),
        delete=AsyncMock(),
        commit=AsyncMock(),
    )
    user = SimpleNamespace(
        id=8,
        tenant_id=66,
        is_superuser=False,
        has_permission=lambda _p: True,
    )
    monkeypatch.setattr(
        "src.api.routes.policies.record_audit_event",
        AsyncMock(),
    )

    with pytest.raises(HTTPException) as exc:
        await delete_policy(
            policy_id=9002,
            db=db,
            current_user=user,
            request_id="req-isolation-del",
        )

    assert exc.value.status_code == 404
    sql = _sql(statements[0])
    assert "tenant_id = 66" in sql
    assert "9002" in sql
