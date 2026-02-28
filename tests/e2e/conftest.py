"""E2E Test Configuration.

Uses per-test database cleanup for isolation.
Seeds default tenant and user for FK integrity.
"""

import pytest

_CLEANUP_TABLES = [
    "audit_findings",
    "audit_responses",
    "audit_events",
    "audit_questions",
    "audit_sections",
    "audit_runs",
    "audit_templates",
    "capa_actions",
    "investigation_actions",
    "investigation_comments",
    "investigation_revision_events",
    "investigation_customer_packs",
    "investigation_runs",
    "investigation_templates",
    "actions",
    "complaint_actions",
    "complaints",
    "incident_actions",
    "incidents",
    "rta_actions",
    "road_traffic_collisions",
    "near_misses",
    "risk_controls",
    "risk_assessments",
    "risks",
    "clauses",
    "controls",
    "standards",
    "policy_versions",
    "policies",
]


@pytest.fixture(scope="session", autouse=True)
async def _seed_default_data():
    """Seed default tenant and user for E2E tests."""
    from sqlalchemy import select

    from src.core.security import get_password_hash
    from src.domain.models.tenant import Tenant
    from src.domain.models.user import User
    from src.infrastructure.database import async_session_maker

    try:
        async with async_session_maker() as session:
            result = await session.execute(select(Tenant).where(Tenant.id == 1))
            if result.scalar_one_or_none() is None:
                session.add(
                    Tenant(
                        id=1,
                        name="E2E Test Tenant",
                        slug="e2e-test",
                        admin_email="e2e@test.example.com",
                    )
                )
                await session.flush()

            result = await session.execute(select(User).where(User.id == 1))
            if result.scalar_one_or_none() is None:
                session.add(
                    User(
                        id=1,
                        email="test@example.com",
                        hashed_password=get_password_hash("testpassword123"),
                        first_name="Test",
                        last_name="User",
                        is_active=True,
                        is_superuser=False,
                        tenant_id=1,
                    )
                )
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
                try:
                    await session.execute(text(f"DELETE FROM {table}"))
                except Exception:
                    await session.rollback()
            try:
                await session.execute(text("DELETE FROM users WHERE id != 1"))
            except Exception:
                await session.rollback()
            await session.commit()
    except Exception:
        pass
