"""Unit tests for TenantContextMiddleware and request-session GUC binding."""

from __future__ import annotations

import inspect
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from starlette.responses import JSONResponse

from src.infrastructure.middleware import tenant_context as tenant_context_mod
from src.infrastructure.middleware.tenant_context import (
    RLS_TABLES,
    SKIP_PATHS,
    TenantContextMiddleware,
    apply_tenant_guc,
    get_request_tenant_id,
    reset_request_tenant_id,
    set_request_tenant_id,
)


def test_tenant_context_middleware_is_registered_on_app():
    from src.main import create_application

    app = create_application()
    classes = [m.cls for m in app.user_middleware]
    assert TenantContextMiddleware in classes


def test_rls_tables_match_policy_migration():
    # Original 12 + policies / audit_findings / investigation_actions
    assert len(RLS_TABLES) == 15
    assert "incidents" in RLS_TABLES
    assert "users" in RLS_TABLES
    assert "audit_log_entries" in RLS_TABLES
    assert "policies" in RLS_TABLES
    assert "audit_findings" in RLS_TABLES
    assert "investigation_actions" in RLS_TABLES


def test_broken_throwaway_session_pattern_removed():
    """Guard against reintroducing throwaway-session SET LOCAL + commit."""
    source = inspect.getsource(tenant_context_mod)
    assert "async_session_maker" not in source
    # Executable SET LOCAL on a side session must not return
    assert "SET LOCAL app.current_tenant_id" not in source
    assert "await session.commit()" not in source


@pytest.mark.asyncio
async def test_middleware_skips_health_paths():
    assert "/healthz" in SKIP_PATHS

    mw = TenantContextMiddleware(app=MagicMock())
    request = MagicMock()
    request.url.path = "/healthz"
    request.state = SimpleNamespace()
    call_next = AsyncMock(return_value=JSONResponse({"ok": True}))

    await mw.dispatch(request, call_next)

    call_next.assert_awaited_once_with(request)
    assert get_request_tenant_id() is None
    assert not hasattr(request.state, "tenant_id") or getattr(request.state, "tenant_id", None) is None


@pytest.mark.asyncio
async def test_middleware_sets_request_state_tenant_id():
    mw = TenantContextMiddleware(app=MagicMock())
    request = MagicMock()
    request.url.path = "/api/v1/ping"
    request.state = SimpleNamespace(
        user=SimpleNamespace(tenant_id=42, is_superuser=False),
    )

    captured: dict = {}

    async def call_next(req):
        captured["tenant_id"] = getattr(req.state, "tenant_id", None)
        captured["ctx"] = get_request_tenant_id()
        captured["rls_intent"] = getattr(req.state, "rls_intent", None)
        return JSONResponse({"ok": True})

    await mw.dispatch(request, call_next)

    assert captured["tenant_id"] == 42
    assert captured["ctx"] == 42
    assert captured["rls_intent"] is True
    # ContextVar cleared after request
    assert get_request_tenant_id() is None


@pytest.mark.asyncio
async def test_apply_tenant_guc_issues_set_config():
    session = AsyncMock()
    bind = MagicMock()
    bind.dialect.name = "postgresql"
    session.get_bind = MagicMock(return_value=bind)

    await apply_tenant_guc(session, 7)

    session.execute.assert_awaited()
    args, _kwargs = session.execute.await_args
    sql = str(args[0])
    assert "set_config" in sql
    assert "app.current_tenant_id" in sql
    params = args[1] if len(args) > 1 else _kwargs
    assert params["tid"] == "7"


@pytest.mark.asyncio
async def test_apply_tenant_guc_noop_on_sqlite():
    session = AsyncMock()
    bind = MagicMock()
    bind.dialect.name = "sqlite"
    session.get_bind = MagicMock(return_value=bind)

    await apply_tenant_guc(session, 7)
    session.execute.assert_not_awaited()


def test_contextvar_set_reset_roundtrip():
    assert get_request_tenant_id() is None
    token = set_request_tenant_id(99)
    assert get_request_tenant_id() == 99
    reset_request_tenant_id(token)
    assert get_request_tenant_id() is None


def test_get_db_registers_after_begin_listener():
    from src.infrastructure.database import get_db

    source = inspect.getsource(get_db)
    assert "after_begin" in source
    assert "set_config" in source
    assert "get_request_tenant_id" in source


def test_auth_dependencies_bind_tenant_guc():
    import src.api.dependencies as deps

    source = inspect.getsource(deps)
    assert "_bind_tenant_rls_guc" in source
    assert "apply_tenant_guc" in source
    assert source.count("await _bind_tenant_rls_guc") >= 2
