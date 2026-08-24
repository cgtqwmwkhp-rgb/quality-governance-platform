"""Converge ``soa_control_entries`` with ``SoAControlEntry`` (C-24, #1526).

Revision ID: 20260908_soa_align
Revises: 20260907_ims_unification
Create Date: 2026-09-08

What was wrong
--------------
``soa_control_entries`` is the one table on this repository where a model
declares columns the migrated database does not have. Measured on a database
built by ``alembic upgrade head`` at ``20260907_ims_unification``, autogenerate
produces fifteen operations for it, none of which any gate reports because the
name is in ``_ALEMBIC_CHECK_EXCLUDED_TABLES`` and ``include_object`` drops the
table from the comparison before a single column is looked at:

    AddColumnOp        tenant_id, justification, implementation_method,
                       risk_treatment_reference
    DropColumnOp       inclusion_justification, exclusion_justification,
                       implementation_description, responsible_party,
                       target_completion_date, updated_at
    AlterColumnOp      implementation_status VARCHAR(30) -> VARCHAR(50)
    CreateIndexOp      ix_soa_control_entries_tenant_id
    CreateForeignKeyOp tenant_id -> tenants.id, control_id -> iso27001_controls.id
    DropConstraintOp   soa_control_entry_control_id_fkey

The four ``AddColumnOp`` are the query-breaking half. SQLAlchemy emits every
mapped column for a whole-entity load, so ``select(SoAControlEntry)`` raises
``UndefinedColumn`` today; the table is unreadable through the ORM, not merely
differently shaped. It has survived because nothing reads it -- the import in
``src/api/routes/iso27001.py`` is dead.

The physical table is a rename of the legacy singular ``soa_control_entry``
(``20260120_add_iso27001_isms`` created it, ``iso27001_table_fix_01`` renamed
it), and its sequence, primary key and foreign keys still carry the singular
name. Run026 deferred the repair to the IMS owner rather than guess, because
the two sides are not "the same design with columns missing" -- see
``docs/governance/attribution_schema_drift.md``.

The decision, and why it is not a guess
---------------------------------------
The database is authoritative for the live compliance columns, so nothing is
dropped and nothing is renamed. This migration adds the four columns the model
declares; the model absorbs the six the database has. Both designs survive
side by side.

That deliberately leaves ``justification`` empty next to the existing
``inclusion_justification`` / ``exclusion_justification``, and
``implementation_method`` empty next to ``implementation_description``. It is
the same principle ``20260902_attrib_cols`` applied to ``created_by_id``: the
question the owner could not answer was *which* of the two justifications the
model's single column means, and copying either one into it would file an
exclusion rationale as an inclusion rationale, or the reverse, on real
certification evidence. A migration does not invent compliance evidence
(#1398). Deciding the mapping is a data exercise for the IMS owner and is not
in scope here; what is fixed here is that the table can be read at all.

``implementation_status`` is widened rather than the model narrowed. Widening
a ``varchar`` in PostgreSQL is a catalogue-only change -- no rewrite, no
rejected value, no truncation -- whereas narrowing the model to ``String(30)``
would start rejecting a 31-character status the database would have accepted.
The two agreeing matters; which one moves is decided by which direction cannot
lose data.

``control_id``'s foreign key is left exactly as the database has it
(``ON DELETE CASCADE``) and the model is changed to declare that, for the same
reason: the cascade is live behaviour on a real constraint, and dropping and
recreating a foreign key to make the metadata prettier is a worse trade than
writing down what is already true.

Reversibility
-------------
``downgrade`` drops the four columns and the index this migration created, and
narrows ``implementation_status`` back. The four columns are created empty, so
dropping them is lossless at the point a downgrade is plausible; if rows have
been written since, those values are discarded, which is the same trade every
other downgrade in this chain makes. The narrowing is the one step that can
refuse: it raises rather than truncate a status longer than 30 characters,
because silently shortening a compliance state is worse than a failed
downgrade.

Not in scope: row-level security. ``tenant_id`` arrives nullable, as the model
declares it, so the table does not meet the TEN2 precondition the RLS expand
waves used, and a table under FORCE RLS needs a dedicated migration plus an
entry in ``RLS_TABLES``. Nor is ``tenant_id`` backfilled -- there is no parent
row to derive it from that is not itself untenanted.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260908_soa_align"
down_revision: Union[str, Sequence[str], None] = "20260907_ims_unification"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

TABLE = "soa_control_entries"
TENANT_INDEX = f"ix_{TABLE}_tenant_id"

#: Columns ``SoAControlEntry`` declares that the migrated table does not have,
#: in the shape the model declares them. Read off the model, then verified
#: against ``information_schema`` on a database at ``20260907_ims_unification``.
ADDED_COLUMNS: tuple[tuple[str, sa.types.TypeEngine], ...] = (
    ("tenant_id", sa.Integer()),
    ("justification", sa.Text()),
    ("implementation_method", sa.Text()),
    ("risk_treatment_reference", sa.String(length=100)),
)

STATUS_COLUMN = "implementation_status"
STATUS_LENGTH_BEFORE = 30
STATUS_LENGTH_AFTER = 50


class StatusValuesTooLongError(RuntimeError):
    """A downgrade would have to truncate a status to narrow the column."""


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _columns() -> dict[str, dict]:
    return {column["name"]: column for column in _inspector().get_columns(TABLE)}


def _has_index(name: str) -> bool:
    return any(index["name"] == name for index in _inspector().get_indexes(TABLE))


def _status_length() -> int | None:
    column = _columns().get(STATUS_COLUMN)
    return getattr(column["type"], "length", None) if column else None


def _column_for(name: str, type_: sa.types.TypeEngine) -> sa.Column:
    if name == "tenant_id":
        # Attached in the ADD COLUMN itself, which needs no orphan scan for the
        # one reason that does not generalise: the column is new, so every value
        # in it is NULL, and NULL satisfies a foreign key.
        return sa.Column(
            name,
            type_,
            sa.ForeignKey("tenants.id", name=f"fk_{TABLE}_tenant_id"),
            nullable=True,
        )
    return sa.Column(name, type_, nullable=True)


def upgrade() -> None:
    if not _inspector().has_table(TABLE):
        # A database without the table is not this migration's business; the
        # coverage gap that represents is tracked in
        # docs/governance/alembic_check_excluded_tables.md.
        logger.info("%s: no %r table, nothing to align.", revision, TABLE)
        return

    present = _columns()
    added: list[str] = []
    adopted: list[str] = []
    for name, type_ in ADDED_COLUMNS:
        if name in present:
            # Adopted, not reconciled: the shape and any constraint on a column
            # that is already there are not verified, the same trade
            # 20260906_doc_ctl_children and 20260907_ims_unification made. It is
            # logged rather than passed over in silence so the one environment
            # where it happens is identifiable -- and, unlike those two, this
            # table is compared by `alembic check` from this revision onward, so
            # a mis-shaped adoption is reported from the next run.
            adopted.append(name)
            continue
        op.add_column(TABLE, _column_for(name, type_))
        added.append(name)

    if not _has_index(TENANT_INDEX):
        op.create_index(TENANT_INDEX, TABLE, ["tenant_id"])

    if _status_length() == STATUS_LENGTH_BEFORE:
        op.alter_column(
            TABLE,
            STATUS_COLUMN,
            existing_type=sa.String(length=STATUS_LENGTH_BEFORE),
            type_=sa.String(length=STATUS_LENGTH_AFTER),
            existing_nullable=False,
        )

    logger.info(
        "%s: added %d column(s) [%s] to %s; adopted %d existing unverified [%s]; %s is varchar(%s).",
        revision,
        len(added),
        ", ".join(added) or "none",
        TABLE,
        len(adopted),
        ", ".join(adopted) or "none",
        STATUS_COLUMN,
        _status_length(),
    )


def downgrade() -> None:
    if not _inspector().has_table(TABLE):
        return

    if _status_length() == STATUS_LENGTH_AFTER:
        too_long = (
            op.get_bind()
            .execute(
                sa.text(
                    f'SELECT count(*) FROM "{TABLE}" '  # noqa: S608 - identifiers are module constants
                    f'WHERE length("{STATUS_COLUMN}") > :limit'
                ),
                {"limit": STATUS_LENGTH_BEFORE},
            )
            .scalar()
        )
        if too_long:
            raise StatusValuesTooLongError(
                f"{too_long} row(s) in {TABLE} hold an {STATUS_COLUMN} longer than "
                f"{STATUS_LENGTH_BEFORE} characters, so narrowing the column back would "
                "truncate a compliance state. Shorten or remove those values first; this "
                "downgrade will not discard them silently."
            )
        op.alter_column(
            TABLE,
            STATUS_COLUMN,
            existing_type=sa.String(length=STATUS_LENGTH_AFTER),
            type_=sa.String(length=STATUS_LENGTH_BEFORE),
            existing_nullable=False,
        )

    if _has_index(TENANT_INDEX):
        op.drop_index(TENANT_INDEX, table_name=TABLE)

    present = _columns()
    for name, _type in reversed(ADDED_COLUMNS):
        if name in present:
            op.drop_column(TABLE, name)
