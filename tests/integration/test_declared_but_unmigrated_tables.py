"""Every test database has tables no deployment has, and the gates cannot see it.

The mechanism
-------------
Production's schema is built by Alembic. Both CI test databases are built from the
SQLAlchemy models: ``tests/integration/conftest.py`` runs ``Base.metadata.create_all``
as an autouse fixture, and ``src.main`` calls ``init_db`` -- and so ``create_all`` --
whenever ``settings.is_development``, which ``.github/workflows/locust-soft-gate.yml``
sets. A table a model declares that no migration creates is therefore present in
every test database and absent from every deployment.

Nothing about that makes a test fail. It makes tests **pass while saying nothing**.
A reachability test over an unmigrated table is green whether or not the migration
exists, so it cannot distinguish a working endpoint from one that answers 500 the
moment it is deployed. That is how endpoints over seven document-control tables
shipped with every gate green.

What this module adds that the existing suite does not have
----------------------------------------------------------
The reachability and disclosure suites are not weakened here and nothing in them is
marked xfail -- they pass, correctly, and an xfail would redden a legitimately
passing test. What they lack is a statement about the *migrated* schema. So this
module keeps their assertions as strict as they are and adds three of its own per
table:

(a) the reader endpoint still returns 200 against the ``create_all`` harness --
    the green that means nothing, pinned so that its meaninglessness is on the
    record next to the reason;
(b) against a database built by ``alembic upgrade head`` and nothing else, reading
    the table fails with PostgreSQL's ``undefined_table`` naming that table;
(c) the table is in ``Base.metadata`` and absent from the Alembic-built schema.

Two of the sixteen were found by this module rather than pinned by it
-------------------------------------------------------------------
``push_subscriptions`` and ``notification_logs`` are declared inside
``src/api/routes/push_notifications.py``. ``alembic/env.py`` builds its comparison
metadata from ``src/domain/models`` plus a fixed module list, so neither table is
in it: they are absent from the migrated schema, absent from the exclusion
register, and absent from every drift report ever published. The router is mounted
at ``/api/v1/notifications/push`` and ``POST /subscribe`` writes
``push_subscriptions``, so unlike the dormant IMS models this pair is reachable.
Recorded here, not fixed here -- the migration and the endpoint's behaviour on an
absent table are a separate change with a separate owner.

READ THIS BEFORE "FIXING" A FAILURE HERE
----------------------------------------
**Assertion (b) is designed to start failing.** When a create migration lands for
one of these tables, the table will exist in the Alembic-built schema, the
undefined-table error will not be raised, and that entry's (b) and (c) will fail.
That is the success condition, not a broken test. The fix is to delete the entry
from ``DECLARED_BUT_UNMIGRATED`` in ``tests/integration/_alembic_only_schema.py``
in the same PR as the migration. Do not relax the assertion, do not add an xfail,
and do not skip the case: the whole value of this module is that it cannot pass
while quietly tolerating either state.

A failure of (b) with no migration in the PR means something else supplied the
table, which is the original defect returning.
"""

from __future__ import annotations

import pytest
import sqlalchemy as sa
from httpx import AsyncClient

from tests.integration._alembic_only_schema import (
    DECLARED_BUT_UNMIGRATED,
    OUTSIDE_ALEMBIC_METADATA,
    UNDEFINED_TABLE_SQLSTATE,
    WITH_READER,
    AlembicOnlySchema,
    UnmigratedTable,
)


def _metadata() -> sa.MetaData:
    """The metadata the running application carries.

    This is the correct left-hand side for this module: it is the object
    ``tests/integration/conftest.py`` hands to ``create_all``, and the one the
    endpoints read through. ``src.main`` is already imported by the time any test
    runs, so every model the app registers is present.

    Deliberately *not* ``scripts/ops/run025/_models.load_metadata()``, which
    reproduces ``alembic/env.py``'s import list. Two reasons, and the first is
    fatal: importing that set into a live app process registers a second class named
    ``Role`` and SQLAlchemy then refuses to configure any mapper for the rest of the
    session ("Multiple classes found for path Role"). The second is that env.py's
    view is the wrong question here -- it declares 248 tables where the app declares
    230, and the tables it does not know about are exactly the ones no gate has ever
    reported.
    """
    from src.infrastructure.database import Base

    return Base.metadata


