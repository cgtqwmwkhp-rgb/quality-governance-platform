"""Governance Library WA-2: function axis + PEL-<FUNCTION>-<SEQ> counters (ADR-0023).

Revision ID: 20261025_lib_wa2_functions_pel
Revises: 20261024_lib_f1_malware_scan
Create Date: 2026-08-09

ADR-0023 moves the PEL reference prefix from the *category* to the owning
*function*: the category classifies, the reference identifies. Concretely:

- `document_functions` — the 11-code controlled list, seeded idempotently from
  specs/governance-library/functions.json.
- `pel_doc_ref_counters` — re-keyed from `category_id` to `function_id`. This
  is the same single counter table, repointed; WA-2 does not add a second
  allocator or a parallel counter home.
- `documents.function_id` — nullable FK, RESTRICT. Fixed at filing.
- `trg_documents_pel_doc_ref_immutable` (PostgreSQL) — refuses any UPDATE that
  rewrites an allocated `pel_doc_ref` or `function_id`, including raw SQL that
  bypasses the ORM guard in `src.domain.models.document`.

Data safety. The retired `PEL-<SECTION>-<SUB>-<SEQ>` form is never issued
again, but references already allocated under it stay verbatim on `documents`
and are not rewritten, renumbered or deleted — they are printed on document
faces and cited in client audit packs. The two forms cannot collide because
the retired form always carries a numeric subcategory group
(`PEL-HSE-01-001`) that the function form (`PEL-HSEQ-0001`) does not, so no
new allocation can reach an existing reference. The old per-category counter
rows are dropped rather than migrated: there is no meaningful mapping from
73 categories to 11 functions, and carrying a category's `next_seq` onto a
function would either skip or re-issue numbers. Every function therefore
starts at 0001.

Seeding runs only on PostgreSQL and only for functions not already present;
re-run `python -m scripts.governance.library.seed_document_categories` after
a functions.json edit rather than writing a new migration.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261025_lib_wa2_functions_pel"
down_revision: Union[str, Sequence[str], None] = "20261024_lib_f1_malware_scan"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


PEL_IMMUTABLE_TRIGGER = "trg_documents_pel_doc_ref_immutable"
PEL_IMMUTABLE_FUNCTION = "documents_pel_doc_ref_immutable"


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _columns(table_name: str) -> set[str]:
    return {c["name"] for c in _inspector().get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if not _table_exists("document_functions"):
        op.create_table(
            "document_functions",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=True),
            sa.Column("code", sa.String(length=20), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uq_document_functions_code"),
        )
        op.create_index("ix_document_functions_tenant_id", "document_functions", ["tenant_id"])
        op.create_index("ix_document_functions_code", "document_functions", ["code"])
        op.create_index("ix_document_functions_active", "document_functions", ["active"])

    _seed_functions()

    # Re-key the single counter table from category to function. Dropping is
    # safe because the counters carry no reference the documents don't already
    # hold: an allocated reference lives on `documents.pel_doc_ref`, and the
    # retired scheme issues nothing further.
    if _table_exists("pel_doc_ref_counters") and "category_id" in _columns("pel_doc_ref_counters"):
        op.drop_table("pel_doc_ref_counters")

    if not _table_exists("pel_doc_ref_counters"):
        op.create_table(
            "pel_doc_ref_counters",
            sa.Column("function_id", sa.Integer(), nullable=False),
            sa.Column("next_seq", sa.Integer(), nullable=False, server_default="1"),
            sa.ForeignKeyConstraint(["function_id"], ["document_functions.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("function_id"),
        )

    _seed_counters()

    documents_columns = _columns("documents")
    if "function_id" not in documents_columns:
        op.add_column("documents", sa.Column("function_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_documents_function_id",
            "documents",
            "document_functions",
            ["function_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        op.create_index("ix_documents_function_id", "documents", ["function_id"])

    if is_postgres:
        _install_immutability_trigger()


def _seed_functions() -> None:
    """Insert any function code from functions.json not already present.

    Idempotent and additive: an existing row is left exactly as it is, because
    its `code` is the literal prefix of every reference it has already issued
    and rewriting it here would orphan those references. Renames and
    deactivations go through the app-level reseed, not a migration.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    from src.domain.services.document_category_seed_data import load_library_functions

    functions_table = sa.table(
        "document_functions",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("sort_order", sa.Integer()),
        sa.column("active", sa.Boolean()),
    )

    existing = {row[0] for row in bind.execute(sa.text("SELECT code FROM document_functions")).all()}
    new_rows = [
        {
            "code": row["code"],
            "name": row["name"],
            "description": row["description"],
            "sort_order": row["sort_order"],
            "active": row["active"],
        }
        for row in load_library_functions()
        if row["code"] not in existing
    ]
    if new_rows:
        bind.execute(functions_table.insert(), new_rows)


def _seed_counters() -> None:
    """Create one counter per function, at 1, for functions that have none.

    Never touches an existing counter row: resetting `next_seq` would re-issue
    a reference that is already printed on a document.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    bind.execute(sa.text("""
            INSERT INTO pel_doc_ref_counters (function_id, next_seq)
            SELECT f.id, 1
            FROM document_functions f
            WHERE NOT EXISTS (
                SELECT 1 FROM pel_doc_ref_counters c WHERE c.function_id = f.id
            )
            """))


def _install_immutability_trigger() -> None:
    """Refuse any UPDATE that rewrites an allocated PEL reference or its function.

    NULL -> value is allowed (a document may be filed before its function is
    confirmed). value -> different value and value -> NULL raise, so the
    guarantee holds against raw SQL and admin consoles, not only the ORM.
    """
    op.execute(sa.text(f"""
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
            """))
    op.execute(sa.text(f"DROP TRIGGER IF EXISTS {PEL_IMMUTABLE_TRIGGER} ON documents"))
    op.execute(sa.text(f"""
            CREATE TRIGGER {PEL_IMMUTABLE_TRIGGER}
            BEFORE UPDATE ON documents
            FOR EACH ROW
            EXECUTE FUNCTION {PEL_IMMUTABLE_FUNCTION}()
            """))


def downgrade() -> None:
    bind = op.get_bind()
    is_postgres = bind.dialect.name == "postgresql"

    if is_postgres:
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS {PEL_IMMUTABLE_TRIGGER} ON documents"))
        op.execute(sa.text(f"DROP FUNCTION IF EXISTS {PEL_IMMUTABLE_FUNCTION}()"))

    documents_columns = _columns("documents")
    if "function_id" in documents_columns:
        op.drop_index("ix_documents_function_id", table_name="documents")
        op.drop_constraint("fk_documents_function_id", "documents", type_="foreignkey")
        op.drop_column("documents", "function_id")

    # Restore the Wave W0 shape of the counter table. Sequences are NOT
    # restored: the pre-WA-2 numbers are gone, and inventing them would let the
    # retired scheme re-issue a reference that a document already carries.
    # `documents.pel_doc_ref` is left untouched on the way down for the same
    # reason it is left untouched on the way up.
    if _table_exists("pel_doc_ref_counters"):
        op.drop_table("pel_doc_ref_counters")
    op.create_table(
        "pel_doc_ref_counters",
        sa.Column("category_id", sa.Integer(), nullable=False),
        sa.Column("next_seq", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["category_id"], ["document_categories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("category_id"),
    )

    if _table_exists("document_functions"):
        op.drop_index("ix_document_functions_active", table_name="document_functions")
        op.drop_index("ix_document_functions_code", table_name="document_functions")
        op.drop_index("ix_document_functions_tenant_id", table_name="document_functions")
        op.drop_table("document_functions")
