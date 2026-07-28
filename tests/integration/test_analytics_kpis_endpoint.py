"""Regression tests for ``GET /api/v1/analytics/kpis``.

The endpoint returned HTTP 500 on staging and production while every aggregate it
composes returned 200 on its own. The cause was session-scoped, not query-scoped:

1. ``_get_kri_summary`` selects the ``KeyRiskIndicator`` entity, which maps
   ``created_by_id``/``updated_by_id`` via ``AuditTrailMixin``. A migrated
   PostgreSQL database has ``created_by``/``updated_by`` instead, so that
   statement fails on every request.
2. ``ExecutiveDashboardService._safe_call`` swallows the failure and rolls the
   session back, so PostgreSQL's aborted transaction cannot poison later
   statements (#1388).
3. A rollback **expires every ORM instance in that session**. ``get_current_user``
   loads the ``User`` on the request session, so ``current_user`` is expired too.
4. Reading ``current_user.tenant_id`` after that point made SQLAlchemy emit a
   lazy refresh — synchronous IO on an async session — raising ``MissingGreenlet``.

Two properties of the default harness hid this, so both are deliberately undone
below. Without them these tests pass against the broken code and prove nothing:

* ``_override_auth`` swaps in a ``get_current_user`` that loads the user on its
  own ``async_session_maker()`` session. An instance owned by another session is
  never expired by the request session's rollback, so step 3 cannot happen.
* ``_bootstrap_test_schema`` builds the schema with ``Base.metadata.create_all``,
  i.e. from the models, so the drifted column of step 1 always exists. These
  tests therefore inject the sub-query failure directly instead of relying on
  schema shape, which also makes them backend-independent: the expiry in step 3
  is ORM behaviour, so this reproduces on SQLite and PostgreSQL alike.
"""

from typing import Annotated

import pytest
from fastapi import Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.api.dependencies import get_current_user
from src.domain.models.user import User
from src.domain.services.executive_dashboard import ExecutiveDashboardService
from src.infrastructure.database import get_db
from src.main import app

TENANT_ID = 1


async def _request_session_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Load the current user on the request session, as production does."""
    result = await db.execute(select(User).where(User.id == 1).options(selectinload(User.roles)))
    return result.scalar_one()


@pytest.fixture(autouse=True)
def _override_auth():
    """Shadow the conftest DB-free auth mock with the production wiring."""
    app.dependency_overrides[get_current_user] = _request_session_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def failing_kri_subquery(monkeypatch):
    """Make one dashboard sub-query fail, as the KRI schema drift does in production."""

    async def _boom(self):
        await self.db.execute(text("SELECT column_that_does_not_exist FROM tenants"))
        raise AssertionError("unreachable: the statement above must fail")

    monkeypatch.setattr(ExecutiveDashboardService, "_get_kri_summary", _boom)


@pytest.mark.asyncio
async def test_kpis_survives_a_dashboard_subquery_failure_on_the_shared_session(
    admin_client,
    failing_kri_subquery,
):
    """A rolled-back sub-query must not 500 the endpoint via an expired ``current_user``."""
    response = await admin_client.get("/api/v1/analytics/kpis")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["period_days"] == 30
    # Proves the tenant-scoped aggregates still ran after the rollback rather than
    # the handler bailing out early.
    assert body["source"] == "executive_dashboard"
    assert isinstance(body["actions"]["total"], int)
    assert isinstance(body["actions"]["overdue"], int)


@pytest.mark.asyncio
async def test_kpis_reports_an_uncomputable_kri_score_as_null_not_zero(
    admin_client,
    failing_kri_subquery,
):
    """A KRI figure that could not be computed must not be served as a real 0."""
    response = await admin_client.get("/api/v1/analytics/kpis")

    assert response.status_code == 200, response.text
    components = response.json()["health_score"]["components"]
    assert components["kri_performance"] is None