def _ids(entries) -> list[str]:
    return [entry.table for entry in entries]


# ---------------------------------------------------------------------------
# The harness must be able to observe the condition
# ---------------------------------------------------------------------------


class TestTheTwoSchemasReallyDiffer:
    """Without these, everything below could pass vacuously."""

    def test_the_alembic_database_was_actually_built(self, alembic_only_schema: AlembicOnlySchema):
        """A chain that silently applied nothing would make every absence assertion
        below trivially true."""
        assert alembic_only_schema.has_table("alembic_version")
        assert len(alembic_only_schema.tables) > 200, (
            f"only {len(alembic_only_schema.tables)} tables were built; the migration " "chain did not run to head"
        )

    async def test_the_shared_harness_has_tables_the_migrations_do_not_create(
        self, alembic_only_schema: AlembicOnlySchema, test_session
    ):
        """The defect itself, stated once as a fact about the two databases.

        This is what makes a green reachability test uninformative: the table the
        endpoint needs is supplied by ``create_all``, not by the migration chain,
        so the test exercises a schema no deployment has.

        Read through the suite's own session rather than a fresh engine, so it is
        the database the endpoint tests use that is being described.
        """
        connection = await test_session.connection()
        harness_tables = await connection.run_sync(lambda sync_conn: set(sa.inspect(sync_conn).get_table_names()))

        supplied_by_create_all = sorted(
            entry.table
            for entry in DECLARED_BUT_UNMIGRATED
            if entry.table in harness_tables and not alembic_only_schema.has_table(entry.table)
        )

        assert supplied_by_create_all == sorted(entry.table for entry in DECLARED_BUT_UNMIGRATED), (
            "the shared integration database no longer supplies every declared-but-"
            "unmigrated table. If a migration landed, delete that entry from "
            "DECLARED_BUT_UNMIGRATED; if create_all stopped running, this module's "
            f"premise changed. Supplied: {supplied_by_create_all}"
        )


# ---------------------------------------------------------------------------
# (c) the drift is real
# ---------------------------------------------------------------------------


class TestTheTableIsDeclaredAndNotBuilt:
    @pytest.mark.parametrize("entry", DECLARED_BUT_UNMIGRATED, ids=_ids(DECLARED_BUT_UNMIGRATED))
    def test_the_model_declares_it(self, entry: UnmigratedTable):
        metadata = _metadata()

        assert entry.table in metadata.tables, (
            f"{entry.table!r} is no longer declared by any model. If the model was " "deleted, delete this entry too."
        )

    @pytest.mark.parametrize("entry", DECLARED_BUT_UNMIGRATED, ids=_ids(DECLARED_BUT_UNMIGRATED))
    def test_the_migrations_do_not_build_it(self, entry: UnmigratedTable, alembic_only_schema: AlembicOnlySchema):
        """Fails when the migration lands. That is the point -- see the module docstring."""
        assert not alembic_only_schema.has_table(entry.table), (
            f"{entry.table!r} now exists in the Alembic-built schema. If a migration "
            f"landed, delete this entry from DECLARED_BUT_UNMIGRATED (declared in "
            f"{entry.declared_in}) in the same PR. Do not weaken this assertion."
        )


# ---------------------------------------------------------------------------
# (b) the absence is load-bearing
# ---------------------------------------------------------------------------


