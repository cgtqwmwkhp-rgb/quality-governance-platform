"""A private database for the policy-acknowledgment honesty suites.

Not a test module (the leading underscore keeps pytest from collecting it). It
holds the harness shared by ``test_policy_ack_dashboard_honesty`` and
``test_policy_ack_my_pending_honesty``, both of which need to observe a table
that is genuinely absent.

Why a private database is necessary
-----------------------------------
The missing-table condition is invisible in the default harness. ``src.main``
calls :func:`init_db` (and therefore ``create_all``) whenever
``settings.is_development``, and ``tests/integration/conftest.py`` has an autouse
fixture that runs ``Base.metadata.create_all`` before every integration test. CI
applies Alembic first and then that fixture, so the shared schema always ends up
containing every declared table regardless of what the migrations create. A test
using the shared database could not observe an absent table and would pass
whether or not the defect were fixed.

The table is dropped with real DDL rather than by mocking an exception, so what
gets pinned is the database's behaviour and not a guess about which exception it
raises. That distinction has teeth here: the same absent table raises
``ProgrammingError`` on PostgreSQL and ``OperationalError`` on SQLite, and the
handlers these suites cover used to catch only the former.

The scratch database follows whatever ``DATABASE_URL`` the suite is running
against, so on CI this exercises Postgres.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import AsyncIterator

import pytest
import sqlalchemy as sa
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

from src.infrastructure.database import get_db
from src.main import app

BACKING_TABLE = "policy_acknowledgments"

TENANT_ID = 1
USER_ID = 1


class ScratchDatabase:
    """A database this test owns, with the app's full declared schema."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self.sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def drop_backing_table(self) -> None:
        async with self.engine.begin() as conn:
            await conn.execute(sa.text(f"DROP TABLE IF EXISTS {BACKING_TABLE}"))

    async def has_backing_table(self) -> bool:
        async with self.engine.connect() as conn:
            return await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).has_table(BACKING_TABLE))

    async def seed_acknowledgments(self, statuses: tuple[str, ...]) -> None:
        """Assign one acknowledgment per status, so a real count is not zero."""
        from src.domain.models.policy_acknowledgment import PolicyAcknowledgment, PolicyAcknowledgmentRequirement
        from tests.factories import PolicyFactory, TenantFactory, UserFactory

        now = datetime.now(timezone.utc)
        async with self.sessions() as session:
            # The database is this test's own, so these rows exist only to satisfy
            # the foreign keys Postgres enforces on the acknowledgments below.
            session.add(
                TenantFactory.build(
                    id=TENANT_ID,
                    name="Scratch Tenant",
                    slug=f"scratch-{uuid.uuid4().hex[:8]}",
                    admin_email="admin@scratch.example.com",
                )
            )
            await session.flush()

            session.add(
                UserFactory.build(
                    id=USER_ID,
                    email=f"scratch-{uuid.uuid4().hex[:8]}@example.com",
                    hashed_password="unused",
                    is_active=True,
                    is_superuser=False,
                    tenant_id=TENANT_ID,
                )
            )
            policy = PolicyFactory.build(tenant_id=TENANT_ID)
            session.add(policy)
            await session.flush()

            requirement = PolicyAcknowledgmentRequirement(
                tenant_id=TENANT_ID,
                policy_id=policy.id,
                due_within_days=30,
                is_active=True,
            )
            session.add(requirement)
            await session.flush()

            for status in statuses:
                session.add(
                    PolicyAcknowledgment(
                        tenant_id=TENANT_ID,
                        requirement_id=requirement.id,
                        policy_id=policy.id,
                        user_id=USER_ID,
                        status=status,
                        assigned_at=now,
                        due_date=now + timedelta(days=30),
                    )
                )
            await session.commit()


async def _make_scratch_engine(tmp_path) -> tuple[AsyncEngine, object]:
    """Build an empty database beside whichever backend the suite is using."""
    base_url = os.environ.get("DATABASE_URL", "")

    if base_url.startswith("sqlite"):
        url = f"sqlite+aiosqlite:///{tmp_path / 'ack-honesty.db'}"
        return create_async_engine(url), None

    name = f"qgp_ack_honesty_{uuid.uuid4().hex[:12]}"
    admin = create_async_engine(base_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            await conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    finally:
        await admin.dispose()

    url = sa.engine.make_url(base_url).set(database=name).render_as_string(hide_password=False)
    return create_async_engine(url), name


async def _drop_scratch_database(name: str) -> None:
    base_url = os.environ["DATABASE_URL"]
    admin = create_async_engine(base_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            await conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}"'))
    finally:
        await admin.dispose()


@pytest.fixture
async def scratch(tmp_path) -> AsyncIterator[ScratchDatabase]:
    """A database carrying the app's declared schema, owned by one test."""
    import src.domain.models  # noqa: F401  — registers models on Base.metadata
    from src.infrastructure.database import Base

    engine, created_name = await _make_scratch_engine(tmp_path)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield ScratchDatabase(engine)
    finally:
        await engine.dispose()
        if created_name is not None:
            await _drop_scratch_database(created_name)


@pytest.fixture
async def scratch_client(scratch: ScratchDatabase) -> AsyncIterator[AsyncClient]:
    """An authenticated client whose requests read the scratch database."""
    from tests.integration.conftest import _generate_test_jwt

    async def _get_scratch_db():
        async with scratch.sessions() as session:
            yield session

    app.dependency_overrides[get_db] = _get_scratch_db
    token = _generate_test_jwt(user_id=str(USER_ID), tenant_id=TENANT_ID, role="admin")
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
            headers={"Authorization": f"Bearer {token}"},
        ) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
