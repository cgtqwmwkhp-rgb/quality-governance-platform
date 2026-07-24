"""Unit tests for customer lookup → contracts.id materialisation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.contract_resolve import ensure_contracts_from_customer_lookups


@pytest.mark.asyncio
async def test_ensure_contracts_from_customer_lookups_resolves_each_active_customer(monkeypatch):
    lookups = [
        SimpleNamespace(code="openreach", label="Openreach"),
        SimpleNamespace(code="defra", label="DEFRA"),
    ]
    result = MagicMock()
    result.scalars.return_value.all.return_value = lookups

    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    resolve = AsyncMock(side_effect=[11, 22])
    monkeypatch.setattr(
        "src.domain.services.contract_resolve.resolve_contract_id_by_code",
        resolve,
    )

    linked = await ensure_contracts_from_customer_lookups(db, tenant_id=7)

    assert linked == 2
    assert resolve.await_count == 2
    resolve.assert_any_await(db, tenant_id=7, code="openreach")
    resolve.assert_any_await(db, tenant_id=7, code="defra")


@pytest.mark.asyncio
async def test_ensure_contracts_skips_unresolved_codes(monkeypatch):
    lookups = [SimpleNamespace(code="ghost", label="Ghost")]
    result = MagicMock()
    result.scalars.return_value.all.return_value = lookups
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    monkeypatch.setattr(
        "src.domain.services.contract_resolve.resolve_contract_id_by_code",
        AsyncMock(return_value=None),
    )

    linked = await ensure_contracts_from_customer_lookups(db, tenant_id=7)
    assert linked == 0
