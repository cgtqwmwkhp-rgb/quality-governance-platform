"""E2E Test Configuration."""

import pytest


@pytest.fixture(scope="session", autouse=True)
async def _seed_default_tenant():
    """Ensure a default tenant exists for E2E tests."""
    from sqlalchemy import text

    from src.infrastructure.database import engine

    try:
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession

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
    except Exception:
        pass
