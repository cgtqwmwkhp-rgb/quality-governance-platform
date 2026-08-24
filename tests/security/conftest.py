"""Give the OWASP suite a database of its own, and never the ambient one.

The suite in this directory deliberately sends SQL injection, command
injection, mass-assignment and path-traversal payloads at the application, and
it reaches the application in-process through ``TestClient``, so it writes to
whatever database ``src.core.config`` resolved at import time. Two things
follow from that.

First, the tests could not run at all. They authenticate through
``tests/conftest.py``'s ``auth_headers``, which performs a real
``POST /api/v1/auth/login``. In CI there was no database and no test user, the
login returned a 5xx, ``_build_test_auth_headers`` treated that as "auth
backend unavailable", and ten tests called ``pytest.skip("Auth required")``
while the workflow reported success. The suite has never exercised its subject.

Second, handing it a DSN is not a neutral act. ``settings.database_url``
defaults to ``postgresql+asyncpg://postgres:password@localhost:5432/quality_governance``
— a developer's real local database, not a scratch one — and an exported
``DATABASE_URL`` overrides even that. So this module resolves the DSN itself
and *overwrites* ``DATABASE_URL``: an ambient value is discarded rather than
inherited. The DSN it chooses must be local (``tests/_dsn_guard``) and must
also name itself as a test database, because "local" alone still includes the
developer's working database.
"""

from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from tests._dsn_guard import assert_test_database_is_local

# The only channel by which a DSN may be supplied to this suite. DATABASE_URL is
# deliberately not consulted: it is the variable that carries a live deployment
# into a shell by accident, and this suite must never be able to reach one.
_DSN_ENV = "SECURITY_TEST_DATABASE_URL"

_DEFAULT_SQLITE_PATH = Path(tempfile.gettempdir()) / f"qgp-test-security-{os.getpid()}.db"
_DEFAULT_DSN = f"sqlite+aiosqlite:///{_DEFAULT_SQLITE_PATH}"

# A non-SQLite DSN must say so in its database name. The host allow-list in
# tests/_dsn_guard admits localhost, which is where the developer's own
# quality_governance database lives; this is the check that keeps the payloads
# out of it.
_TEST_DB_NAME_MARKERS = ("test", "scratch", "throwaway", "disposable")


class UnsafeSecurityTestDatabaseError(RuntimeError):
    """Raised when the DSN for this suite is not demonstrably disposable."""


def _database_name(dsn: str) -> str:
    scheme, _, rest = dsn.partition("://")
    base_scheme = scheme.split("+", 1)[0]
    try:
        path = urlsplit(f"{base_scheme}://{rest}").path
    except ValueError:
        return ""
    return path.lstrip("/").split("?", 1)[0]


def assert_database_is_disposable(dsn: str) -> None:
    """Refuse any DSN that is not local *and* named as a test database.

    Raises rather than warns: the failure being defended against here is a
    suite that quietly points somewhere it should not.
    """
    assert_test_database_is_local(dsn)

    scheme = dsn.partition("://")[0].split("+", 1)[0].lower()
    if scheme.startswith("sqlite"):
        return

    name = _database_name(dsn).lower()
    if any(marker in name for marker in _TEST_DB_NAME_MARKERS):
        return

    raise UnsafeSecurityTestDatabaseError(
        "Refusing to run the security suite against this database.\n"
        f"  database name: {name or '<none>'}\n"
        "These tests send SQL injection, command injection, mass-assignment and "
        "path-traversal payloads, and they write to the database they are given. "
        f"The name must contain one of {list(_TEST_DB_NAME_MARKERS)} so that a "
        "disposable database cannot be confused with a working one. Set "
        f"{_DSN_ENV} to a throwaway database, or leave it unset to use a "
        "temporary SQLite file."
    )


def _resolve_dsn() -> str:
    configured = (os.environ.get(_DSN_ENV) or "").strip()
    return configured or _DEFAULT_DSN


_RESOLVED_DSN = _resolve_dsn()
assert_database_is_disposable(_RESOLVED_DSN)

