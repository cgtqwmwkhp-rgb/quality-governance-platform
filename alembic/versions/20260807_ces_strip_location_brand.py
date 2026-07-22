"""Strip Plantexpand brand prefix from CES provisional location names.

Revision ID: 20260807_ces_loc_brand
Revises: 20260806_catalog_ssot
"""

from __future__ import annotations

import re
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260807_ces_loc_brand"
down_revision: Union[str, Sequence[str], None] = "20260806_catalog_ssot"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_BRAND_PREFIX_RE = re.compile(
    r"^(?:plantexpand(?:\s+limited|\s+ltd)?)\b[\s,.-]*",
    re.IGNORECASE,
)
_LEADING_LTD_RE = re.compile(r"^ltd\b[\s,.-]*", re.IGNORECASE)


def _strip_brand(name: str) -> str:
    result = re.sub(r"\s+", " ", (name or "")).strip(" ,-")
    while True:
        match = _BRAND_PREFIX_RE.match(result)
        if not match:
            break
        result = result[match.end() :].strip(" ,-")
    result = _LEADING_LTD_RE.sub("", result).strip(" ,-")
    return result


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text("""
            SELECT id, tenant_id, name, approval_status
            FROM locations
            WHERE name ILIKE 'plantexpand%'
            ORDER BY id
            """)).fetchall()

    for row in rows:
        loc_id, tenant_id, name, approval_status = row[0], row[1], row[2], row[3]
        new_name = _strip_brand(name)
        if not new_name or new_name == name:
            # Brand-only name: keep a stable placeholder so FK rows remain addressable.
            if not new_name:
                new_name = f"Unspecified site ({loc_id})"
            else:
                continue

        existing = conn.execute(
            sa.text("""
                SELECT id FROM locations
                WHERE tenant_id = :tenant_id
                  AND lower(name) = lower(:new_name)
                  AND id <> :loc_id
                ORDER BY
                  CASE WHEN approval_status = 'approved' THEN 0 ELSE 1 END,
                  id
                LIMIT 1
                """),
            {"tenant_id": tenant_id, "new_name": new_name, "loc_id": loc_id},
        ).fetchone()

        if existing:
            target_id = existing[0]
            conn.execute(
                sa.text("""
                    UPDATE assets
                    SET location_id = :target_id,
                        site = CASE
                          WHEN site ILIKE 'plantexpand%' THEN :new_name
                          ELSE site
                        END
                    WHERE location_id = :loc_id
                    """),
                {"target_id": target_id, "new_name": new_name, "loc_id": loc_id},
            )
            # Preserve every relationship to the merged location, not just assets.
            conn.execute(
                sa.text("""
                    UPDATE documents
                    SET site_location_id = :target_id
                    WHERE site_location_id = :loc_id
                    """),
                {"target_id": target_id, "loc_id": loc_id},
            )
            conn.execute(
                sa.text("""
                    UPDATE audit_runs
                    SET location_id = :target_id
                    WHERE location_id = :loc_id
                    """),
                {"target_id": target_id, "loc_id": loc_id},
            )
            conn.execute(
                sa.text("""
                    UPDATE asset_assignment_events
                    SET from_location_id = :target_id
                    WHERE from_location_id = :loc_id
                    """),
                {"target_id": target_id, "loc_id": loc_id},
            )
            conn.execute(
                sa.text("""
                    UPDATE asset_assignment_events
                    SET to_location_id = :target_id
                    WHERE to_location_id = :loc_id
                    """),
                {"target_id": target_id, "loc_id": loc_id},
            )
            conn.execute(
                sa.text("""
                    UPDATE locations
                    SET parent_id = CASE
                      WHEN id = :target_id THEN NULL
                      ELSE :target_id
                    END
                    WHERE parent_id = :loc_id
                    """),
                {"target_id": target_id, "loc_id": loc_id},
            )
            conn.execute(
                sa.text("""
                    UPDATE locations
                    SET is_active = false,
                        approval_status = 'rejected'
                    WHERE id = :loc_id
                    """),
                {"loc_id": loc_id},
            )
        else:
            conn.execute(
                sa.text("""
                    UPDATE locations
                    SET name = :new_name
                    WHERE id = :loc_id
                    """),
                {"new_name": new_name[:200], "loc_id": loc_id},
            )
            conn.execute(
                sa.text("""
                    UPDATE assets
                    SET site = :new_name
                    WHERE location_id = :loc_id
                      AND (site IS NULL OR site ILIKE 'plantexpand%')
                    """),
                {"new_name": new_name[:200], "loc_id": loc_id},
            )

    # Free-text site leftovers not linked (or already linked) that still carry the brand.
    conn.execute(sa.text("""
            UPDATE assets
            SET site = NULLIF(
              TRIM(BOTH ' ,-' FROM regexp_replace(
                site,
                '(?i)^((plantexpand(\\s+limited|\\s+ltd)?\\b|ltd\\b)[\\s,.-]*)+',
                '',
                'g'
              )),
              ''
            )
            WHERE site ILIKE 'plantexpand%'
            """))


def downgrade() -> None:
    # Non-destructive: renamed labels are kept.
    pass
