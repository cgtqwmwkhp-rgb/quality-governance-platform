"""A private database whose schema has genuinely drifted, for the C-7 / C-53 suites.

Not a test module (the leading underscore keeps pytest from collecting it). It
holds the machinery behind the ``drifted_scratch`` and
``drifted_scratch_client`` fixtures in ``tests/integration/conftest.py``.

Why a private database is necessary
-----------------------------------
The condition under test is a column that the ORM declares and the database does
not have. That cannot occur in the shared harness: ``tests/integration/conftest.py``
runs ``Base.metadata.create_all`` before every integration test, so the shared
schema always matches the models exactly. A test using that database would pass
whether or not the defect were fixed. This is the same reasoning, and the same
shape of harness, as ``_document_control_scratch``.

Why real DDL rather than a patched exception
--------------------------------------------
``ALTER TABLE ... DROP COLUMN`` reproduces what the two defects actually depend
on, which a ``raise`` in a monkeypatched method does not:

* the failure arrives as ``ProgrammingError`` from asyncpg, at the point the
  statement is executed rather than at the point the coroutine is created;
* on PostgreSQL the failing statement **aborts the surrounding transaction**, so
  every later statement in the same transaction is refused until it is unwound.
  That second property is the whole reason ``_read_savepoint`` exists, and it is
  invisible to a test that simply raises;
* a count over a table with a dropped column still *succeeds* when the count
  does not name that column, which is what makes the drift partial rather than
  total. ``SELECT count(*) FROM audit_runs WHERE tenant_id = x`` survives
  ``DROP COLUMN status``; the very next count, which filters on ``status``, does
  not. A hand-rolled failure cannot reproduce that asymmetry, and the asymmetry
  is exactly what produced a confident zero from a readable table.

PostgreSQL only
---------------
SQLite's ``ALTER TABLE DROP COLUMN`` support is version-dependent and it does not
abort transactions the way PostgreSQL does, so a SQLite run would be measuring
something other than the defect. Tests using these fixtures skip unless
``DATABASE_URL`` points at PostgreSQL, as CI's does.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker, create_async_engine

TENANT_ID = 1
USER_ID = 1

# The drift each suite induces, named so a failure message says which column is
# missing rather than just which test broke.
#
# audit_runs.status  — breaks AuditAnalyticsService.get_summary at its *second*
#   query, after the `totals` count has already succeeded. That is what makes the
#   resulting `audits.total: 0` a fabrication rather than an absence: the number
#   was readable and the endpoint published zero anyway.
# capa_actions.tenant_id — breaks every CAPA read, count and rows alike, because
#   both name the column in their WHERE clause. This is the shape a table created
#   before multi-tenancy was introduced actually has.
# incident_actions.description — breaks the *row read* while leaving the *count*
#   working, because `select(func.count())` names only the filter columns while
#   `select(IncidentAction)` names every column. This is the asymmetry that
#   produces the worst observable state in the register: a count of 3 beside an
#   empty list, at HTTP 200. It is reached without the zero-total short-circuit
#   being involved at all — see test_actions_list_partial_failure.
AUDIT_RUNS_STATUS = ("audit_runs", "status")
CAPA_ACTIONS_TENANT = ("capa_actions", "tenant_id")
INCIDENT_ACTIONS_DESCRIPTION = ("incident_actions", "description")


def is_postgres(url: str) -> bool:
    return url.startswith("postgresql")


class DriftedDatabase:
    """A database one test owns, whose schema can be made to disagree with the ORM."""

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self.sessions = async_sessionmaker(engine, expire_on_commit=False)

    async def drop_column(self, table: str, column: str) -> None:
        """Induce genuine schema drift.

        CASCADE because indexes and check constraints reference these columns;
        without it PostgreSQL refuses the drop and the test would silently be
        measuring an undrifted database.
        """
        async with self.engine.begin() as conn:
            await conn.execute(sa.text(f"ALTER TABLE {table} DROP COLUMN {column} CASCADE"))

    async def has_column(self, table: str, column: str) -> bool:
        """Confirm the drift is real, so a test cannot pass against a clean schema."""
        async with self.engine.connect() as conn:
            result = await conn.execute(
                sa.text("SELECT 1 FROM information_schema.columns " "WHERE table_name = :t AND column_name = :c"),
                {"t": table, "c": column},
            )
            return result.first() is not None

    async def seed_tenant_and_user(self) -> None:
        """The two rows every foreign key below needs."""
        from tests.factories import TenantFactory, UserFactory

        async with self.sessions() as session:
            session.add(
                TenantFactory.build(
                    id=TENANT_ID,
                    name="Drift Tenant",
                    slug=f"drift-{uuid.uuid4().hex[:8]}",
                    admin_email="admin@drift.example.com",
                )
            )
            await session.flush()
            session.add(
                UserFactory.build(
                    id=USER_ID,
                    email=f"drift-{uuid.uuid4().hex[:8]}@example.com",
                    hashed_password="unused",
                    is_active=True,
                    is_superuser=False,
                    tenant_id=TENANT_ID,
                )
            )
            await session.commit()

    async def seed_audit_runs(self, *, completed: int = 2, in_progress: int = 1) -> int:
        """Seed audit runs that a working aggregate would report.

        Returns the total seeded. Completed runs carry a ``score_percentage`` so
        the difference between "no completed run was scored" (a real None) and
        "the query failed" (also currently None) is not the only thing under test.
        """
        from src.domain.models.audit import AuditRun, AuditStatus, AuditTemplate

        async with self.sessions() as session:
            tag = uuid.uuid4().hex[:8]
            template = AuditTemplate(
                tenant_id=TENANT_ID,
                name="Drift Template",
                audit_type="inspection",
                reference_number=f"TPL-{tag}",
                created_by_id=USER_ID,
            )
            session.add(template)
            await session.flush()

            now = datetime.now(timezone.utc)
            for seq in range(completed):
                session.add(
                    AuditRun(
                        tenant_id=TENANT_ID,
                        template_id=template.id,
                        title=f"Completed run {seq}",
                        status=AuditStatus.COMPLETED.value,
                        score_percentage=90.0,
                        passed=True,
                        reference_number=f"RUN-{tag}-c{seq}",
                        created_at=now - timedelta(days=1),
                        created_by_id=USER_ID,
                    )
                )
            for seq in range(in_progress):
                session.add(
                    AuditRun(
                        tenant_id=TENANT_ID,
                        template_id=template.id,
                        title=f"In-progress run {seq}",
                        status=AuditStatus.IN_PROGRESS.value,
                        reference_number=f"RUN-{tag}-p{seq}",
                        created_at=now - timedelta(days=1),
                        created_by_id=USER_ID,
                    )
                )
            await session.commit()

        return completed + in_progress

    async def seed_capa_actions(self, count: int = 2) -> int:
        """Seed CAPA actions — the rows a fabricated zero total hides."""
        from src.domain.models.capa import CAPAAction, CAPAPriority, CAPAStatus, CAPAType

        async with self.sessions() as session:
            for seq in range(count):
                session.add(
                    CAPAAction(
                        tenant_id=TENANT_ID,
                        reference_number=f"CAPA-DRIFT-{uuid.uuid4().hex[:8]}-{seq}",
                        title=f"Drift CAPA {seq}",
                        description="Seeded to prove a failed count cannot empty the register.",
                        capa_type=CAPAType.CORRECTIVE,
                        status=CAPAStatus.OPEN,
                        priority=CAPAPriority.MEDIUM,
                        created_by_id=USER_ID,
                    )
                )
            await session.commit()
        return count

    async def seed_capa_items(self, count: int = 2) -> int:
        """Seed CAPA plan items — the store read *after* ``capa_actions``.

        Read order in ``list_actions`` is incident, rta, complaint, investigation,
        capa, capa_item. So these are the rows that a failed ``capa_actions`` read
        used to take down with it: on PostgreSQL the aborted transaction makes the
        next statement raise regardless of whether its own table is healthy.
        Seeding here is what makes that blast radius observable rather than argued.
        """
        from src.domain.models.rca_tools import CAPAItem

        async with self.sessions() as session:
            for seq in range(count):
                session.add(
                    CAPAItem(
                        tenant_id=TENANT_ID,
                        action_type="corrective",
                        title=f"Drift CAPA item {seq}",
                        description="Readable row in a healthy table, after a broken one.",
                        status="open",
                        priority="medium",
                    )
                )
            await session.commit()
        return count

    async def seed_incident_actions(self, count: int = 3) -> int:
        """Seed incident actions in a table that is *not* drifted.

        These are the rows the fix must keep returning: a partial failure has to
        degrade to "some sources are unreadable", not to a blank page.
        """
        from src.domain.models.incident import Incident, IncidentAction

        async with self.sessions() as session:
            tag = uuid.uuid4().hex[:8]
            incident = Incident(
                tenant_id=TENANT_ID,
                title="Drift incident",
                description="Parent for seeded actions.",
                incident_date=datetime.now(timezone.utc) - timedelta(days=3),
                reported_date=datetime.now(timezone.utc) - timedelta(days=3),
                reference_number=f"INC-{tag}",
                created_by_id=USER_ID,
            )
            session.add(incident)
            await session.flush()

            for seq in range(count):
                session.add(
                    IncidentAction(
                        tenant_id=TENANT_ID,
                        incident_id=incident.id,
                        title=f"Drift incident action {seq}",
                        description="Readable row beside an unreadable count.",
                        reference_number=f"IA-{tag}-{seq}",
                        created_by_id=USER_ID,
                    )
                )
            await session.commit()
        return count


async def make_drifted_engine() -> tuple[AsyncEngine, str]:
    """Build an empty PostgreSQL database beside whichever one the suite is using."""
    base_url = os.environ.get("DATABASE_URL", "")
    if not is_postgres(base_url):
        raise RuntimeError("the drifted-schema harness requires PostgreSQL; see module docstring")

    name = f"qgp_fabricated_zero_{uuid.uuid4().hex[:12]}"
    admin = create_async_engine(base_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            await conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    finally:
        await admin.dispose()

    url = sa.engine.make_url(base_url).set(database=name).render_as_string(hide_password=False)
    return create_async_engine(url), name


async def drop_drifted_database(name: str) -> None:
    base_url = os.environ["DATABASE_URL"]
    admin = create_async_engine(base_url, isolation_level="AUTOCOMMIT")
    try:
        async with admin.connect() as conn:
            await conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}"'))
    finally:
        await admin.dispose()