# Assignment, not setdefault: an ambient DATABASE_URL is replaced. This runs at
# conftest import, before any fixture imports src.core.config and caches
# settings.
#
# TESTING=1 is deliberately NOT set, unlike the integration harness. That flag
# makes rate_limit_middleware return early (src/infrastructure/middleware/
# rate_limiter.py), and this suite asserts on the X-RateLimit headers that
# middleware adds — setting it would turn a passing rate-limit test red while
# looking like an unrelated tidy-up. The engine already selects NullPool for any
# pytest process, so nothing here needs the flag.
os.environ["DATABASE_URL"] = _RESOLVED_DSN


# The persona these tests assume: a signed-in user who is not an administrator.
# Read grants matter — without them the injection probes are answered 403 before
# a query is ever built, and the tests pass having proved nothing. Only tokens
# in src/domain/authz/catalogue.py ENFORCED_PERMISSIONS are granted.
_SECURITY_TEST_ROLE = "security-test-user"
_SECURITY_TEST_PERMISSIONS = ",".join(
    [
        "incident:read",
        "incident:create",
        "complaint:read",
        "near_miss:read",
        "document:read",
        "audit:read",
    ]
)


async def _create_schema_and_seed(test_email: str, test_password: str) -> None:
    """Create the schema if absent and seed the tenant, role and user login needs."""
    from sqlalchemy import select

    import src.domain.models  # noqa: F401  — registers every model on Base.metadata
    from src.core.security import get_password_hash
    from src.domain.models.tenant import Tenant
    from src.domain.models.user import Role, User
    from src.infrastructure.database import Base, async_session_maker, engine

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with async_session_maker() as session:
        tenant = (await session.execute(select(Tenant).where(Tenant.id == 1))).scalar_one_or_none()
        if tenant is None:
            session.add(
                Tenant(
                    id=1,
                    name="Security Test Tenant",
                    slug="security-test-tenant",
                    admin_email="admin@security-test.example.com",
                    is_active=True,
                )
            )
            await session.flush()

        role = (await session.execute(select(Role).where(Role.name == _SECURITY_TEST_ROLE))).scalar_one_or_none()
        if role is None:
            role = Role(
                name=_SECURITY_TEST_ROLE,
                description="Non-admin persona used by tests/security",
                permissions=_SECURITY_TEST_PERMISSIONS,
            )
            session.add(role)
            await session.flush()
        else:
            role.permissions = _SECURITY_TEST_PERMISSIONS

        user = (await session.execute(select(User).where(User.email == test_email))).scalar_one_or_none()
        if user is None:
            user = User(
                email=test_email,
                hashed_password=get_password_hash(test_password),
                first_name="Security",
                last_name="Test",
                is_active=True,
                is_superuser=False,
                tenant_id=1,
            )
            session.add(user)
            await session.flush()
        else:
            # A re-run against the same disposable database must still be able
            # to log in, whatever a previous run left behind.
            user.hashed_password = get_password_hash(test_password)
            user.is_active = True
            user.is_superuser = False
            user.tenant_id = 1

        await session.refresh(user, attribute_names=["roles"])
        if all(existing.id != role.id for existing in user.roles):
            user.roles.append(role)

        await session.commit()

    await engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def security_test_database(test_config) -> None:
    """Point the application at a disposable database and seed the login it needs.

    The DSN is re-checked here against the engine the application actually
    opened, not against the value resolved above: another conftest on the same
    pytest invocation can import ``src.main`` first and win the race to
    ``settings``. Whatever the application ended up holding is what these
    payloads will hit, so that is what has to be proven disposable.
    """
    from src.infrastructure.database import engine

    effective_dsn = engine.url.render_as_string(hide_password=False)
    try:
        assert_database_is_disposable(effective_dsn)
    except Exception as exc:  # noqa: BLE001 — refuse the session, do not skip it
        pytest.exit(f"tests/security refused to run: {exc}", returncode=4)

    # asyncio.run gets its own loop, which is safe here because the test engine
    # is built with NullPool (see src/infrastructure/database.py), so no
    # connection outlives this call to be reused on the TestClient's loop.
    asyncio.run(
        _create_schema_and_seed(
            test_config.TEST_USER_EMAIL.lower(),
            test_config.TEST_USER_PASSWORD,
        )
    )
