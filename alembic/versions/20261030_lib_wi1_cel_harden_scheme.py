"""WI-1 / L-26–28: CEL harden + standards scheme converge (D14 / D15).

Revision ID: 20261030_lib_wi1_cel
Revises: 20261029_lib_ns_wf_review_cycle
Create Date: 2026-08-09

Absolute rules (F-3 / D14 / D15)
--------------------------------
- ``compliance_evidence_links`` stays the coverage SoT — no
  ``document_coverage_claims`` / frameworks twin.
- Clause identity converges onto ``clauses.catalogue_key`` equal to
  ``ALL_CLAUSES`` / CEL ``clause_id`` strings.
- Scheme identity (UVDB B2, Planet Mark) lands as ``standards.kind =
  scheme`` shells; UVDB/PM trees stay in their existing homes.

What this revision does
-----------------------
1. ``standards.kind`` — ``iso`` | ``scheme`` (NOT NULL, default ``iso``).
2. Seed / stamp ISO edition rows + UVDB_B2 / PLANET_MARK scheme shells.
3. ``clauses.catalogue_key`` + partial unique where not null; upsert every
   ``ALL_CLAUSES`` id under the matching ISO standard.
4. CEL ``cover_kind`` (``covers`` | ``evidences``, default ``evidences``) and
   durable ``confirmed_by_id`` / ``confirmed_at``.
5. Replace the live-blind unique index with a soft-delete-aware partial
   unique that includes ``cover_kind`` so reject/soft-delete → re-link works
   and one entity may hold both a covers and an evidences row for the same
   clause.

Legacy backfill notes
---------------------
- Existing CEL rows get ``cover_kind = evidences`` (conservative; never
  silently claim ``covers``).
- Historical *manual* confirmed rows copy ``created_by_id`` →
  ``confirmed_by_id`` and ``updated_at``/``created_at`` → ``confirmed_at``.
  AI / auto-applied confirmed rows are left without a confirmer — humans
  must stamp via the confirm routes.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261030_lib_wi1_cel"
down_revision: Union[str, Sequence[str], None] = "20261029_lib_ns_wf_review_cycle"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

OLD_CEL_UNIQUE = "ix_cel_tenant_entity_clause"
NEW_CEL_UNIQUE = "ux_cel_tenant_entity_clause_cover_live"
CEL_UNIQUE_PREDICATE = "deleted_at IS NULL"
CEL_UNIQUE_DDL = (
    f"CREATE UNIQUE INDEX {NEW_CEL_UNIQUE} ON compliance_evidence_links "
    f"(tenant_id, entity_type, entity_id, clause_id, cover_kind) "
    f"WHERE {CEL_UNIQUE_PREDICATE}"
)
CLAUSE_CATALOGUE_UNIQUE = "ux_clauses_catalogue_key"
CLAUSE_CATALOGUE_PREDICATE = "catalogue_key IS NOT NULL"
CLAUSE_CATALOGUE_DDL = (
    f"CREATE UNIQUE INDEX {CLAUSE_CATALOGUE_UNIQUE} ON clauses (catalogue_key) "
    f"WHERE {CLAUSE_CATALOGUE_PREDICATE}"
)


def _inspector() -> sa.Inspector:
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _columns(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {c["name"] for c in _inspector().get_columns(table_name)}


def _index_exists(index_name: str, table_name: str) -> bool:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return bool(
            bind.execute(
                sa.text("SELECT 1 FROM pg_class WHERE relkind = 'i' AND relname = :name"),
                {"name": index_name},
            ).fetchone()
        )
    if not _table_exists(table_name):
        return False
    return any(idx["name"] == index_name for idx in _inspector().get_indexes(table_name))


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _add_standards_kind() -> None:
    cols = _columns("standards")
    if "kind" not in cols:
        op.add_column(
            "standards",
            sa.Column(
                "kind",
                sa.String(length=20),
                nullable=False,
                server_default="iso",
            ),
        )
    op.execute(sa.text("UPDATE standards SET kind = 'iso' WHERE kind IS NULL OR kind = ''"))
    # Drop server default after backfill so new inserts must choose explicitly
    # at the ORM layer (ORM still supplies default=iso).
    try:
        op.alter_column("standards", "kind", server_default=None)
    except Exception:
        # SQLite / some dialects cannot drop server defaults cleanly; leave it.
        logger.info("%s: left standards.kind server_default in place", revision)

    # Check constraint — idempotent name.
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("ALTER TABLE standards DROP CONSTRAINT IF EXISTS ck_standards_kind"))
        op.execute(
            sa.text(
                "ALTER TABLE standards ADD CONSTRAINT ck_standards_kind "
                "CHECK (kind IN ('iso', 'scheme'))"
            )
        )


def _add_clause_catalogue_key() -> None:
    cols = _columns("clauses")
    if "catalogue_key" not in cols:
        op.add_column(
            "clauses",
            sa.Column("catalogue_key", sa.String(length=50), nullable=True),
        )
        op.create_index("ix_clauses_catalogue_key", "clauses", ["catalogue_key"])
    if not _index_exists(CLAUSE_CATALOGUE_UNIQUE, "clauses"):
        if _is_postgres():
            op.execute(sa.text(CLAUSE_CATALOGUE_DDL))
        else:
            op.create_index(
                CLAUSE_CATALOGUE_UNIQUE,
                "clauses",
                ["catalogue_key"],
                unique=True,
                sqlite_where=sa.text(CLAUSE_CATALOGUE_PREDICATE),
            )


def _seed_standards_and_clauses() -> None:
    """PostgreSQL-only: stamp ISO kind, insert scheme shells, upsert ALL_CLAUSES."""
    if not _is_postgres():
        return
    if not _table_exists("standards") or not _table_exists("clauses"):
        return

    from src.domain.services.clause_catalogue_seed import (
        STANDARD_KIND_ISO,
        build_clause_catalogue_rows,
        build_iso_standard_upserts,
        build_scheme_standard_upserts,
        match_iso_standard_row,
    )
    from src.domain.services.iso_compliance_service import ISOStandard

    bind = op.get_bind()
    standards_rows = bind.execute(
        sa.text("SELECT id, code, name, full_name, kind FROM standards")
    ).mappings().all()

    # Stamp existing ISO editions.
    for row in standards_rows:
        matched = match_iso_standard_row(row)
        if matched is not None and row.get("kind") != STANDARD_KIND_ISO:
            bind.execute(
                sa.text("UPDATE standards SET kind = :kind WHERE id = :id"),
                {"kind": STANDARD_KIND_ISO, "id": row["id"]},
            )

    to_insert_iso, iso_to_id = build_iso_standard_upserts(standards_rows)
    for row in to_insert_iso:
        result = bind.execute(
            sa.text(
                """
                INSERT INTO standards (code, name, full_name, version, description, kind, is_active)
                VALUES (:code, :name, :full_name, :version, :description, :kind, :is_active)
                RETURNING id
                """
            ),
            row,
        )
        new_id = result.scalar_one()
        # Map by matching the inserted code back to ISO enum.
        for spec_iso, spec in (
            (ISOStandard.ISO_9001, "ISO9001"),
            (ISOStandard.ISO_14001, "ISO14001"),
            (ISOStandard.ISO_45001, "ISO45001"),
            (ISOStandard.ISO_27001, "ISO27001"),
        ):
            if row["code"] == spec:
                iso_to_id[spec_iso] = new_id

    # Refresh iso_to_id for rows that existed by exact canonical code but
    # were skipped by build_iso_standard_upserts' "code in existing" branch.
    refreshed = bind.execute(
        sa.text("SELECT id, code, name, full_name FROM standards")
    ).mappings().all()
    for row in refreshed:
        matched = match_iso_standard_row(row)
        if matched is not None:
            iso_to_id.setdefault(matched, int(row["id"]))

    scheme_rows = build_scheme_standard_upserts(refreshed)
    for row in scheme_rows:
        bind.execute(
            sa.text(
                """
                INSERT INTO standards (code, name, full_name, version, description, kind, is_active)
                VALUES (:code, :name, :full_name, :version, :description, :kind, :is_active)
                """
            ),
            row,
        )

    missing = [iso.value for iso in ISOStandard if iso not in iso_to_id]
    if missing:
        raise RuntimeError(
            f"{revision}: cannot seed clauses.catalogue_key — missing standards for {missing}"
        )

    clause_plans = build_clause_catalogue_rows(iso_to_id)
    existing_keys = {
        row[0]
        for row in bind.execute(
            sa.text("SELECT catalogue_key FROM clauses WHERE catalogue_key IS NOT NULL")
        ).all()
    }

    for plan in clause_plans:
        if plan["catalogue_key"] in existing_keys:
            continue
        bind.execute(
            sa.text(
                """
                INSERT INTO clauses (
                    standard_id, catalogue_key, clause_number, title, description,
                    level, sort_order, is_active
                ) VALUES (
                    :standard_id, :catalogue_key, :clause_number, :title, :description,
                    :level, :sort_order, :is_active
                )
                """
            ),
            {
                "standard_id": plan["standard_id"],
                "catalogue_key": plan["catalogue_key"],
                "clause_number": plan["clause_number"],
                "title": plan["title"],
                "description": plan["description"],
                "level": plan["level"],
                "sort_order": plan["sort_order"],
                "is_active": plan["is_active"],
            },
        )
        existing_keys.add(plan["catalogue_key"])

    # Second pass: parent FK via catalogue_key.
    key_to_id = {
        row[0]: row[1]
        for row in bind.execute(
            sa.text("SELECT catalogue_key, id FROM clauses WHERE catalogue_key IS NOT NULL")
        ).all()
    }
    for plan in clause_plans:
        parent_key = plan.get("parent_catalogue_key")
        if not parent_key:
            continue
        parent_id = key_to_id.get(parent_key)
        child_id = key_to_id.get(plan["catalogue_key"])
        if parent_id is None or child_id is None:
            continue
        bind.execute(
            sa.text(
                """
                UPDATE clauses
                SET parent_clause_id = :parent_id
                WHERE id = :child_id
                  AND (parent_clause_id IS NULL OR parent_clause_id IS DISTINCT FROM :parent_id)
                """
            ),
            {"parent_id": parent_id, "child_id": child_id},
        )

    logger.info(
        "%s: catalogue_key coverage — %s ALL_CLAUSES keys present in clauses",
        revision,
        len(existing_keys),
    )


def _harden_cel() -> None:
    cols = _columns("compliance_evidence_links")
    if not cols:
        return

    if "cover_kind" not in cols:
        op.add_column(
            "compliance_evidence_links",
            sa.Column(
                "cover_kind",
                sa.String(length=20),
                nullable=False,
                server_default="evidences",
            ),
        )
        op.execute(
            sa.text(
                "UPDATE compliance_evidence_links SET cover_kind = 'evidences' "
                "WHERE cover_kind IS NULL OR cover_kind = ''"
            )
        )
        op.create_index("ix_cel_cover_kind", "compliance_evidence_links", ["cover_kind"])

    if "confirmed_by_id" not in cols:
        op.add_column(
            "compliance_evidence_links",
            sa.Column("confirmed_by_id", sa.Integer(), nullable=True),
        )
        op.create_foreign_key(
            "fk_cel_confirmed_by_id_users",
            "compliance_evidence_links",
            "users",
            ["confirmed_by_id"],
            ["id"],
        )
    if "confirmed_at" not in cols:
        op.add_column(
            "compliance_evidence_links",
            sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        )

    # Legacy manual confirmed → durable confirmer (D15 audit note).
    op.execute(
        sa.text(
            """
            UPDATE compliance_evidence_links
            SET confirmed_by_id = created_by_id,
                confirmed_at = COALESCE(updated_at, created_at)
            WHERE deleted_at IS NULL
              AND confirmed_by_id IS NULL
              AND created_by_id IS NOT NULL
              AND COALESCE(auto_applied, false) = false
              AND (
                    lower(COALESCE(status, '')) = 'confirmed'
                    OR (status IS NULL AND lower(COALESCE(linked_by, '')) = 'manual')
                  )
            """
        )
    )

    if _is_postgres():
        op.execute(
            sa.text(
                "ALTER TABLE compliance_evidence_links "
                "DROP CONSTRAINT IF EXISTS ck_cel_cover_kind"
            )
        )
        op.execute(
            sa.text(
                "ALTER TABLE compliance_evidence_links ADD CONSTRAINT ck_cel_cover_kind "
                "CHECK (cover_kind IN ('covers', 'evidences'))"
            )
        )

    if _index_exists(OLD_CEL_UNIQUE, "compliance_evidence_links"):
        op.drop_index(OLD_CEL_UNIQUE, table_name="compliance_evidence_links")

    if not _index_exists(NEW_CEL_UNIQUE, "compliance_evidence_links"):
        if _is_postgres():
            op.execute(sa.text(CEL_UNIQUE_DDL))
        else:
            op.create_index(
                NEW_CEL_UNIQUE,
                "compliance_evidence_links",
                ["tenant_id", "entity_type", "entity_id", "clause_id", "cover_kind"],
                unique=True,
                sqlite_where=sa.text(CEL_UNIQUE_PREDICATE),
            )


def upgrade() -> None:
    if _table_exists("standards"):
        _add_standards_kind()
    if _table_exists("clauses"):
        _add_clause_catalogue_key()
    _seed_standards_and_clauses()
    if _table_exists("compliance_evidence_links"):
        _harden_cel()


def downgrade() -> None:
    if _table_exists("compliance_evidence_links"):
        if _index_exists(NEW_CEL_UNIQUE, "compliance_evidence_links"):
            op.drop_index(NEW_CEL_UNIQUE, table_name="compliance_evidence_links")
        if not _index_exists(OLD_CEL_UNIQUE, "compliance_evidence_links"):
            op.create_index(
                OLD_CEL_UNIQUE,
                "compliance_evidence_links",
                ["tenant_id", "entity_type", "entity_id", "clause_id"],
                unique=True,
            )
        cols = _columns("compliance_evidence_links")
        if _is_postgres():
            op.execute(
                sa.text(
                    "ALTER TABLE compliance_evidence_links "
                    "DROP CONSTRAINT IF EXISTS ck_cel_cover_kind"
                )
            )
        if "confirmed_at" in cols:
            op.drop_column("compliance_evidence_links", "confirmed_at")
        if "confirmed_by_id" in cols:
            op.drop_constraint(
                "fk_cel_confirmed_by_id_users",
                "compliance_evidence_links",
                type_="foreignkey",
            )
            op.drop_column("compliance_evidence_links", "confirmed_by_id")
        if "cover_kind" in cols:
            if _index_exists("ix_cel_cover_kind", "compliance_evidence_links"):
                op.drop_index("ix_cel_cover_kind", table_name="compliance_evidence_links")
            op.drop_column("compliance_evidence_links", "cover_kind")

    if _table_exists("clauses"):
        if _index_exists(CLAUSE_CATALOGUE_UNIQUE, "clauses"):
            op.drop_index(CLAUSE_CATALOGUE_UNIQUE, table_name="clauses")
        if _index_exists("ix_clauses_catalogue_key", "clauses"):
            op.drop_index("ix_clauses_catalogue_key", table_name="clauses")
        if "catalogue_key" in _columns("clauses"):
            op.drop_column("clauses", "catalogue_key")

    if _table_exists("standards") and "kind" in _columns("standards"):
        if _is_postgres():
            op.execute(sa.text("ALTER TABLE standards DROP CONSTRAINT IF EXISTS ck_standards_kind"))
        op.drop_column("standards", "kind")
