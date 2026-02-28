"""E2E Test Configuration.

Uses the per-test transaction rollback pattern for complete isolation.
"""

import asyncio

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

from src.infrastructure.database import engine, get_db
from src.main import app


@pytest.fixture(scope="session", autouse=True)
def _seed_default_tenant():
    """Ensure a default tenant exists for E2E tests."""

    async def _seed():
        from sqlalchemy import select

        from src.domain.models.tenant import Tenant
        from src.infrastructure.database import async_session_maker

        async with async_session_maker() as session:
            result = await session.execute(select(Tenant).where(Tenant.id == 1))
            if result.scalar_one_or_none() is None:
                tenant = Tenant(
                    id=1,
                    name="E2E Test Tenant",
                    slug="e2e-test",
                    admin_email="e2e@test.example.com",
                )
                session.add(tenant)
                await session.commit()

    try:
        asyncio.run(_seed())
    except Exception:
        pass


@pytest.fixture(autouse=True)
async def _db_rollback():
    """Wrap every E2E test in a rolled-back transaction for isolation."""
    connection = await engine.connect()
    transaction = await connection.begin()

    session = AsyncSession(bind=connection, expire_on_commit=False)
    await connection.begin_nested()

    @event.listens_for(session.sync_session, "after_transaction_end")
    def _restart_savepoint(sync_session, trans):
        if trans.nested and not trans._parent.nested:
            sync_session.begin_nested()

    async def _override_get_db():
        yield session

    app.dependency_overrides[get_db] = _override_get_db

    yield session

    app.dependency_overrides.pop(get_db, None)
    await session.close()
    await transaction.rollback()
    await connection.close()
