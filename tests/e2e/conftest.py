"""E2E Test Configuration.

Uses per-test database cleanup for isolation.
"""

import pytest

_CLEANUP_TABLES = [
    "audit_events",
    "audit_questions",
    "audit_sections",
    "audit_run_responses",
    "audit_runs",
    "audit_templates",
    "actions",
    "investigation_runs",
    "investigations",
    "complaints",
    "incidents",
    "near_misses",
    "risks",
    "policies",
    "standards",
    "users",
]


@pytest.fixture(scope="session", autouse=True)
async def _seed_default_tenant():
    """Ensure a default tenant exists for E2E tests."""
    from sqlalchemy import select

    from src.domain.models.tenant import Tenant
    from src.infrastructure.database import async_session_maker

    try:
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


@pytest.fixture(autouse=True)
async def _cleanup_test_data():
    """Delete test data after each test for isolation."""
    yield

    from sqlalchemy import text

    from src.infrastructure.database import async_session_maker

    try:
        async with async_session_maker() as session:
            for table in _CLEANUP_TABLES:
                await session.execute(text(f"DELETE FROM {table}"))
            await session.commit()
    except Exception:
        pass
