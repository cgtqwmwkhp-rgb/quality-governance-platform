"""Regression suite: the investigation tenant gate, and that nothing bypasses it.

Companion to ``tests/integration/test_investigation_tenant_isolation.py``, which
proves the behaviour over HTTP. These are the fast guards:

* the gate itself refuses a mismatched tenant, a tenant-less record and a
  tenant-less caller;
* ``investigations:view_all`` is never even consulted for a run outside the
  caller's tenant, which is the whole point — the permission means "every
  investigation in my tenant", as its siblings in the four case registers do;
* no route can reach an ``InvestigationRun`` by id without passing the gate,
  which is what stops the next endpoint added to the module from reopening this.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from src.api.routes.investigations import _assert_investigation_tenant, _get_investigation_or_404
from src.domain.exceptions import TenantAccessError

ROUTE_MODULE = Path("src/api/routes/investigations.py")
LOADER = "_load_investigation_or_404"
GATE = "_assert_investigation_tenant"


def _run(*, tenant_id, **overrides):
    defaults = dict(
        id=7,
        tenant_id=tenant_id,
        reference_number="INV-2026-0007",
        assigned_to_user_id=None,
        reviewer_user_id=None,
        approved_by_id=None,
        created_by_id=None,
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _user(*, tenant_id, is_superuser=False, permissions=()):
    granted = set(permissions)
    return SimpleNamespace(
        id=42,
        tenant_id=tenant_id,
        is_superuser=is_superuser,
        has_permission=MagicMock(side_effect=lambda permission: permission in granted),
    )


def _db_returning(row):
    result = MagicMock()
    result.scalar_one_or_none.return_value = row
    db = AsyncMock()
    db.execute = AsyncMock(return_value=result)
    return db


class TestTheGate:
    def test_matching_tenant_is_allowed_and_yields_the_scope(self):
        assert _assert_investigation_tenant(_run(tenant_id=9), _user(tenant_id=9)) == 9

    def test_a_different_tenant_is_refused_under_the_shared_code(self):
        with pytest.raises(TenantAccessError) as exc_info:
            _assert_investigation_tenant(_run(tenant_id=9), _user(tenant_id=1))

        assert exc_info.value.code == "TENANT_ACCESS_DENIED"
        assert exc_info.value.details["investigation_id"] == 7

    def test_a_tenantless_record_is_refused_rather_than_guessed_at(self):
        """``investigation_runs.tenant_id`` is NOT NULL, so this row is corrupt."""
        with pytest.raises(TenantAccessError):
            _assert_investigation_tenant(_run(tenant_id=None), _user(tenant_id=1))

    def test_a_tenantless_caller_cannot_borrow_the_records_tenant(self):
        with pytest.raises(HTTPException) as exc_info:
            _assert_investigation_tenant(_run(tenant_id=9), _user(tenant_id=None))

        assert exc_info.value.status_code == 403

    def test_a_superuser_is_scoped_to_their_own_tenant(self):
        """Deliberate. #1389 already refuses a superuser's cross-tenant closure."""
        with pytest.raises(TenantAccessError):
            _assert_investigation_tenant(_run(tenant_id=9), _user(tenant_id=1, is_superuser=True))


@pytest.mark.asyncio
class TestViewAllIsTenantBounded:
    async def test_view_all_is_not_even_consulted_for_another_tenants_run(self):
        """The defect: this permission was read as "every investigation anywhere"."""
        holder = _user(tenant_id=1, permissions={"investigations:view_all"})

        with pytest.raises(TenantAccessError):
            await _get_investigation_or_404(7, _db_returning(_run(tenant_id=9)), holder)

        holder.has_permission.assert_not_called()

    async def test_view_all_still_reaches_a_run_inside_the_callers_tenant(self):
        holder = _user(tenant_id=9, permissions={"investigations:view_all"})
        run = _run(tenant_id=9)

        assert await _get_investigation_or_404(7, _db_returning(run), holder) is run

    async def test_being_named_on_another_tenants_run_is_not_enough(self):
        run = _run(tenant_id=9, assigned_to_user_id=42)

        with pytest.raises(TenantAccessError):
            await _get_investigation_or_404(7, _db_returning(run), _user(tenant_id=1))


class TestNoRouteBypassesTheGate:
    """Structural, so a new endpoint cannot quietly reopen the hole."""

    @staticmethod
    def _module() -> ast.Module:
        return ast.parse(ROUTE_MODULE.read_text(encoding="utf-8"))

    @staticmethod
    def _called_names(node: ast.AST) -> set[str]:
        return {
            child.func.id
            for child in ast.walk(node)
            if isinstance(child, ast.Call) and isinstance(child.func, ast.Name)
        }

    def test_by_id_selects_live_only_in_the_single_loader(self):
        """One place reads a run by bare id, so there is one place to gate."""
        offenders = []
        for node in ast.walk(self._module()):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name == LOADER:
                continue
            source = ast.unparse(node)
            if "InvestigationRun.id == investigation_id" in source:
                offenders.append(node.name)

        assert offenders == [], f"{offenders} load an investigation by id outside {LOADER}"

    def test_every_loader_caller_also_applies_the_gate(self):
        ungated = []
        for node in ast.walk(self._module()):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            called = self._called_names(node)
            if LOADER in called and GATE not in called:
                ungated.append(node.name)

        assert ungated == [], f"{ungated} load an investigation without calling {GATE}"

    def test_the_list_endpoint_is_tenant_filtered(self):
        listing = next(
            node
            for node in ast.walk(self._module())
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "list_investigations"
        )
        called = self._called_names(listing)

        assert "apply_tenant_filter" in called
        assert "require_tenant_id" in called
