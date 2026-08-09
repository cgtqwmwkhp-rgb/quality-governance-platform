"""NS-FUNC / W2: reseed functions — CTR+SVC active, OPS withdrawn.

Revision ID: 20261028_lib_ns_func_ctr_svc
Revises: 20261027_lib_ns1_banded_pel
Create Date: 2026-08-09

Northern Star v6.0 FINAL (ADR-0023 § Amendment) splits the WA-2 OPS fold into
CTR (Control Room) and SVC (Service Delivery / workshop). Deploy runs
``alembic upgrade head`` only — not the admin reseed endpoint — so this
revision must land the vocabulary change on production:

- Upsert every row from ``specs/governance-library/functions.json``
  (insert CTR/SVC; refresh names/descriptions/sort_order/active).
- Force ``OPS.active = false`` even if a prior manual edit reactivated it.
- Seed missing ``pel_doc_ref_counters`` rows for new functions × bands 1–5
  (NS-1 shape). Never reset an existing ``next_seq`` (R06/R29).

Issued ``PEL-OPS-####`` strings on ``documents`` are never rewritten. OPS
remains as an inactive ``document_functions`` row so those references stay
resolvable; forward filing must pick CTR or SVC.
"""

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261028_lib_ns_func_ctr_svc"
down_revision: Union[str, Sequence[str], None] = "20261027_lib_ns1_banded_pel"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CASCADE_BANDS = (1, 2, 3, 4, 5)


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if not _table_exists("document_functions"):
        return

    _upsert_functions()
    _force_ops_inactive()
    _seed_banded_counters()


def downgrade() -> None:
    """Best-effort: reactivate OPS and deactivate CTR/SVC.

    Does not delete CTR/SVC rows (they may already own issued references) and
    does not touch counters. Prefer forward fix over downgrade in production.
    """
    bind = op.get_bind()
    if bind.dialect.name != "postgresql":
        return
    if not _table_exists("document_functions"):
        return
    bind.execute(
        sa.text(
            """
            UPDATE document_functions
            SET active = true,
                name = 'Operations',
                updated_at = NOW()
            WHERE code = 'OPS'
            """
        )
    )
    bind.execute(
        sa.text(
            """
            UPDATE document_functions
            SET active = false, updated_at = NOW()
            WHERE code IN ('CTR', 'SVC')
            """
        )
    )


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _upsert_functions() -> None:
    from src.domain.services.document_category_seed_data import load_library_functions

    bind = op.get_bind()
    existing = {
        row[0]: row
        for row in bind.execute(
            sa.text("SELECT code, id FROM document_functions")
        ).all()
    }

    for row in load_library_functions():
        if row["code"] in existing:
            bind.execute(
                sa.text(
                    """
                    UPDATE document_functions
                    SET name = :name,
                        description = :description,
                        sort_order = :sort_order,
                        active = :active,
                        updated_at = NOW()
                    WHERE code = :code
                    """
                ),
                {
                    "code": row["code"],
                    "name": row["name"],
                    "description": row["description"],
                    "sort_order": row["sort_order"],
                    "active": row["active"],
                },
            )
        else:
            bind.execute(
                sa.text(
                    """
                    INSERT INTO document_functions
                        (code, name, description, sort_order, active)
                    VALUES
                        (:code, :name, :description, :sort_order, :active)
                    """
                ),
                {
                    "code": row["code"],
                    "name": row["name"],
                    "description": row["description"],
                    "sort_order": row["sort_order"],
                    "active": row["active"],
                },
            )


def _force_ops_inactive() -> None:
    """Belt-and-braces: OPS must not appear in filing pickers after W2."""
    op.get_bind().execute(
        sa.text(
            """
            UPDATE document_functions
            SET active = false,
                name = 'Operations (withdrawn — use CTR or SVC)',
                updated_at = NOW()
            WHERE code = 'OPS'
            """
        )
    )


def _seed_banded_counters() -> None:
    """One counter per (function, band) at next_seq=1 — never reset existing."""
    if not _table_exists("pel_doc_ref_counters"):
        return
    cols = {c["name"] for c in sa.inspect(op.get_bind()).get_columns("pel_doc_ref_counters")}
    if "level_band" not in cols:
        # Pre-NS-1 shape should not exist on this revision's parent, but refuse
        # to invent a wrong insert rather than corrupt the allocator.
        return

    bands = ", ".join(str(band) for band in CASCADE_BANDS)
    op.get_bind().execute(
        sa.text(
            f"""
            INSERT INTO pel_doc_ref_counters (function_id, level_band, next_seq)
            SELECT f.id, b.band, 1
            FROM document_functions f
            CROSS JOIN (SELECT unnest(ARRAY[{bands}]) AS band) b
            WHERE NOT EXISTS (
                SELECT 1
                FROM pel_doc_ref_counters c
                WHERE c.function_id = f.id AND c.level_band = b.band
            )
            """
        )
    )
