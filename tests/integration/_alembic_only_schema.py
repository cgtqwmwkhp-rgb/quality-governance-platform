"""A database built by the migrations and nothing else.

Not a test module (the leading underscore keeps pytest from collecting it). It
holds the machinery behind the ``alembic_only_schema`` fixture in
``tests/integration/conftest.py``.

Why a separate database is necessary
------------------------------------
Production's schema is built by Alembic. Both CI test databases are built from the
SQLAlchemy models by ``Base.metadata.create_all`` -- ``tests/integration/conftest.py``
runs it as an autouse fixture, and ``src.main`` calls ``init_db`` whenever
``settings.is_development``, which the Locust workflow sets. So any table a model
declares that no migration creates is present in every test database and absent
from every deployment.

The consequence is not that tests fail dishonestly. It is worse: they pass
honestly, and their passing carries no information about production. A reachability
test for an endpoint over an unmigrated table is green either way. Seven tables
remain in that position on the current main -- sixteen before C-67 migrated the
push-notification pair and C-24 the document-control children -- and endpoints
over the seven document-control tables returned 500s in production while every
gate was green.

The only way to say something true about production from CI is to hold a database
the migrations built and ``create_all`` never touched, which is what this module
provides. It costs one ``alembic upgrade head`` per test session -- measured at
4.7s against PostgreSQL 16.14 and 7.3s against 14.20 locally -- so the fixture is
session-scoped and the cost is paid once.

Deliberately not reused: the ``doc_control_scratch`` fixture builds its schema with
``create_all`` and then DROPs the seven tables. That is the right tool for pinning
endpoint *behaviour* against a known-absent table, and it is exact about the seven
it drops. It cannot answer the question this module exists for -- "which tables
does the migration chain actually fail to create" -- because the answer is supplied
by the same ``create_all`` it starts from.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import sqlalchemy as sa

REPO_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class UnmigratedTable:
    """A table the running app declares that ``alembic upgrade head`` does not create.

    ``reader`` is an endpoint that returns 200 against the ``create_all`` harness.
    Where one exists it is the point of the exercise: the green is real and means
    nothing about a deployment.

    ``in_alembic_metadata`` records whether ``alembic check`` can see the table at
    all. Two of these tables are declared inside an API route module rather than
    under ``src/domain/models/``, and ``alembic/env.py`` imports only the latter, so
    the drift gate has no knowledge of them. They are not deferred on the exclusion
    register; they are outside the comparison, which is why no gate has ever
    mentioned them.
    """

    table: str
    owner: str
    declared_in: str
    reader: Optional[str] = None
    in_alembic_metadata: bool = True


#: Declared rather than derived from the schema, on purpose. Deriving the list from
#: "tables absent from the Alembic database" would make the assertion that they are
#: absent circular, and the test would keep passing while the set silently changed.
#: This is a claim about the repository that the suite checks; when a migration
#: lands, that entry's assertions fail and the entry must be deleted. That is the
#: intended way for this tuple to shrink.
#:
#: The left-hand side is the metadata the *running application* carries, because
#: that is what the test harness hands to ``create_all`` and what the endpoints
#: read. It is not the metadata ``alembic/env.py`` compares against, and the
#: difference is not small: measured 2026-07-29, the app declares 230 tables and
#: env.py's import set declares 248, each containing tables the other does not.
#: ``load_metadata()`` cannot be used here to get env.py's view -- importing that
#: set into a live app process registers a second class named ``Role`` and breaks
#: SQLAlchemy mapper configuration for the rest of the session.
#:
#: Measured against `alembic upgrade head` on PostgreSQL 14.20 and 16.14: app
#: declares these 7 tables that the migration chain does not create. (The push
#: notification pair that used to sit here was migrated in C-67 / 20260903_push_notif,
#: and the seven document-control children in C-24 / 20260906_doc_ctl_children.)
DECLARED_BUT_UNMIGRATED: tuple[UnmigratedTable, ...] = (
    # The seven document-control child tables that used to head this tuple were
    # migrated on 2026-09-06 by `20260906_doc_ctl_children` (C-24) and removed
    # from the exclusion register in the same PR, so `alembic check` now compares
    # them and this module has nothing left to say about them.
    #
    # IMS unification: seven models with no migration and, as measured, no reader
    # anywhere in src/ either. Nothing is breaking; they are recorded so that
    # wiring a route to one of them is a visible decision rather than a 500.
    UnmigratedTable("ims_controls", "IMS / ISO27001", "src/domain/models/ims_unification.py"),
    UnmigratedTable("ims_control_requirement_mappings", "IMS / ISO27001", "src/domain/models/ims_unification.py"),
    UnmigratedTable("ims_objectives", "IMS / ISO27001", "src/domain/models/ims_unification.py"),
    UnmigratedTable("ims_process_maps", "IMS / ISO27001", "src/domain/models/ims_unification.py"),
    UnmigratedTable("management_reviews", "IMS / ISO27001", "src/domain/models/ims_unification.py"),
    UnmigratedTable("management_review_inputs", "IMS / ISO27001", "src/domain/models/ims_unification.py"),
    UnmigratedTable("unified_audit_plans", "Risk / Audit", "src/domain/models/ims_unification.py"),
)

#: Tables the drift gate is structurally unable to report on, because the module
#: declaring them is not on ``alembic/env.py``'s import list. Distinct from the
#: exclusion register: an excluded table is a recorded decision with an owner,
#: whereas these were never a decision at all.
#:
#: Empty after C-67 moved ``push_subscriptions`` / ``notification_logs`` into
#: ``src/domain/models/push_notification.py``. Kept as a derived tuple so a future
#: route-declared model reintroduces the failure mode visibly.
OUTSIDE_ALEMBIC_METADATA: tuple[UnmigratedTable, ...] = tuple(
    entry for entry in DECLARED_BUT_UNMIGRATED if not entry.in_alembic_metadata
)

WITH_READER: tuple[UnmigratedTable, ...] = tuple(entry for entry in DECLARED_BUT_UNMIGRATED if entry.reader)

#: PostgreSQL's undefined_table. Asserted rather than matching on message text,
#: which is localised and has changed between server versions.
UNDEFINED_TABLE_SQLSTATE = "42P01"


class AlembicOnlySchema:
    """A migrated database, plus the two questions this suite asks of it."""

    def __init__(self, url: str, engine: sa.Engine):
        self.url = url
        self.engine = engine
        self._tables: Optional[frozenset[str]] = None

    @property
    def tables(self) -> frozenset[str]:
        if self._tables is None:
            with self.engine.connect() as conn:
                self._tables = frozenset(sa.inspect(conn).get_table_names())
        return self._tables

    def has_table(self, name: str) -> bool:
        return name in self.tables

    def select_every_mapped_column(self, table: sa.Table) -> None:
        """Emit the statement a whole-entity ORM load emits.

        ``select(Model)`` names every mapped column, so this is the shape that
        turns one absent table -- or one absent column -- into a failure of every
        read of that entity, not only the reads that mention the missing thing.
        """
        columns = ", ".join(f'"{column.name}"' for column in table.columns)
        with self.engine.connect() as conn:
            conn.execute(sa.text(f'SELECT {columns} FROM "{table.name}" LIMIT 1'))  # noqa: S608 - names from metadata


def is_postgres(url: str) -> bool:
    return url.startswith("postgresql")


def build(url_of_suite: str) -> AlembicOnlySchema:
    """Create a database beside the suite's own and migrate it.

    Raises rather than skipping on failure: a migration chain that will not apply
    is a finding, and swallowing it here would restore exactly the blind spot this
    module exists to remove.
    """
    name = f"qgp_alembic_only_{uuid.uuid4().hex[:12]}"
    admin = sa.create_engine(_sync(url_of_suite), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    finally:
        admin.dispose()

    scratch_url = sa.engine.make_url(url_of_suite).set(database=name).render_as_string(hide_password=False)

    env = dict(os.environ)
    env["DATABASE_URL"] = scratch_url
    result = subprocess.run(  # noqa: S603 - fixed argv, no shell
        [_alembic_executable(), "upgrade", "head"],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        drop(url_of_suite, name)
        raise RuntimeError(
            "alembic upgrade head failed against a clean database, so this suite "
            "cannot say anything about the migrated schema.\n"
            f"stdout:\n{result.stdout[-4000:]}\nstderr:\n{result.stderr[-4000:]}"
        )

    return AlembicOnlySchema(scratch_url, sa.create_engine(_sync(scratch_url)))


def _alembic_executable() -> str:
    """The ``alembic`` console script.

    Not ``python -m alembic``: the package ships no ``__main__``. And not
    ``python -c "from alembic.config import main"`` either, because that puts the
    working directory first on ``sys.path``, where this repository's own
    ``alembic/`` package shadows the installed library. The console script is what
    CI already invokes.
    """
    beside_interpreter = Path(sys.executable).parent / "alembic"
    if beside_interpreter.is_file():
        return str(beside_interpreter)
    found = shutil.which("alembic")
    if found:
        return found
    raise RuntimeError(
        "the alembic console script was found neither beside the interpreter at "
        f"{beside_interpreter} nor on PATH, so the migrated schema cannot be built."
    )


def drop(url_of_suite: str, name: str) -> None:
    admin = sa.create_engine(_sync(url_of_suite), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}"'))
    finally:
        admin.dispose()


def _sync(url: str) -> str:
    """psycopg2 rather than asyncpg, so the fixture can be session-scoped.

    A session-scoped async fixture would need an event loop outliving the
    function-scoped one pytest-asyncio configures for this repository
    (``asyncio_default_fixture_loop_scope=function`` in pytest.ini), and sharing a
    loop across scopes is a class of flake nobody should have to debug to read a
    schema.
    """
    return url.replace("+asyncpg", "+psycopg2").replace("postgresql://", "postgresql+psycopg2://")
