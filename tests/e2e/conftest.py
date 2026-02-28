"""E2E Test Configuration."""

import pytest


@pytest.fixture(scope="session", autouse=True)
async def _seed_default_tenant():
    """Ensure a default tenant exists for E2E tests."""
    from sqlalchemy import text

    from src.infrastructure.database import engine

    try:
        async with engine.begin() as conn:
            result = await conn.execute(text("SELECT id FROM tenants WHERE id = 1"))
            if result.fetchone() is None:
                await conn.execute(
                    text(
                        "INSERT INTO tenants (id, name, slug, admin_email) "
                        "VALUES (1, 'E2E Test Tenant', 'e2e-test', 'e2e@test.example.com') "
                        "ON CONFLICT (id) DO NOTHING"
                    )
                )
    except Exception:
        pass
