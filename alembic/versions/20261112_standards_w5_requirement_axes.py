"""Int-W5 — seed ISO 22301 + scheme requirement axis clause rows.

Revision ID: 20261112_standards_w5_axes
Revises: 20261105_standards_alignment
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20261112_standards_w5_axes"
down_revision: Union[str, Sequence[str], None] = "20261105_standards_alignment"
branch_labels = None
depends_on = None


def _table(name: str) -> sa.Table:
    return sa.table(
        name,
        sa.column("id", sa.Integer),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
        sa.column("full_name", sa.String),
        sa.column("version", sa.String),
        sa.column("description", sa.Text),
        sa.column("kind", sa.String),
        sa.column("is_active", sa.Boolean),
        sa.column("standard_id", sa.Integer),
        sa.column("catalogue_key", sa.String),
        sa.column("clause_number", sa.String),
        sa.column("title", sa.String),
        sa.column("level", sa.Integer),
        sa.column("sort_order", sa.Integer),
        sa.column("parent_clause_id", sa.Integer),
    )


def upgrade() -> None:
    from src.domain.services.clause_catalogue_seed import (
        SCHEME_STANDARD_SPECS,
        build_clause_catalogue_rows,
        build_iso_standard_upserts,
        build_scheme_standard_upserts,
    )
    from src.domain.services.iso_compliance_service import ALL_CLAUSES, ISOStandard
    from src.domain.services.standards_requirement_axis import build_scheme_requirement_clause_plans

    bind = op.get_bind()
    standards = _table("standards")
    clauses = _table("clauses")

    existing = [
        dict(row)
        for row in bind.execute(
            sa.select(
                standards.c.id,
                standards.c.code,
                standards.c.name,
                standards.c.full_name,
            )
        ).mappings()
    ]
    inserts, iso_to_id = build_iso_standard_upserts(existing)
    for row in inserts:
        bind.execute(
            standards.insert().values(
                code=row["code"],
                name=row["name"],
                full_name=row["full_name"],
                version=row["version"],
                description=row["description"],
                kind=row["kind"],
                is_active=True,
            )
        )
    # Refresh ids after inserts
    existing = [
        dict(row)
        for row in bind.execute(
            sa.select(
                standards.c.id,
                standards.c.code,
                standards.c.name,
                standards.c.full_name,
            )
        ).mappings()
    ]
    _, iso_to_id = build_iso_standard_upserts(existing)
    # Match by code for ISO22301 if matcher already found via existing row
    for row in existing:
        code = str(row["code"]).replace(" ", "").upper()
        if "22301" in code and ISOStandard.ISO_22301 not in iso_to_id:
            iso_to_id[ISOStandard.ISO_22301] = int(row["id"])

    # Ensure every ISO in ALL_CLAUSES has an id
    for iso in ISOStandard:
        if iso not in iso_to_id:
            raise RuntimeError(f"Int-W5 seed: missing standards.id for {iso.value}")

    scheme_inserts = build_scheme_standard_upserts(existing)
    for row in scheme_inserts:
        bind.execute(
            standards.insert().values(
                code=row["code"],
                name=row["name"],
                full_name=row["full_name"],
                version=row["version"],
                description=row["description"],
                kind=row["kind"],
                is_active=True,
            )
        )

    code_to_id = {
        str(row["code"]): int(row["id"])
        for row in bind.execute(sa.select(standards.c.id, standards.c.code)).mappings()
    }

    existing_keys = {
        str(row["catalogue_key"])
        for row in bind.execute(sa.select(clauses.c.catalogue_key)).mappings()
        if row["catalogue_key"]
    }

    # ISO 22301 (and any missing ALL_CLAUSES keys) — insert only.
    iso_plans = build_clause_catalogue_rows(iso_to_id)
    for plan in iso_plans:
        if plan["catalogue_key"] in existing_keys:
            continue
        if not str(plan["catalogue_key"]).startswith("22301-"):
            # Other ISO clauses already seeded by WI-1; do not rewrite.
            continue
        bind.execute(
            clauses.insert().values(
                standard_id=plan["standard_id"],
                catalogue_key=plan["catalogue_key"],
                clause_number=plan["clause_number"],
                title=plan["title"],
                description=plan["description"],
                level=plan["level"],
                sort_order=plan["sort_order"],
                is_active=True,
            )
        )
        existing_keys.add(plan["catalogue_key"])

    for plan in build_scheme_requirement_clause_plans(code_to_id):
        if plan["catalogue_key"] in existing_keys:
            continue
        bind.execute(
            clauses.insert().values(
                standard_id=plan["standard_id"],
                catalogue_key=plan["catalogue_key"],
                clause_number=plan["clause_number"],
                title=plan["title"],
                description=plan["description"],
                level=plan["level"],
                sort_order=plan["sort_order"],
                is_active=True,
            )
        )
        existing_keys.add(plan["catalogue_key"])

    # Silence unused import if SCHEME_STANDARD_SPECS only referenced indirectly
    _ = SCHEME_STANDARD_SPECS
    _ = ALL_CLAUSES


def downgrade() -> None:
    bind = op.get_bind()
    standards = _table("standards")
    clauses = _table("clauses")

    # Delete only W5-created catalogue keys / codes.
    w5_codes = (
        "ISO22301",
        "CYBER_ESSENTIALS",
        "CYBER_ESS_PLUS",
        "CHAS_CAS",
        "SSIP_CORE",
        "IIP_2018",
    )
    ids = [
        int(row["id"])
        for row in bind.execute(
            sa.select(standards.c.id).where(standards.c.code.in_(w5_codes))
        ).mappings()
    ]
    if ids:
        bind.execute(clauses.delete().where(clauses.c.standard_id.in_(ids)))
        bind.execute(standards.delete().where(standards.c.id.in_(ids)))

    # UVDB/PM scheme shells pre-existed — only drop W5 requirement keys.
    bind.execute(
        clauses.delete().where(
            sa.or_(
                clauses.c.catalogue_key.like("uvdb-%"),
                clauses.c.catalogue_key.like("pm-%"),
                clauses.c.catalogue_key.like("ce-%"),
                clauses.c.catalogue_key.like("cep-%"),
                clauses.c.catalogue_key.like("chas-%"),
                clauses.c.catalogue_key.like("ssip-%"),
                clauses.c.catalogue_key.like("iip-%"),
                clauses.c.catalogue_key.like("22301-%"),
            )
        )
    )
