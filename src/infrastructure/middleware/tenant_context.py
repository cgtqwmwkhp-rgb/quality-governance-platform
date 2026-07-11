"""Tenant context middleware for PostgreSQL Row-Level Security.

Auth resolves the tenant after ``get_db`` has already opened the request
session, so this middleware does **not** bind the tenant GUC on a throwaway
connection. Instead it:

1. Skips health/docs paths
2. Reads tenant_id from ``request.state`` when present (or from ``request.state.user``)
3. Sets a ContextVar so ``get_db`` can re-apply the GUC on ``after_begin``
4. Stores ``request.state.tenant_id`` for downstream code
5. Clears the ContextVar in ``finally``

The actual ``set_config('app.current_tenant_id', ..., true)`` bind happens on
the real request session via ``apply_tenant_guc`` from auth dependencies
(and via the ``after_begin`` listener in ``get_db`` for later transactions).

Users with a ``tenant_id`` (including app ``is_superuser``) get the GUC set so
FORCE RLS policies match their tenant. Cross-tenant admin requires a DB role
with BYPASSRLS (e.g. ``qgp_migrations``), not an unset GUC.
"""

from __future__ import annotations

import logging
from contextvars import ContextVar, Token
from typing import Callable, Optional

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

SKIP_PATHS = frozenset(
    {
        "/",
        "/health",
        "/healthz",
        "/readyz",
        "/.well-known/security.txt",
        "/api/v1/privacy/contact",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
)

# Tables with tenant_isolation policies (USING + WITH CHECK).
# Original 12 from 20260222_add_row_level_security / 20260710_force_rls;
# expanded in 20260711_rls_with_check_expand (policies, audit_findings,
# investigation_actions) and 20260711_rls_force_expand_actions
# (incident_actions, complaint_actions, rta_actions).
RLS_TABLES = (
    "incidents",
    "complaints",
    "risks",
    "capa_actions",
    "audit_runs",
    "investigation_runs",
    "documents",
    "near_misses",
    "road_traffic_collisions",
    "workflow_rules",
    "users",
    "audit_log_entries",
    "policies",
    "audit_findings",
    "investigation_actions",
    "incident_actions",
    "complaint_actions",
    "rta_actions",
)

_current_tenant_id: ContextVar[Optional[int]] = ContextVar("current_tenant_id", default=None)


def get_request_tenant_id() -> Optional[int]:
    """Return the tenant id bound for the current request, if any."""
    return _current_tenant_id.get()


def set_request_tenant_id(tenant_id: Optional[int]) -> Token:
    """Set the request-scoped tenant id ContextVar; return a reset token."""
    return _current_tenant_id.set(tenant_id)


def reset_request_tenant_id(token: Token) -> None:
    """Reset the request-scoped tenant id ContextVar using a prior token."""
    _current_tenant_id.reset(token)


async def apply_tenant_guc(session, tenant_id: int) -> None:
    """Bind ``app.current_tenant_id`` on the real request DB session (transaction-local).

    Uses ``set_config(..., true)`` so the GUC is local to the current transaction.
    No-ops gracefully on SQLite / non-PostgreSQL so unit tests keep working.
    """
    from sqlalchemy import text

    try:
        bind = session.get_bind()
        dialect_name = getattr(getattr(bind, "dialect", None), "name", None)
        if dialect_name is not None and dialect_name != "postgresql":
            return
    except Exception:
        # AsyncSession may not expose bind the same way in all contexts; try execute.
        pass

    try:
        await session.execute(
            text("SELECT set_config('app.current_tenant_id', :tid, true)"),
            {"tid": str(tenant_id)},
        )
    except Exception:
        logger.debug(
            "apply_tenant_guc skipped (non-PostgreSQL or set_config unavailable)",
            exc_info=True,
        )


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Propagate tenant intent for RLS; GUC bind happens on the request session.

    Middleware runs before auth, and ``get_current_user`` Depends on ``get_db``,
    so the session exists before the tenant is known. This middleware therefore
    only sets/clears the ContextVar and ``request.state.tenant_id`` when a tenant
    is already present on the request. Auth calls ``apply_tenant_guc`` on the
    same ``get_db`` session after tenant resolution; ``get_db`` re-applies the
    GUC on ``after_begin`` for later transactions in the same request.

    Skipped for health-check / docs endpoints. When ``tenant_id`` is missing,
    no ContextVar is set (fail-closed under FORCE RLS). App superusers with a
    tenant_id still receive the GUC (tenant-scoped); cross-tenant access needs
    BYPASSRLS on the DB role.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id is None:
            user = getattr(request.state, "user", None)
            if user is not None and hasattr(user, "tenant_id"):
                tenant_id = user.tenant_id

        token: Optional[Token] = None
        try:
            if tenant_id is not None:
                request.state.tenant_id = tenant_id
                request.state.rls_intent = True
                token = set_request_tenant_id(int(tenant_id))
            return await call_next(request)
        finally:
            if token is not None:
                reset_request_tenant_id(token)
