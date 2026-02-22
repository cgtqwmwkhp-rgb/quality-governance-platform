"""Tenant context middleware for PostgreSQL Row-Level Security.

Sets ``app.current_tenant_id`` on the database connection so that RLS
policies can enforce tenant isolation transparently.  Uses ``SET LOCAL``
so the GUC is scoped to the current transaction and automatically reset
on commit/rollback.
"""

import logging
from typing import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)

SKIP_PATHS = frozenset(
    {
        "/",
        "/health",
        "/healthz",
        "/readyz",
        "/docs",
        "/redoc",
        "/openapi.json",
    }
)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Inject the authenticated user's tenant_id into the DB connection.

    The middleware reads ``tenant_id`` from ``request.state`` (populated by
    the auth layer) and issues a ``SET LOCAL app.current_tenant_id`` on a
    fresh DB connection so PostgreSQL RLS policies can filter rows.

    Skipped for:
    - Unauthenticated requests (no tenant_id on request.state)
    - Superuser requests (superusers bypass RLS by design)
    - Health-check / docs endpoints
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if request.url.path in SKIP_PATHS:
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id is None:
            user = getattr(request.state, "user", None)
            if user is not None and hasattr(user, "tenant_id"):
                tenant_id = user.tenant_id

        if tenant_id is None:
            return await call_next(request)

        is_superuser = getattr(getattr(request.state, "user", None), "is_superuser", False)
        if is_superuser:
            return await call_next(request)

        # Store resolved tenant_id so downstream code can reference it
        request.state.tenant_id = tenant_id

        from sqlalchemy import text
        from src.infrastructure.database import async_session_maker

        async with async_session_maker() as session:
            await session.execute(
                text("SET LOCAL app.current_tenant_id = :tid"),
                {"tid": str(tenant_id)},
            )
            await session.commit()

        return await call_next(request)
