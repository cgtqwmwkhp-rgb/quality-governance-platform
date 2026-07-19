"""Governance Library Wave W0: taxonomy categories, tags, PEL doc-ref counters.

Revision ID: 20260719_gov_lib_w0_taxonomy_pel
Revises: 20260719_index_job_doc_prog
Create Date: 2026-07-19

Adds the Governance Library taxonomy layer alongside the existing
`documents` (file SoT) / `controlled_documents` (control layer) split:

- `document_categories` — 2-level taxonomy (13 sections + 73 subcategories
  = 86 rows), seeded idempotently from specs/governance-library/taxonomy.json.
  06.04 (O-Licence & Tachograph / HGV) seeds `active=false` (Wave W0
  decision — Plantexpand does not currently run HGVs under an O-licence).
- `document_tags` — controlled tag vocabulary, seeded minus the ISO
  standards tags (iso-9001/14001/45001/27001 dropped; planet-mark + all
  subject/audience/process tags kept).
- `pel_doc_ref_counters` — one row per level-2 category, backing atomic
  `PEL-<SECTION>-<SUB>-<SEQ>` allocation.
- `documents.category_id` (nullable FK), `documents.pel_doc_ref` (nullable
  unique — sits alongside the existing `reference_number` DOC-YYYY-####),
  `documents.site_location_id` (nullable FK to the existing `locations`
  table — no new Site table).

Seeding runs only on first apply (skipped if `document_categories` already
has rows) and only against PostgreSQL; use
`python -m scripts.governance.library.seed_document_categories` to
(re)seed idempotently after a taxonomy.json edit.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20260719_gov_lib_w0_taxonomy_pel"
down_revision: Union[str, Sequence[str], None] = "20260719_index_job_doc_prog"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def upgrade() -> None:
    if not _table_exists("document_categories"):
        op.create_table(
            "document_categories",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=True),
            sa.Column("taxonomy_id", sa.String(length=20), nullable=False),
            sa.Column("parent_id", sa.Integer(), nullable=True),
            sa.Column("level", sa.Integer(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("slug", sa.String(length=200), nullable=False),
            sa.Column("ref_prefix", sa.String(length=20), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("default_access", sa.String(length=20), nullable=True),
            sa.Column("access_note", sa.Text(), nullable=True),
            sa.Column("suggested_owner_role", sa.String(length=200), nullable=True),
            sa.Column("review_cycle", sa.String(length=200), nullable=True),
            sa.Column("retention_rule", sa.Text(), nullable=True),
            sa.Column("typical_contents", sa.Text(), nullable=True),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["parent_id"], ["document_categories.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("taxonomy_id", name="uq_document_categories_taxonomy_id"),
        )
        op.create_index("ix_document_categories_tenant_id", "document_categories", ["tenant_id"])
        op.create_index("ix_document_categories_taxonomy_id", "document_categories", ["taxonomy_id"])
        op.create_index("ix_document_categories_parent_id", "document_categories", ["parent_id"])
        op.create_index("ix_document_categories_slug", "document_categories", ["slug"])
        op.create_index("ix_document_categories_active", "document_categories", ["active"])

    if not _table_exists("document_tags"):
        op.create_table(
            "document_tags",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("tenant_id", sa.Integer(), nullable=True),
            sa.Column("slug", sa.String(length=100), nullable=False),
            sa.Column("label", sa.String(length=200), nullable=False),
            sa.Column("group", sa.String(length=50), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug", name="uq_document_tags_slug"),
        )
        op.create_index("ix_document_tags_tenant_id", "document_tags", ["tenant_id"])
        op.create_index("ix_document_tags_slug", "document_tags", ["slug"])

    if not _table_exists("pel_doc_ref_counters"):
        op.create_table(
            "pel_doc_ref_counters",
            sa.Column("category_id", sa.Integer(), nullable=False),
            sa.Column("next_seq", sa.Integer(), nullable=False, server_default="1"),
            sa.ForeignKeyConstraint(["category_id"], ["document_categories.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("category_id"),
        )

    documents_columns = {c["name"] for c in _inspector().get_columns("documents")}
    if "category_id" not in documents_columns:
        op.add_column("documents", sa.Column("category_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_documents_category_id",
            "documents",
            "document_categories",
            ["category_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_documents_category_id", "documents", ["category_id"])

    if "pel_doc_ref" not in documents_columns:
        op.add_column("documents", sa.Column("pel_doc_ref", sa.String(length=30), nullable=True))
        op.create_index("ix_documents_pel_doc_ref", "documents", ["pel_doc_ref"], unique=True)

    if "site_location_id" not in documents_columns:
        op.add_column("documents", sa.Column("site_location_id", sa.Integer(), nullable=True))
        op.create_foreign_key(
            "fk_documents_site_location_id",
            "documents",
            "locations",
            ["site_location_id"],
            ["id"],
            ondelete="SET NULL",
        )
        op.create_index("ix_documents_site_location_id", "documents", ["site_location_id"])

    _seed_initial_taxonomy()


def _seed_initial_taxonomy() -> None:
    """One-shot initial seed — skipped if document_categories already has rows.

    Only runs on PostgreSQL (matches production/staging); re-seeding after
    a taxonomy.json edit goes through
    `python -m scripts.governance.library.seed_document_categories`, not
    a new migration.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return

    existing_count = bind.execute(sa.text("SELECT COUNT(*) FROM document_categories")).scalar_one()
    if existing_count:
        return

    from src.domain.services.document_category_seed_data import TAG_SEED, load_taxonomy_categories

    categories_table = sa.table(
        "document_categories",
        sa.column("id", sa.Integer()),
        sa.column("taxonomy_id", sa.String()),
        sa.column("parent_id", sa.Integer()),
        sa.column("level", sa.Integer()),
        sa.column("sort_order", sa.Integer()),
        sa.column("name", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("ref_prefix", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("default_access", sa.String()),
        sa.column("access_note", sa.Text()),
        sa.column("suggested_owner_role", sa.String()),
        sa.column("review_cycle", sa.String()),
        sa.column("retention_rule", sa.Text()),
        sa.column("typical_contents", sa.Text()),
        sa.column("active", sa.Boolean()),
    )
    counters_table = sa.table(
        "pel_doc_ref_counters",
        sa.column("category_id", sa.Integer()),
        sa.column("next_seq", sa.Integer()),
    )
    tags_table = sa.table(
        "document_tags",
        sa.column("slug", sa.String()),
        sa.column("label", sa.String()),
        sa.column("group", sa.String()),
        sa.column("active", sa.Boolean()),
    )

    rows = load_taxonomy_categories()
    db_id_by_taxonomy_id: dict[str, int] = {}
    level2_db_ids: list[int] = []

    for level in (1, 2):
        for row in rows:
            if row["level"] != level:
                continue
            parent_db_id = db_id_by_taxonomy_id.get(row["parent_taxonomy_id"]) if row["parent_taxonomy_id"] else None
            result = bind.execute(
                categories_table.insert().values(
                    taxonomy_id=row["taxonomy_id"],
                    parent_id=parent_db_id,
                    level=row["level"],
                    sort_order=row["sort_order"],
                    name=row["name"],
                    slug=row["slug"],
                    ref_prefix=row["ref_prefix"],
                    description=row["description"],
                    default_access=row["default_access"],
                    access_note=row["access_note"],
                    suggested_owner_role=row["suggested_owner_role"],
                    review_cycle=row["review_cycle"],
                    retention_rule=row["retention_rule"],
                    typical_contents=row["typical_contents"],
                    active=row["active"],
                ).returning(categories_table.c.id)
            )
            new_id = result.scalar_one()
            db_id_by_taxonomy_id[row["taxonomy_id"]] = new_id
            if row["level"] == 2:
                level2_db_ids.append(new_id)

    if level2_db_ids:
        bind.execute(
            counters_table.insert(),
            [{"category_id": cid, "next_seq": 1} for cid in level2_db_ids],
        )

    if TAG_SEED:
        bind.execute(
            tags_table.insert(),
            [{"slug": t["slug"], "label": t["label"], "group": t["group"], "active": True} for t in TAG_SEED],
        )


def downgrade() -> None:
    documents_columns = {c["name"] for c in _inspector().get_columns("documents")}
    if "site_location_id" in documents_columns:
        op.drop_index("ix_documents_site_location_id", table_name="documents")
        op.drop_constraint("fk_documents_site_location_id", "documents", type_="foreignkey")
        op.drop_column("documents", "site_location_id")

    if "pel_doc_ref" in documents_columns:
        op.drop_index("ix_documents_pel_doc_ref", table_name="documents")
        op.drop_column("documents", "pel_doc_ref")

    if "category_id" in documents_columns:
        op.drop_index("ix_documents_category_id", table_name="documents")
        op.drop_constraint("fk_documents_category_id", "documents", type_="foreignkey")
        op.drop_column("documents", "category_id")

    if _table_exists("pel_doc_ref_counters"):
        op.drop_table("pel_doc_ref_counters")

    if _table_exists("document_tags"):
        op.drop_table("document_tags")

    if _table_exists("document_categories"):
        op.drop_table("document_categories")
