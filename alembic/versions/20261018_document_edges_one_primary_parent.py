"""Doc Graph X-0b: one live primary implements parent per child.

Revision ID: 20261018_doc_one_primary
Revises: 20261017_capa_fra_ocr
Create Date: 2026-10-18

X-0 refuses a second primary ``implements`` parent in application code. Two
concurrent writers can still both pass that check and both commit, and legacy
rows written before the guard can already hold more than one live primary for
the same child. This revision is the constraint that can: a partial unique
index on ``(tenant_id, src_document_id)`` for live primary implements edges.

Pre-flight remediation
----------------------
``CREATE UNIQUE INDEX`` on colliding data fails mid-deploy with the offending
key and nothing else. Before building the index we demote every extra primary
in a colliding group to ``is_primary_parent = false``, keeping the lowest edge
id — the same deterministic pick the X-0 thread walk already uses among legacy
duplicates. Soft-delete is not used: demoting preserves the non-primary
``implements`` edge for operators to confirm or reject explicitly.

Why this is not CONCURRENTLY
----------------------------
Same trade as ``20260914_cs_notif_dedupe``: every other index in this repository
is built inside its migration transaction. Staging Doc Graph traffic is flag-off;
introducing the first non-atomic migration to shorten an unobservable lock is
the worse trade.
"""

from __future__ import annotations

import logging
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "20261018_doc_one_primary"
down_revision: Union[str, Sequence[str], None] = "20261017_capa_fra_ocr"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

logger = logging.getLogger("alembic.runtime.migration")

TABLE = "document_edges"
INDEX_NAME = "ux_document_edges_one_primary_parent"
PREDICATE = "is_primary_parent AND edge_type = 'implements' AND deleted_at IS NULL"

INDEX_DDL = f"CREATE UNIQUE INDEX {INDEX_NAME} ON {TABLE} " f"(tenant_id, src_document_id) WHERE {PREDICATE}"

DUPLICATE_GROUPS_SQL = f"""
SELECT tenant_id, src_document_id, COUNT(*) AS edge_count,
       array_agg(id ORDER BY id) AS edge_ids
FROM {TABLE}
WHERE is_primary_parent IS TRUE
  AND edge_type = 'implements'
  AND deleted_at IS NULL
GROUP BY tenant_id, src_document_id
HAVING COUNT(*) > 1
ORDER BY tenant_id, src_document_id
"""

DEMOTE_EXTRAS_SQL = f"""
WITH ranked AS (
    SELECT id,
           ROW_NUMBER() OVER (
               PARTITION BY tenant_id, src_document_id
               ORDER BY id ASC
           ) AS rn
    FROM {TABLE}
    WHERE is_primary_parent IS TRUE
      AND edge_type = 'implements'
      AND deleted_at IS NULL
)
UPDATE {TABLE} AS e
SET is_primary_parent = false,
    updated_at = now()
FROM ranked AS r
WHERE e.id = r.id
  AND r.rn > 1
RETURNING e.id, e.tenant_id, e.src_document_id
"""


def _is_postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _table_exists() -> bool:
    return sa.inspect(op.get_bind()).has_table(TABLE)


def _index_exists() -> bool:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        return bool(
            bind.execute(
                sa.text("SELECT 1 FROM pg_class WHERE relkind = 'i' AND relname = :name"),
                {"name": INDEX_NAME},
            ).fetchone()
        )
    if not _table_exists():
        return False
    return any(idx["name"] == INDEX_NAME for idx in sa.inspect(bind).get_indexes(TABLE))


