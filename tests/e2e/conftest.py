"""E2E Test Configuration.

Uses per-test database cleanup for isolation.
Seeds default tenant and user for FK integrity.
Overrides ``get_current_user`` so authenticated endpoints return 200.
"""

import pytest

from src.api.dependencies import get_current_user
from src.main import app


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

        from sqlalchemy import text

        from src.infrastructure.database import engine

        async with engine.begin() as conn:
            await conn.execute(text("SELECT setval('tenants_id_seq', GREATEST((SELECT MAX(id) FROM tenants), 1))"))
            await conn.execute(text("SELECT setval('users_id_seq', GREATEST((SELECT MAX(id) FROM users), 1))"))
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Auth override – every E2E test gets a superuser mock
# ---------------------------------------------------------------------------

_ADMIN_PERMS = ",".join(
    [
        "incident:create",
        "incident:read",
        "incident:update",
        "incident:delete",
        "complaint:create",
        "complaint:read",
        "complaint:update",
        "complaint:delete",
        "rta:create",
        "rta:read",
        "rta:update",
        "rta:delete",
        "policy:create",
        "policy:read",
        "policy:update",
        "policy:delete",
        "action:create",
        "action:read",
        "action:update",
        "action:delete",
        "investigation:create",
        "investigation:read",
        "investigation:update",
        "audit:create",
        "audit:read",
        "audit:update",
        "audit:delete",
        "standard:create",
        "standard:read",
        "standard:update",
        "risk:create",
        "risk:read",
        "risk:update",
        "near_miss:create",
        "near_miss:read",
        "near_miss:update",
        "audit_template:create",
        "audit_template:read",
        "audit_template:update",
        "audit_template:delete",
    ]
)


class _MockRole:
    def __init__(self):
        self.id = 1
        self.name = "admin"
        self.permissions = _ADMIN_PERMS
        self.description = None
        self.is_system_role = False


class _MockUser:
    def __init__(self):
        self.id = 1
        self.email = "test@example.com"
        self.first_name = "Test"
        self.last_name = "User"
        self.hashed_password = "unused"
        self.job_title = None
        self.department = None
        self.phone = None
        self.is_active = True
        self.is_superuser = True
        self.tenant_id = 1
        self.last_login = None
        self.azure_oid = None
        self.roles = [_MockRole()]

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"

    def has_permission(self, permission):
        return True


@pytest.fixture(autouse=True)
def _override_auth(request):
    """Override ``get_current_user`` for E2E tests.

    Tests marked with ``@pytest.mark.no_auth_override`` are excluded so
    they can verify 401 / authentication behaviour.
    """
    if "no_auth_override" in request.keywords:
        yield
        return

    async def _mock_get_current_user():
        return _MockUser()

    app.dependency_overrides[get_current_user] = _mock_get_current_user
    yield
    app.dependency_overrides.pop(get_current_user, None)


# ---------------------------------------------------------------------------
# Quarantine hooks – skip Phase 3/4 tests that hit unimplemented endpoints
# ---------------------------------------------------------------------------


def pytest_configure(config):
    """Register custom markers for E2E tests."""
    config.addinivalue_line(
        "markers",
        "phase34: marks tests requiring Phase 3/4 features (quarantined)",
    )
    config.addinivalue_line(
        "markers",
        "no_auth_override: skip the autouse auth override for this test",
    )


def pytest_collection_modifyitems(config, items):
    """Auto-skip quarantined tests."""
    skip_phase34 = pytest.mark.skip(reason="QUARANTINED [GOVPLAT-001]: Phase 3/4 not implemented. Expiry: 2026-03-23")
    for item in items:
        if "phase34" in item.keywords:
            item.add_marker(skip_phase34)
