"""A scratch database built by the alembic chain, so drift is observable.

Not a test module (the leading underscore keeps pytest from collecting it).

Why the shared harness cannot host these assertions
---------------------------------------------------
``tests/integration/conftest.py`` has an autouse fixture that runs
``Base.metadata.create_all`` before every integration test, and CI applies the
alembic chain to the same database first. ``create_all`` issues ``CREATE TABLE
IF NOT EXISTS`` per table, so it adds nothing to a table the migrations already
built — but any table the migrations did *not* build arrives complete, and any
declared table the migrations built with fewer columns keeps the migrated shape.
The net effect is a schema that is a union of the two, and a missing-column
condition is masked for exactly the tables where ``create_all`` won: the check
would pass whether or not the defect were fixed.

So these suites build their own database, apply only the migrations, and read
``information_schema``. That is the schema a deploy actually produces.

Alembic runs as the console script in a subprocess
--------------------------------------------------
``alembic/env.py`` reads the URL from ``src.core.config.settings``, which is a
module-level singleton already constructed by the time any test imports it, and
it runs migrations as an import side effect. Both make in-process invocation a
matter of patching around the design rather than using it. A subprocess with
``DATABASE_URL`` in its environment is what CI does, so it is also what is
actually covered.

It has to be the ``alembic`` console script and not ``python -m alembic``: this
repository has a directory named ``alembic`` at its root, which shadows the
installed package for any interpreter started with the repo root on
``sys.path``. The console script starts with its own ``bin`` directory there
instead, and ``prepend_sys_path = .`` in ``alembic.ini`` puts the repo root on
the path afterwards, which is how ``env.py`` finds ``src`` without the collision.

PostgreSQL only. The foreign-key half of this census reads ``pg_constraint``,
and the column half needs the schema a Postgres deploy produces; SQLite has
neither, so the fixture skips rather than asserting something weaker.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import uuid
from pathlib import Path
from typing import Any

import sqlalchemy as sa

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Attribution columns ``AuditTrailMixin`` declares.
ATTRIBUTION_COLUMNS: tuple[str, ...] = ("created_by_id", "updated_by_id")


def postgres_base_url() -> str | None:
    """The suite's DSN when it is PostgreSQL, else ``None``."""
    url = os.environ.get("DATABASE_URL", "")
    return url if url.startswith("postgresql") else None


def _sync_url(url: str) -> str:
    return sa.engine.make_url(url).set(drivername="postgresql+psycopg2").render_as_string(hide_password=False)


class MigratedSchema:
    """A database this test owns, carrying only what the migrations created."""

    def __init__(self, url: str, name: str):
        self.url = url
        self.name = name
        self.engine = sa.create_engine(_sync_url(url))

    def columns(self, table: str) -> set[str]:
        with self.engine.connect() as conn:
            return {
                row[0]
                for row in conn.execute(
                    sa.text(
                        "SELECT column_name FROM information_schema.columns "
                        "WHERE table_schema = current_schema() AND table_name = :table"
                    ),
                    {"table": table},
                )
            }

    def tables(self) -> set[str]:
        with self.engine.connect() as conn:
            return {
                row[0]
                for row in conn.execute(
                    sa.text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE'"
                    )
                )
            }

    def foreign_key_targets(self, table: str, column: str) -> set[str]:
        """Tables that ``table.column`` is constrained to reference."""
        with self.engine.connect() as conn:
            return {
                row[0]
                for row in conn.execute(
                    sa.text("""
                        SELECT tgt.relname
                        FROM pg_constraint AS con
                        JOIN pg_class AS src ON src.oid = con.conrelid
                        JOIN pg_class AS tgt ON tgt.oid = con.confrelid
                        JOIN pg_namespace AS ns ON ns.oid = src.relnamespace
                        JOIN unnest(con.conkey) WITH ORDINALITY AS ck(attnum, ord) ON TRUE
                        JOIN pg_attribute AS att
                          ON att.attrelid = con.conrelid AND att.attnum = ck.attnum
                        WHERE con.contype = 'f'
                          AND ns.nspname = current_schema()
                          AND src.relname = :table
                          AND att.attname = :column
                        """),
                    {"table": table, "column": column},
                )
            }

    def execute(self, statement: str, parameters: dict[str, Any] | None = None) -> Any:
        with self.engine.begin() as conn:
            return conn.execute(sa.text(statement), parameters or {})

    def dispose(self) -> None:
        self.engine.dispose()


def alembic_executable() -> str | None:
    """The ``alembic`` console script, or ``None`` if it is not on PATH."""
    return shutil.which("alembic")


def create_migrated_database(base_url: str) -> MigratedSchema:
    """Create a scratch database and bring it to head with the alembic chain."""
    alembic = alembic_executable()
    if alembic is None:
        raise RuntimeError("the alembic console script is not on PATH")

    name = f"qgp_run026_schema_{uuid.uuid4().hex[:12]}"
    admin = sa.create_engine(_sync_url(base_url), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(f'CREATE DATABASE "{name}"'))
    finally:
        admin.dispose()

    url = sa.engine.make_url(base_url).set(database=name).render_as_string(hide_password=False)

    environment = {**os.environ, "DATABASE_URL": url}
    # The scratch database is not the one the DSN guard was pointed at, and it is
    # created on the same host, so the guard's own decision still holds.
    environment.pop("ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT", None)
    environment.pop("ALEMBIC_DRIFT_INVENTORY_FILE", None)

    result = subprocess.run(
        [alembic, "upgrade", "head"],
        cwd=REPO_ROOT,
        env=environment,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        drop_database(base_url, name)
        raise RuntimeError(
            "alembic upgrade head failed on the scratch database, so this suite cannot "
            f"observe the migrated schema.\nstdout:\n{result.stdout[-4000:]}\nstderr:\n{result.stderr[-4000:]}"
        )
    return MigratedSchema(url, name)


def drop_database(base_url: str, name: str) -> None:
    admin = sa.create_engine(_sync_url(base_url), isolation_level="AUTOCOMMIT")
    try:
        with admin.connect() as conn:
            conn.execute(sa.text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
    finally:
        admin.dispose()
