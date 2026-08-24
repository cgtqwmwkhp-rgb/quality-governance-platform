"""NS-1: band the PEL sequence by cascade level + documents.cascade_level.

Revision ID: 20261027_lib_ns1_banded_pel
Revises: 20261026_lib_wc1_control_holds
Create Date: 2026-08-09

Northern Star v6 fixes the reference grammar at
``^PEL-(HSEQ|IT|FAC|PPL|PROC|FLT|CTR|SVC|TECH|DP|FIN|COM)-[1-5][0-9]{3}$``
(R01), and R02 requires the first digit of the sequence to equal the
document's cascade level. WA-2's allocator issues ``PEL-HSEQ-0001`` — a
leading ``0`` that no band claims — so every reference it produces fails R01
and R02. This revision makes the banded form the only one the system can
issue:

- ``pel_doc_ref_counters`` — re-keyed from ``(function_id)`` to
  ``(function_id, level_band)``, with a CHECK pinning the band to 1..5. One
  function now owns five independent sequences.
- ``documents.cascade_level`` — nullable SMALLINT, CHECK 1..5.
- ``documents_pel_doc_ref_immutable`` — extended so an issued document's
  cascade level cannot drift away from the band printed in its reference
  (R02/R05), including via raw SQL.

Data safety. Nothing is renumbered and nothing is re-issued (R29). References
already allocated under the unbanded WA-2 form (``PEL-HSEQ-0001``) and the
retired Wave W0 form (``PEL-HSE-01-001``) stay verbatim on ``documents``:
they are printed on document faces and cited in client audit packs. They
cannot collide with anything allocated from here on, because a banded
sequence always starts with 1-5 and the unbanded form always starts with 0.

The old per-function counter rows are dropped rather than split across the
five new bands. Splitting them is not possible even in principle: a
function's ``next_seq`` is a single number with no record of which levels
consumed it, so any mapping onto five bands would either skip numbers or
re-issue them. Dropping is safe for the same reason WA-2 could drop the
per-category counters — the counters carry no reference the documents do not
already hold, and the namespace they numbered is closed. Every (function,
band) therefore starts at 1, and the first banded HSEQ procedure is
``PEL-HSEQ-3001``.

``documents.cascade_level`` is left NULL for existing rows rather than
backfilled. A level is a governance judgement about where a document sits in
the cascade; deriving one from a category or a title would be a guess, and
under R02 a guess printed next to an unbanded reference is worse than an
honest blank. Legacy rows are re-levelled when they are re-filed.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261027_lib_ns1_banded_pel"
down_revision: Union[str, Sequence[str], None] = "20261026_lib_wc1_control_holds"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

PEL_IMMUTABLE_TRIGGER = "trg_documents_pel_doc_ref_immutable"
PEL_IMMUTABLE_FUNCTION = "documents_pel_doc_ref_immutable"

CASCADE_LEVEL_CHECK = "ck_documents_cascade_level_range"
COUNTER_BAND_CHECK = "ck_pel_doc_ref_counters_level_band"

# Kept in step with src.domain.models.document_library.CASCADE_LEVELS. Spelled
# out here rather than imported, so a later edit to the model cannot silently
# rewrite what this migration did to a database that already ran it.
CASCADE_BANDS = (1, 2, 3, 4, 5)
_BAND_MIN, _BAND_MAX = CASCADE_BANDS[0], CASCADE_BANDS[-1]
_BAND_CHECK_SQL = f"level_band >= {_BAND_MIN} AND level_band <= {_BAND_MAX}"
_LEVEL_CHECK_SQL = f"cascade_level IS NULL OR (cascade_level >= {_BAND_MIN} AND cascade_level <= {_BAND_MAX})"


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table: str) -> bool:
    return _inspector().has_table(table)


def _columns(table: str) -> set[str]:
    if not _table_exists(table):
        return set()
    return {c["name"] for c in _inspector().get_columns(table)}


def _add_check_constraint(table: str, name: str, condition: str) -> None:
    """Add a named CHECK on either dialect.

    SQLite cannot ALTER in a constraint, so the batch helper rebuilds the
    table; PostgreSQL adds it in place. The PostgreSQL branch drops any
    same-named constraint first so a re-run is idempotent.
    """
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch_op:
            batch_op.create_check_constraint(name, condition)
        return
    op.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}"))
    op.create_check_constraint(name, table, condition)


def _drop_check_constraint(table: str, name: str) -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table(table) as batch_op:
            try:
                batch_op.drop_constraint(name, type_="check")
            except Exception:  # noqa: BLE001 — unnamed/absent CHECK on a create_all schema
                pass
        return
    op.execute(sa.text(f"ALTER TABLE {table} DROP CONSTRAINT IF EXISTS {name}"))


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    # ------------------------------------------------------------------
    # documents.cascade_level
    # ------------------------------------------------------------------
    if "cascade_level" not in _columns("documents"):
        op.add_column("documents", sa.Column("cascade_level", sa.SmallInteger(), nullable=True))
        op.create_index("ix_documents_cascade_level", "documents", ["cascade_level"])
        # Every existing row is NULL at this point, so the constraint validates
        # without a rewrite and there is no need for NOT VALID / VALIDATE.
        _add_check_constraint("documents", CASCADE_LEVEL_CHECK, _LEVEL_CHECK_SQL)

    # ------------------------------------------------------------------
    # pel_doc_ref_counters: re-key (function_id) -> (function_id, level_band)
    # ------------------------------------------------------------------
    counter_columns = _columns("pel_doc_ref_counters")
    if _table_exists("pel_doc_ref_counters") and "level_band" not in counter_columns:
        op.drop_table("pel_doc_ref_counters")
        counter_columns = set()

    if not _table_exists("pel_doc_ref_counters"):
        op.create_table(
            "pel_doc_ref_counters",
            sa.Column("function_id", sa.Integer(), nullable=False),
            sa.Column("level_band", sa.SmallInteger(), nullable=False),
            sa.Column("next_seq", sa.Integer(), nullable=False, server_default="1"),
            sa.ForeignKeyConstraint(["function_id"], ["document_functions.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("function_id", "level_band"),
            sa.CheckConstraint(_BAND_CHECK_SQL, name=COUNTER_BAND_CHECK),
        )

    _seed_counters()

    if is_postgres:
        _install_immutability_trigger()


def _seed_counters() -> None:
    """Create one counter per (function, band), at 1, for every band that has none.

    Never touches an existing counter row: resetting `next_seq` would re-issue
    a reference that is already printed on a document (R06/R29).
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    bands = ", ".join(str(band) for band in CASCADE_BANDS)
    bind.execute(
        sa.text(f"""
            INSERT INTO pel_doc_ref_counters (function_id, level_band, next_seq)
            SELECT f.id, b.band, 1
            FROM document_functions f
            CROSS JOIN (SELECT unnest(ARRAY[{bands}]) AS band) b
            WHERE NOT EXISTS (
                SELECT 1
                FROM pel_doc_ref_counters c
                WHERE c.function_id = f.id AND c.level_band = b.band
            )
            """)
    )