def _demote_duplicate_primaries() -> int:
    """Keep lowest edge id as primary; demote the rest. Returns demoted row count.

    Matches the X-0 ancestor walk's deterministic ``ORDER BY id ASC`` pick among
    legacy duplicate primaries, so the surviving primary is the one thread walks
    already preferred.
    """
    bind = op.get_bind()
    if not _is_postgres():
        # SQLite (and other dialects) lack array_agg / the PG-shaped UPDATE…FROM
        # used below. Production is PostgreSQL; create_all carries the index for
        # the SQLite test harness. Refuse rather than silently skip remediation
        # if somehow run against non-empty non-PG data.
        duplicates = bind.execute(sa.text(f"""
                SELECT tenant_id, src_document_id, COUNT(*) AS edge_count
                FROM {TABLE}
                WHERE is_primary_parent IS TRUE
                  AND edge_type = 'implements'
                  AND deleted_at IS NULL
                GROUP BY tenant_id, src_document_id
                HAVING COUNT(*) > 1
                """)).fetchall()
        if duplicates:
            sample = ", ".join(f"tenant={r[0]} src={r[1]} (n={r[2]})" for r in duplicates[:10])
            raise RuntimeError(
                f"{revision}: refusing to create {INDEX_NAME} on non-PostgreSQL with "
                f"{len(duplicates)} duplicate primary group(s) — {sample}. "
                "Demote extras (keep lowest edge id) before re-running."
            )
        return 0

    groups = bind.execute(sa.text(DUPLICATE_GROUPS_SQL)).mappings().fetchall()
    if not groups:
        logger.info("%s: no duplicate primary implements parents — nothing to demote", revision)
        return 0

    sample = ", ".join(
        f"tenant={g['tenant_id']} src={g['src_document_id']} ids={list(g['edge_ids'])}" for g in groups[:10]
    )
    logger.warning(
        "%s: demoting extras in %s duplicate primary group(s) (keep lowest id) — %s%s",
        revision,
        len(groups),
        sample,
        " …" if len(groups) > 10 else "",
    )
    demoted = bind.execute(sa.text(DEMOTE_EXTRAS_SQL)).mappings().fetchall()
    logger.info(
        "%s: demoted %s extra primary edge(s) to is_primary_parent=false",
        revision,
        len(demoted),
    )
    return len(demoted)


def _assert_index_matches() -> None:
    """Re-read pg_index and raise unless the index really has both parts."""
    row = (
        op.get_bind()
        .execute(
            sa.text("""
                SELECT i.indisunique AS is_unique,
                       i.indisvalid  AS is_valid,
                       pg_get_expr(i.indpred, i.indrelid) AS predicate,
                       pg_get_indexdef(i.indexrelid)      AS definition
                FROM pg_index AS i
                JOIN pg_class AS c ON c.oid = i.indexrelid
                WHERE c.relname = :name
                """),
            {"name": INDEX_NAME},
        )
        .mappings()
        .fetchone()
    )

    problems: list[str] = []
    if row is None:
        problems.append("index is absent from pg_index")
    else:
        if not row["is_unique"]:
            problems.append("index is not UNIQUE, so it constrains nothing")
        if not row["is_valid"]:
            problems.append("index is INVALID and will not be used or enforced")
        predicate = row["predicate"]
        if predicate is None:
            problems.append(
                "index has no partial predicate: it would apply to every row in "
                "the table rather than live primary implements edges only"
            )
        else:
            for fragment in ("is_primary_parent", "implements", "deleted_at"):
                if fragment not in predicate:
                    problems.append(f"predicate is {predicate!r}, expected it to contain {fragment!r}")
        definition = row["definition"] or ""
        if "tenant_id" not in definition or "src_document_id" not in definition:
            problems.append(f"definition is {definition!r}, expected columns (tenant_id, src_document_id)")

    if problems:
        raise RuntimeError(
            f"{revision} did not achieve the index state it reported. "
            "Refusing to record this revision as applied.\n  " + "\n  ".join(problems)
        )


def upgrade() -> None:
    if not _table_exists():
        logger.info("%s: %s absent — nothing to do", revision, TABLE)
        return

    if _is_postgres():
        if _index_exists():
            logger.info("%s: %s already present — verifying rather than recreating", revision, INDEX_NAME)
            _assert_index_matches()
            return

        _demote_duplicate_primaries()
        op.execute(sa.text(INDEX_DDL))
        _assert_index_matches()
        logger.info("%s: created %s", revision, INDEX_NAME)
        return

    # SQLite harness: index comes from the ORM declaration via create_all.
    # Still refuse if colliding rows somehow exist so a local alembic upgrade
    # cannot claim success while leaving data the unique index would reject.
    _demote_duplicate_primaries()
    if not _index_exists():
        op.create_index(
            INDEX_NAME,
            TABLE,
            ["tenant_id", "src_document_id"],
            unique=True,
            sqlite_where=sa.text(PREDICATE),
        )
        logger.info("%s: created %s (sqlite)", revision, INDEX_NAME)


def downgrade() -> None:
    if not _table_exists():
        return
    if _is_postgres():
        op.execute(sa.text(f"DROP INDEX IF EXISTS {INDEX_NAME}"))
        return
    if _index_exists():
        op.drop_index(INDEX_NAME, table_name=TABLE)
