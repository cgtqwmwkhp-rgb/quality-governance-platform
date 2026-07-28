"""A private database for the document-control disclosure suite.

Not a test module (the leading underscore keeps pytest from collecting it). It
holds the machinery behind the ``doc_control_scratch`` and
``doc_control_scratch_client`` fixtures in ``tests/integration/conftest.py``.

Why a private database is necessary
-----------------------------------
The condition under test — a table that is not in the database — cannot occur in
the shared harness. ``tests/integration/conftest.py`` runs
``Base.metadata.create_all`` before every integration test, and ``src.main``
calls ``init_db`` whenever ``settings.is_development``, so the shared schema ends
up holding every declared table no matter what the migrations create. On CI,
Alembic runs first and ``create_all`` then fills in the seven tables Alembic
never created. A test using that database would pass whether or not the defect
were fixed — which is precisely how four of these endpoints came to be returning
500s in production with every gate green.

The tables are removed with real DDL rather than by patching an exception, so
what gets pinned is the database's behaviour and not a guess about it. The
distinction has teeth: the same absent table raises ``ProgrammingError`` on
PostgreSQL and ``OperationalError`` on SQLite, and on PostgreSQL it additionally
aborts the surrounding transaction, which is what turned one unreadable
subordinate list into a dead document-detail page.

The scratch database follows whichever ``DATABASE_URL`` the suite is running
against, so on CI this exercises Postgres.
"""

from __future__ import annotations

import os
import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

# The seven document-control tables with no create migration, verified absent
# from production. Listed child-first so the drops do not need CASCADE on a
# backend that lacks it.
ABSENT_IN_PRODUCTION: tuple[str, ...] = (
    "document_approval_actions",
    "document_approval_instances",
    "document_approval_workflows",
    "document_distributions",
    "document_training_links",
    "document_access_logs",
    "obsolete_document_records",
)

DISTRIBUTIONS_TABLE = "document_distributions"
ACCESS_LOG_TABLE = "document_access_logs"
WORKFLOWS_TABLE = "document_approval_workflows"
OBSOLETE_TABLE = "obsolete_document_records"

TENANT_ID = 1
USER_ID = 1


class ScratchDatabase:
    """A database one test owns, carrying the app's full declared schema."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self.sessions = async_sessionmaker(engine, expire_on_commit=False)

    @property
    def _is_postgres(self) -> bool:
        return self.engine.dialect.name == "postgresql"

    async def drop_tables(self, names: tuple[str, ...] = ABSENT_IN_PRODUCTION) -> None:
        """Put the schema into the shape production is actually in."""
        suffix = " CASCADE" if self._is_postgres else ""
        async with self.engine.begin() as conn:
            for name in names:
                await conn.execute(sa.text(f"DROP TABLE IF EXISTS {name}{suffix}"))

    async def has_table(self, name: str) -> bool:
        async with self.engine.connect() as conn:
            return await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).has_table(name))

    async def seed_tenant_and_user(self) -> None:
        """The two rows every document write needs a foreign key onto."""
        from tests.factories import TenantFactory, UserFactory

        async with self.sessions() as session:
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
            await session.commit()

    async def view_count(self, document_id: int) -> int:
        """Read ``view_count`` straight from the table.

        The detail endpoint increments this in the same commit that used to carry
        the access-log INSERT, so it is the cheapest evidence that the commit now
        happens at all.
        """
        async with self.sessions() as session:
            result = await session.execute(
                sa.text("SELECT view_count FROM controlled_documents WHERE id = :id"),
                {"id": document_id},
            )
            return int(result.scalar_one())

    async def document_status(self, document_id: int) -> tuple[str, bool]:
        """``(status, is_current)`` — what a refused write must not have changed."""
        async with self.sessions() as session:
            result = await session.execute(
                sa.text("SELECT status, is_current FROM controlled_documents WHERE id = :id"),
                {"id": document_id},
            )
            row = result.one()
            return str(row[0]), bool(row[1])


async def make_scratch_engine(tmp_path) -> tuple[AsyncEngine, object]:
    """Build an empty database beside whichever backend the suite is using."""
    base_url = os.environ.get("DATABASE_URL", "")

    if base_url.startswith("sqlite"):
        return create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'doc-control-disclosure.db'}"), None

    name = f"qgp_doc_control_disclosure_{uuid.uuid4().hex[:12]}"
    admin = create_async_engine(base_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            await conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    finally:
        await admin.dispose()

    url = sa.engine.make_url(base_url).set(database=name).render_as_string(hide_password=False)
    return create_async_engine(url), name


async def drop_scratch_database(name: str) -> None:
    base_url = os.environ["DATABASE_URL"]
    admin = create_async_engine(base_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            await conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}"'))
    finally:
        await admin.dispose()