def _install_immutability_trigger() -> None:
    """Re-assert PEL immutability and extend it to the cascade level (R02/R05).

    WA-2 installed this trigger for `pel_doc_ref` and `function_id`. NS-1 adds
    the level: the band digit of an issued reference *is* the cascade level, so
    letting the level move on an issued document would leave `PEL-HSEQ-3001`
    claiming level 3 while the row claims level 4 — and the reference cannot
    follow, because it is immutable. A level change is a reissue (R05).

    Before issue the level is freely editable, which is why the guard keys off
    `OLD.pel_doc_ref` rather than off `OLD.cascade_level` being set.
    """
    op.execute(
        sa.text(f"""
            CREATE OR REPLACE FUNCTION {PEL_IMMUTABLE_FUNCTION}()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.pel_doc_ref IS NOT NULL
                   AND NEW.pel_doc_ref IS DISTINCT FROM OLD.pel_doc_ref THEN
                    RAISE EXCEPTION
                        'documents.pel_doc_ref is immutable once allocated (% -> %); re-file to issue a new reference (ADR-0023)',
                        OLD.pel_doc_ref, NEW.pel_doc_ref
                        USING ERRCODE = 'restrict_violation';
                END IF;
                IF OLD.function_id IS NOT NULL
                   AND NEW.function_id IS DISTINCT FROM OLD.function_id THEN
                    RAISE EXCEPTION
                        'documents.function_id is immutable once set (% -> %); re-file to change the owning function (ADR-0023)',
                        OLD.function_id, NEW.function_id
                        USING ERRCODE = 'restrict_violation';
                END IF;
                IF OLD.pel_doc_ref IS NOT NULL
                   AND OLD.cascade_level IS NOT NULL
                   AND NEW.cascade_level IS DISTINCT FROM OLD.cascade_level THEN
                    RAISE EXCEPTION
                        'documents.cascade_level is fixed once a PEL reference is issued (% -> %); % is banded to that level, so re-file to supersede it (Northern Star R02/R05)',
                        OLD.cascade_level, NEW.cascade_level, OLD.pel_doc_ref
                        USING ERRCODE = 'restrict_violation';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """)
    )
    op.execute(sa.text(f"DROP TRIGGER IF EXISTS {PEL_IMMUTABLE_TRIGGER} ON documents"))
    op.execute(
        sa.text(f"""
            CREATE TRIGGER {PEL_IMMUTABLE_TRIGGER}
            BEFORE UPDATE ON documents
            FOR EACH ROW
            EXECUTE FUNCTION {PEL_IMMUTABLE_FUNCTION}()
            """)
    )


