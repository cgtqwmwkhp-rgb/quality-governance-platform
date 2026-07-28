"""``AuditTrailMixin`` must declare attribution as a reference, not a bare integer.

The mixin is the root cause of the unenforced-attribution drift. It declared
``created_by_id`` and ``updated_by_id`` as plain integers with no ``ForeignKey``,
and the cost of that was 30 tables reaching production where ``created_by_id``
could name a user that had never existed. Nothing reported it: the ORM had
nothing to enforce, the database had no constraint, and ``alembic check`` strips
``CreateForeignKeyOp`` under ``ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1``.

Fixing this only in migrations would leave the models declaring a plain integer
while the database enforced a reference — real drift, kept silent by that same
filter. These are the model half of the fix.

The declarations are read through ``tests._run026_model_probe``, which does the
importing in a subprocess. Doing it in-process poisons ``Base.registry`` for the
whole pytest session; see that module for the two pre-existing model defects that
make it so.
"""

from __future__ import annotations

import pytest

from tests._run026_model_probe import ATTRIBUTION_COLUMNS, probe

EXPECTED_TARGET = "users.id"


@pytest.fixture(scope="module")
def declared():
    """The declared schema, collected once for the module."""
    return probe()


def test_the_mixin_declares_both_attribution_columns(declared):
    """Guard the premise: if the mixin stops declaring these, the rest is vacuous."""
    assert sorted(declared["mixin_declares"]) == sorted(ATTRIBUTION_COLUMNS), (
        "AuditTrailMixin no longer declares both attribution columns. The suites that assert "
        "the database constrains them are calibrated to the mixin declaring them, so update "
        f"them together. Declared: {declared['mixin_declares']}"
    )


def test_every_mixin_table_declares_a_foreign_key_to_users(declared):
    """Attribution columns must be declared as references to ``users.id``.

    Enumerated over every table that inherits the mixin rather than over the
    mixin alone, because a consuming model may override either column, and an
    override that drops the reference is the same defect by another route.
    """
    unconstrained: list[str] = []
    for table_name in declared["mixin_tables"]:
        table = declared["tables"].get(table_name)
        if table is None:
            unconstrained.append(f"{table_name} (mapped but absent from metadata)")
            continue
        for column_name in ATTRIBUTION_COLUMNS:
            references = table["attribution_references"].get(column_name)
            if references is None:
                unconstrained.append(f"{table_name}.{column_name} (not mapped)")
            elif EXPECTED_TARGET not in references:
                unconstrained.append(f"{table_name}.{column_name} -> {references or 'nothing'}")

    assert unconstrained == [], (
        "these attribution columns are declared as plain integers, so nothing stops them "
        f"naming a user that does not exist: {unconstrained}"
    )


def test_every_declared_attribution_column_references_users(declared):
    """Also true of tables that declare the columns without the mixin.

    ``compliance_evidence_links`` declares ``created_by_id`` directly on its
    model and is one of the 30 tables the Run026 migration constrains, so a
    sweep restricted to mixin subclasses would leave the model and the database
    disagreeing about it.
    """
    unconstrained: list[str] = []
    for table_name, table in sorted(declared["tables"].items()):
        for column_name, references in sorted(table["attribution_references"].items()):
            if EXPECTED_TARGET not in references:
                unconstrained.append(f"{table_name}.{column_name} -> {references or 'nothing'}")

    assert unconstrained == [], (
        "every created_by_id / updated_by_id must be declared as a reference to users.id, "
        f"however the model came by the column: {unconstrained}"
    )


def test_mixin_attribution_columns_stay_nullable(declared):
    """The reference must not become mandatory as a side effect of constraining it.

    Rows predating id-based attribution carry no ``created_by_id``, and the eight
    tables that gained the column in ``20260902_attrib_cols`` gained it empty on
    every existing row. ``NOT NULL`` on a mixin column would make that migration
    unrunnable on any database with history, which is the trap the WCS-TEN2
    ``tenant_id`` wave fell into.

    Scoped to tables that take the column *from the mixin*. Six models —
    ``capa_actions``, ``competence_gap_actions``,
    ``document_discussion_threads``, ``document_quiz_drafts``, ``risk_notes``,
    ``signature_templates`` — declare their own ``created_by_id`` ``NOT NULL``
    with an explicit reference, because a note or a signature with no author is
    not a record worth keeping. That is a deliberate per-model decision, their
    columns already exist, and nothing in Run026 alters their nullability.
    """
    mandatory: list[str] = []
    for table_name in declared["mixin_tables"]:
        table = declared["tables"].get(table_name)
        if table is None:
            continue
        for column_name in table["attribution_references"]:
            if not table["nullable"].get(column_name, True):
                mandatory.append(f"{table_name}.{column_name}")

    assert mandatory == [], (
        "mixin attribution columns must stay nullable: rows predating id-based attribution "
        f"have no user to name, and a NOT NULL migration over them cannot run: {mandatory}"
    )