class TestReadingTheTableFailsOnTheMigratedSchema:
    """The assertion that makes this module worth its runtime.

    Every other check here compares two lists of names. This one executes the
    statement the ORM executes and shows the database refusing it, so what is
    pinned is the deployment's behaviour rather than a belief about it.
    """

    @pytest.mark.parametrize("entry", DECLARED_BUT_UNMIGRATED, ids=_ids(DECLARED_BUT_UNMIGRATED))
    def test_a_whole_entity_read_raises_undefined_table(
        self, entry: UnmigratedTable, alembic_only_schema: AlembicOnlySchema
    ):
        table = _metadata().tables[entry.table]

        with pytest.raises(sa.exc.ProgrammingError) as raised:
            alembic_only_schema.select_every_mapped_column(table)

        pgcode = getattr(raised.value.orig, "pgcode", None)
        assert pgcode == UNDEFINED_TABLE_SQLSTATE, (
            f"reading {entry.table!r} failed with SQLSTATE {pgcode!r}, not "
            f"undefined_table ({UNDEFINED_TABLE_SQLSTATE}). A different error means "
            "this test is no longer measuring what it claims to."
        )
        assert entry.table in str(raised.value), (
            "the error does not name the table, so a deployment log would not say "
            f"which table is missing: {raised.value}"
        )


# ---------------------------------------------------------------------------
# (a) the green that means nothing
# ---------------------------------------------------------------------------


class TestTheEndpointIsGreenOnTheHarnessAnyway:
    """Pinned deliberately, and deliberately not turned red.

    These endpoints are not broken -- they answer 200 here because the harness
    gives them a table, and they answer honestly on a database without it because
    the absent-table disclosure work made them check first. Both facts are true at
    once, and recording the 200 next to the ``undefined_table`` above is the only
    way the pair is legible to the next reader.
    """

    @pytest.mark.parametrize("entry", WITH_READER, ids=_ids(WITH_READER))
    async def test_the_reader_returns_200_on_the_create_all_harness(
        self, entry: UnmigratedTable, admin_client: AsyncClient
    ):
        response = await admin_client.get(entry.reader)

        assert response.status_code == 200, (
            f"{entry.reader} does not return 200 on the shared harness, so it cannot "
            f"be used to demonstrate that a green result over {entry.table!r} is "
            f"uninformative. Got {response.status_code}: {response.text}"
        )


# ---------------------------------------------------------------------------
# The shape of the backlog, so it cannot be misreported again
# ---------------------------------------------------------------------------


class TestTheBacklogIsNotOverstated:
    """An earlier report read 23 absent tables off a static pass. It was wrong.

    The measured figure is 16, against the metadata the app actually carries.
    Until C-70 it read 23 if you swept the models package with ``pkgutil``, because
    that imported ``audit_template.py`` and registered seven more tables on the
    same ``Base``: no migration created them, nothing under ``src/`` imported the
    module, and the database held equivalents under different names
    (``audit_templates`` vs ``audit_builder_templates``, ``audit_sections`` vs
    ``audit_template_sections``). That was a naming divergence behind dead code,
    not a migration gap, and the module has since been deleted — so the two import
    strategies now agree on 16.
    """

    def test_the_measured_count_is_the_declared_count(self, alembic_only_schema: AlembicOnlySchema):
        """No declared table is absent beyond the ones on record.

        The direction that matters: an unlisted absence is a table nobody knows is
        missing, which is the condition this whole module exists to end.
        """
        metadata = _metadata()
        absent = {name for name in metadata.tables if not alembic_only_schema.has_table(name)}
        recorded = {entry.table for entry in DECLARED_BUT_UNMIGRATED}

        assert absent == recorded, (
            f"unrecorded absent table(s): {sorted(absent - recorded)}; "
            f"recorded but now present: {sorted(recorded - absent)}. "
            "Update DECLARED_BUT_UNMIGRATED in the same PR as the schema change."
        )

    def test_audit_template_models_are_not_counted_as_a_migration_gap(self):
        """They were unreachable, not un-migrated, and are now absent entirely.

        Settled by measurement before the model was deleted for C-70: nothing under
        ``src/`` imported ``src.domain.models.audit_template``, so its seven
        classes were never registered on ``Base.metadata`` by the import path
        Alembic or the app uses, and ``create_all`` did not create them either. No
        migration creates any of the seven, and a database built by ``alembic
        upgrade head`` does not carry them
        (``docs/evidence/run026-local-alembic-head-absent-tables-20260728.json``).

        The assertion is kept as-is now the module is gone. It is cheap, and the
        thing it forbids — these seven names arriving in the metadata without
        migrations — is exactly what would happen if the deleted model were
        restored or rewritten, which is the mistake this entry exists to catch.
        """
        metadata = _metadata()
        builder_tables = {
            "audit_builder_templates",
            "audit_builder_runs",
            "audit_builder_responses",
            "audit_builder_findings",
            "audit_template_sections",
            "audit_template_questions",
            "audit_template_versions",
        }

        assert builder_tables.isdisjoint(set(metadata.tables)), (
            "audit_template.py is now on the metadata Alembic compares against, so "
            "its seven tables will start reporting as absent. Either give them "
            "migrations or keep them out of the comparison -- do not add them to "
            f"DECLARED_BUT_UNMIGRATED as a create backlog: {sorted(builder_tables & set(metadata.tables))}"
        )

    def test_no_create_table_op_does_not_mean_no_absent_tables(self, alembic_only_schema: AlembicOnlySchema):
        """The inference that produced the wrong number, closed off.

        The published drift inventory contains zero ``CreateTableOp``, which reads
        as "no table is missing". It is not: 14 of these 16 are removed from the
        comparison by ``include_object``, and the other two are declared in a module
        ``alembic/env.py`` never imports. Both make ``CreateTableOp`` zero without
        making a single table exist.
        """
        from scripts.ops.run025._models import alembic_check_excluded_tables

        excluded = set(alembic_check_excluded_tables())
        recorded = {entry.table for entry in DECLARED_BUT_UNMIGRATED}
        invisible = {entry.table for entry in OUTSIDE_ALEMBIC_METADATA}

        unaccounted = recorded - excluded - invisible

        assert unaccounted == set(), (
            f"{sorted(unaccounted)} is absent from the migrated schema, is not on the "
            "exclusion register, and is visible to alembic check -- so alembic check "
            "should be emitting CreateTableOp for it and the gate should be red. "
            "Either it is red, or the accounting here is wrong; find out which."
        )