def _restore_wa2_immutability_trigger() -> None:
    """Put the trigger back exactly as WA-2 left it (no cascade_level clause)."""
    op.execute(
        sa.text(f"""
            CREATE OR REPLACE FUNCTION {PEL_IMMUTABLE_FUNCTION}()
            RETURNS trigger AS $$
            BEGIN
                IF OLD.pel_doc_ref IS NOT NULL
                   AND NEW.pel_doc_ref IS DISTINCT FROM OLD.pel_doc_ref THEN
                    RAISE EXCEPTION
                        'documents.pel_doc_ref is immutable once allocated (% -> %); re-file to issue a new reference (ADR-0023)',
                        OLD.pel_doc_ref, NEW.pel_doc_ref
                        USING ERRCODE = 'restrict_violation';
                END IF;
                IF OLD.function_id IS NOT NULL
                   AND NEW.function_id IS DISTINCT FROM OLD.function_id THEN
                    RAISE EXCEPTION
                        'documents.function_id is immutable once set (% -> %); re-file to change the owning function (ADR-0023)',
                        OLD.function_id, NEW.function_id
                        USING ERRCODE = 'restrict_violation';
                END IF;
                RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """)
    )
    op.execute(sa.text(f"DROP TRIGGER IF EXISTS {PEL_IMMUTABLE_TRIGGER} ON documents"))
    op.execute(
        sa.text(f"""
            CREATE TRIGGER {PEL_IMMUTABLE_TRIGGER}
            BEFORE UPDATE ON documents
            FOR EACH ROW
            EXECUTE FUNCTION {PEL_IMMUTABLE_FUNCTION}()
            """)
    )


def downgrade() -> None:
    """Return to the WA-2 unbanded counter shape.

    Sequences are NOT restored: the pre-NS-1 per-function numbers are gone, and
    inventing them would let the unbanded scheme re-issue a reference a
    document already carries. `documents.pel_doc_ref` is left untouched on the
    way down for the same reason it is left untouched on the way up — banded
    references already issued stay exactly as they are, and remain resolvable.
    """
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        _restore_wa2_immutability_trigger()

    if _table_exists("pel_doc_ref_counters"):
        op.drop_table("pel_doc_ref_counters")
    op.create_table(
        "pel_doc_ref_counters",
        sa.Column("function_id", sa.Integer(), nullable=False),
        sa.Column("next_seq", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["function_id"], ["document_functions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("function_id"),
    )
    if is_postgres:
        bind.execute(
            sa.text("""
                INSERT INTO pel_doc_ref_counters (function_id, next_seq)
                SELECT f.id, 1
                FROM document_functions f
                WHERE NOT EXISTS (
                    SELECT 1 FROM pel_doc_ref_counters c WHERE c.function_id = f.id
                )
                """)
        )

    if "cascade_level" in _columns("documents"):
        _drop_check_constraint("documents", CASCADE_LEVEL_CHECK)
        op.drop_index("ix_documents_cascade_level", table_name="documents")
        op.drop_column("documents", "cascade_level")