class TestSomeTablesAreOutsideTheDriftGateEntirely:
    """The worst case is not a deferred table, it is an invisible one.

    ``alembic/env.py`` builds its comparison metadata from ``src/domain/models``
    plus a hard-coded list of modules. ``push_subscriptions`` and
    ``notification_logs`` are declared in ``src/api/routes/push_notifications.py``,
    so they are in neither. They are absent from the migrated schema, absent from
    the exclusion register, and absent from every drift report -- and the router
    that writes them is mounted.
    """

    @pytest.mark.parametrize("entry", OUTSIDE_ALEMBIC_METADATA, ids=_ids(OUTSIDE_ALEMBIC_METADATA))
    def test_the_table_is_not_on_the_exclusion_register(self, entry: UnmigratedTable):
        """So its absence was never a recorded decision with an owner."""
        from scripts.ops.run025._models import alembic_check_excluded_tables

        assert entry.table not in set(alembic_check_excluded_tables()), (
            f"{entry.table!r} is now on the exclusion register, which means its "
            "absence has become a recorded deferral. Move this entry accordingly."
        )

    @pytest.mark.parametrize("entry", OUTSIDE_ALEMBIC_METADATA, ids=_ids(OUTSIDE_ALEMBIC_METADATA))
    def test_the_declaring_module_is_not_on_alembic_s_import_list(self, entry: UnmigratedTable):
        """The mechanism, pinned so that fixing it is detected.

        If someone adds this module to ``env.py``, ``alembic check`` starts emitting
        ``CreateTableOp`` for the table and the gate goes red -- which is the correct
        outcome and must not be a surprise. This test failing is the signal that the
        table has become visible; delete the entry then.
        """
        from scripts.ops.run025._models import side_effect_model_modules

        module = entry.declared_in.removesuffix(".py").replace("/", ".")

        assert module not in side_effect_model_modules(), (
            f"{module} is now imported by alembic/env.py, so {entry.table!r} is "
            "inside the comparison. Expect CreateTableOp and handle it deliberately."
        )
        assert not module.startswith("src.domain.models"), (
            f"{entry.table!r} is declared under src.domain.models, which env.py "
            "imports wholesale, so it cannot be invisible to the gate."
        )
