#!/usr/bin/env python3
"""Backfill ``tenant_id`` on NULL-tenant rows **outside** the #1398 case/action scope.

Production holds tenant-less rows in tables the ``20260901_case_tenant_nn``
migration does not touch — audit runs, audit findings, risks and the external-audit
import tables. Reads are fail-closed on an exact tenant match, so those rows are
invisible to the only tenant that exists. The product owner's decision is to
attribute them rather than delete them, because unlike the three E2E incidents that
were purged, this is real audit history.

Why this is a separate script and not a flag on ``assign_tenant_orphan_rows``
----------------------------------------------------------------------------
``assign_tenant_orphan_rows`` refuses production outright and deliberately has no
override, because assigning a *case* to a tenant is a confidentiality claim. Adding
a bypass flag there would eventually be used by habit, so that refusal stays
absolute and flagless.

Splitting the work also buys a structural guarantee that a mode flag could not: the
two scripts operate on **disjoint** table sets. ``assign`` can only ever touch the
ten tables named by the migration, and only off production. This script can only
ever touch tables *not* named by the migration — ``backfill_scope`` subtracts them,
and ``_assert_disjoint`` fails the run if that ever stops being true. Neither script
can be pointed at the other's tables, whatever flags are passed.

Why a blanket default is permitted here at all
----------------------------------------------
The migrations' fail-safes exist to stop ``tenant_id = 1`` being invented when the
answer is unknown. The decision here rests on a narrower claim: production has
exactly **one** active tenant, so there is no second candidate that could be
wronged. That claim is a fact about the database, not a policy, so it is enforced as
a runtime precondition rather than trusted:

* exactly one active tenant  -> that tenant is the default;
* anything else              -> the default is unavailable and the run refuses.

There is no ``--tenant-id`` override. The moment this database has two active
tenants, the justification for the blanket default evaporates, and the script must
stop rather than let an operator re-supply the reasoning from memory. Rows that can
be attributed from evidence are unaffected by that precondition.

Provenance before default
-------------------------
Following ``20260720_ea_tenant_nn``, attribution is inherited where possible and
defaulted only where it is not. ``PROVENANCE_RULES`` declares, per table, which
relationships actually imply ownership, in priority order. They are declared rather
than derived from the foreign-key graph because "a finding belongs to its run" is
domain knowledge; ``audit_runs.asset_id`` is a foreign key too, but an asset does
not own the audit performed against it.

Inheritance sources are restricted to parents that already held a ``tenant_id``
before this run. A parent that is itself about to be defaulted is not evidence, so
a child pointing at it is reported as defaulted too. That keeps the
inherited-versus-defaulted split in the report honest instead of laundering the
default one hop through a parent row.

Refusals
--------
* **RLS blindness** — a role without ``rolsuper``/``rolbypassrls`` sees no rows in a
  FORCE RLS table, so its zero is meaningless.
* **Non-historical orphans** — if a table's newest orphan is recent, the write path
  is still producing them and backfilling would mask a live defect. Checked per
  table, not assumed from the two import tables that were verified by hand.
* **Unprovable age** — a table with orphans but no ``created_at`` cannot be shown to
  be historical, so it is refused rather than assumed.
* **Undeclared provenance** — a table with orphans and no rule in
  ``PROVENANCE_RULES`` would go straight to the default without anyone having looked
  for a parent. That is refused; the fix is a reviewed addition to the rules.
* **Row set drift** — ``--apply`` writes exactly the rows in the manifest, by primary
  key, and rolls back if any of them stopped being NULL since the dry run.

Usage:
  env -u DATABASE_URL -u PRODDB -u STAGING_DB \\
    DATABASE_URL=postgresql+asyncpg://user@host/db \\
    python -m scripts.ops.run025.backfill_tenant_orphan_rows \\
      --manifest /tmp/tenant-backfill-manifest.json --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import sqlalchemy as sa

from scripts.ops.run021._common import (
    add_safety_args,
    emit_report,
    enforce_apply_safety,
    is_protected_ci_smoke_email,
    matches_test_token,
    open_session,
    require_database_url,
    truncate,
    utc_now_iso,
)
from scripts.ops.run025._models import migration_target_tables, tenant_required_tables

# resolve_tenant is reused rather than reimplemented so there is one place that
# cross-checks DEFAULT_TENANT_ID against the database. It is always called with
# requested=None, which is what makes multiple active tenants a refusal here.
from scripts.ops.run025.assign_tenant_orphan_rows import TenantAmbiguous, resolve_tenant
from scripts.ops.run025.inventory_tenant_id_nulls import _reflect, _rls_blinded, dsn_label

# An orphan newer than this is treated as evidence of a live write-path defect.
DEFAULT_MAX_ORPHAN_AGE_DAYS = 30

# Text columns worth scanning for UAT/CUJ/smoke markers. Restricted to name- and
# title-like columns: scanning every string would match unrelated free text.
DEBRIS_TEXT_COLUMNS: tuple[str, ...] = (
    "title",
    "reference",
    "reference_number",
    "source_filename",
    "provider_name",
    "issuer_name",
    "organization_name",
    "auditor_name",
    "external_body_name",
    "external_auditor_name",
    "suggested_action_title",
    "suggested_risk_title",
)


@dataclass(frozen=True)
class AttributionRule:
    """A relationship asserted to imply tenant ownership."""

    fk_column: str
    parent_table: str
    why: str


# Declared in priority order, strongest claim first. Deliberately narrow: a rule
# here is a statement that the parent's tenant *owns* the child.
PROVENANCE_RULES: dict[str, tuple[AttributionRule, ...]] = {
    "audit_findings": (
        AttributionRule("run_id", "audit_runs", "a finding is raised within one audit run"),
        AttributionRule("created_by_id", "users", "the user who raised the finding"),
    ),
    "audit_runs": (
        AttributionRule("template_id", "audit_templates", "a run is an instance of one tenant's template"),
        AttributionRule("created_by_id", "users", "the user who started the run"),
        AttributionRule("assigned_to_id", "users", "the user the run was assigned to"),
    ),
    "external_audit_import_jobs": (
        AttributionRule("audit_run_id", "audit_runs", "the run this import populates"),
        AttributionRule("created_by_id", "users", "the user who started the import"),
    ),
    "external_audit_import_drafts": (
        AttributionRule("import_job_id", "external_audit_import_jobs", "a draft belongs to one import job"),
        AttributionRule("audit_run_id", "audit_runs", "the run the draft targets"),
        AttributionRule("promoted_finding_id", "audit_findings", "the finding this draft became"),
        AttributionRule("created_by_id", "users", "the user who created the draft"),
    ),
    "risks_v2": (
        # Note the column is created_by, not created_by_id, unlike every other
        # table here. A generic created_by_id sweep would silently miss this table.
        AttributionRule("created_by", "users", "the user who registered the risk"),
        AttributionRule("risk_owner_id", "users", "the accountable risk owner"),
    ),
}


class RowSetDrifted(RuntimeError):
    """Raised when the rows to update no longer match the reviewed manifest."""


def backfill_scope() -> tuple[str, ...]:
    """Tenant-required tables that ``20260901_case_tenant_nn`` does *not* cover."""
    in_migration = set(migration_target_tables())
    scope = tuple(table for table in tenant_required_tables() if table not in in_migration)
    _assert_disjoint(scope)
    return scope


def _assert_disjoint(scope: tuple[str, ...]) -> None:
    """Fail loudly if this script could ever touch a case/action table."""
    overlap = sorted(set(scope).intersection(migration_target_tables()))
    if overlap:
        raise RuntimeError(
            f"refusing to run: {', '.join(overlap)} are in the case/action migration scope, "
            "which this script must never write to (see assign_tenant_orphan_rows)"
        )


def _primary_keys(sync_session: Any, tables: list[str]) -> dict[str, Optional[str]]:
    """Single-column primary key per table, or None when there isn't one.

    Rows are updated by primary key so that ``--apply`` writes exactly what the
    manifest recorded. A table without an addressable single-column key cannot be
    handled that way, so it is reported rather than swept with a blanket UPDATE.
    """
    inspector = sa.inspect(sync_session.get_bind())
    present = set(inspector.get_table_names())
    keys: dict[str, Optional[str]] = {}
    for table in tables:
        if table not in present:
            keys[table] = None
            continue
        columns = inspector.get_pk_constraint(table).get("constrained_columns") or []
        keys[table] = columns[0] if len(columns) == 1 else None
    return keys


def _parent_tables() -> list[str]:
    return sorted({rule.parent_table for rules in PROVENANCE_RULES.values() for rule in rules})


async def _orphan_rows(db: Any, table: str, pk: str) -> list[dict[str, Any]]:
    """Every column of every NULL-tenant row, for the manifest."""
    # Table and key names come from SQLAlchemy metadata and the rules above,
    # never from argv.
    rows = (
        await db.execute(sa.text(f"SELECT * FROM {table} WHERE tenant_id IS NULL ORDER BY {pk}"))  # noqa: S608
    ).mappings()
    return [dict(row) for row in rows]


async def _attribute(
    db: Any,
    *,
    table: str,
    pk: str,
    rules: tuple[AttributionRule, ...],
    columns: set[str],
    parent_keys: dict[str, Optional[str]],
) -> tuple[dict[Any, dict[str, Any]], list[str]]:
    """Resolve tenant from parents that *already* hold one. First rule wins."""
    resolved: dict[Any, dict[str, Any]] = {}
    skipped: list[str] = []

    for rule in rules:
        if rule.fk_column not in columns:
            skipped.append(f"{table}.{rule.fk_column} is not a column in this database")
            continue
        parent_pk = parent_keys.get(rule.parent_table)
        if parent_pk is None:
            skipped.append(f"{rule.parent_table} is absent or has no single-column primary key")
            continue

        found = (
            await db.execute(
                sa.text(  # noqa: S608
                    f"SELECT child.{pk} AS child_pk, parent.tenant_id AS tenant_id "
                    f"FROM {table} AS child "
                    f"JOIN {rule.parent_table} AS parent ON parent.{parent_pk} = child.{rule.fk_column} "
                    "WHERE child.tenant_id IS NULL AND parent.tenant_id IS NOT NULL"
                )
            )
        ).all()
        for child_pk, tenant_id in found:
            if child_pk in resolved:
                continue
            resolved[child_pk] = {
                "tenant_id": int(tenant_id),
                "attribution": "inherited",
                "source": f"{rule.parent_table}.tenant_id via {table}.{rule.fk_column}",
                "why": rule.why,
            }
    return resolved, skipped


async def _orphans_under_orphan_parent(
    db: Any, *, table: str, rule: AttributionRule, columns: set[str], parent_keys: dict[str, Optional[str]]
) -> Optional[int]:
    """Orphans whose strongest parent is itself an orphan.

    Not a rule and not a blocker: it is evidence about shape. A large count says
    the orphans form coherent groups written by one broken run, rather than being
    scattered rows that each lost their tenant independently.
    """
    if rule.fk_column not in columns:
        return None
    parent_pk = parent_keys.get(rule.parent_table)
    if parent_pk is None:
        return None
    return int(
        (
            await db.execute(
                sa.text(  # noqa: S608
                    f"SELECT COUNT(*) FROM {table} AS child "
                    f"JOIN {rule.parent_table} AS parent ON parent.{parent_pk} = child.{rule.fk_column} "
                    "WHERE child.tenant_id IS NULL AND parent.tenant_id IS NULL"
                )
            )
        ).scalar()
        or 0
    )


async def _age_evidence(db: Any, *, table: str, columns: set[str]) -> dict[str, Any]:
    """Whether a table's orphans are historical, with the dates behind the verdict."""
    if "created_at" not in columns:
        return {"created_at_available": False}

    oldest, newest = (
        await db.execute(
            sa.text(f"SELECT MIN(created_at), MAX(created_at) FROM {table} WHERE tenant_id IS NULL")  # noqa: S608
        )
    ).one()
    attributed_newest = (
        await db.execute(sa.text(f"SELECT MAX(created_at) FROM {table} WHERE tenant_id IS NOT NULL"))  # noqa: S608
    ).scalar()
    attributed_after = (
        await db.execute(
            sa.text(  # noqa: S608
                f"SELECT COUNT(*) FROM {table} " "WHERE tenant_id IS NOT NULL AND created_at > :newest_orphan"
            ),
            {"newest_orphan": newest},
        )
    ).scalar()

    return {
        "created_at_available": True,
        "oldest_orphan": oldest,
        "newest_orphan": newest,
        "newest_attributed_row": attributed_newest,
        # The write path is demonstrably fixed if plenty of rows written after the
        # last orphan all carry a tenant. This is the check done by hand for the
        # import tables, computed for every table instead.
        "attributed_rows_written_after_newest_orphan": int(attributed_after or 0),
    }


def _debris_signals(
    rows: list[dict[str, Any]],
    creators: dict[Any, dict[str, Any]],
    creator_column: Optional[str],
    pk: str,
) -> dict[str, Any]:
    """Count orphans that look like test debris rather than business records.

    Reported, never a blocker. Whether synthetic rows should be attributed or
    deleted is the same judgement that was made for the three E2E incidents, and it
    belongs to the product owner — but it cannot be made without seeing this.
    """
    token_hits: list[Any] = []
    smoke_created: list[Any] = []
    inactive_creator: list[Any] = []

    for row in rows:
        text_values = [row.get(column) for column in DEBRIS_TEXT_COLUMNS if isinstance(row.get(column), str)]
        if matches_test_token(*text_values):
            token_hits.append(row.get(pk))
        if creator_column is None:
            continue
        creator = creators.get(row.get(creator_column))
        if creator is None:
            continue
        if is_protected_ci_smoke_email(creator.get("email")):
            smoke_created.append(row.get(pk))
        elif not creator.get("is_active"):
            inactive_creator.append(row.get(pk))

    return {
        "rows_matching_test_tokens": len(token_hits),
        "rows_created_by_ci_smoke_account": len(smoke_created),
        "rows_created_by_deactivated_user": len(inactive_creator),
        "example_test_token_ids": token_hits[:10],
    }


async def _creators(db: Any, *, table: str, column: str) -> dict[Any, dict[str, Any]]:
    rows = (
        await db.execute(
            sa.text(  # noqa: S608
                "SELECT u.id, u.email, u.is_active, u.tenant_id FROM users AS u "
                f"WHERE u.id IN (SELECT {column} FROM {table} WHERE tenant_id IS NULL AND {column} IS NOT NULL)"
            )
        )
    ).mappings()
    return {row["id"]: dict(row) for row in rows}


def _creator_column(rules: tuple[AttributionRule, ...]) -> Optional[str]:
    return next((rule.fk_column for rule in rules if rule.parent_table == "users"), None)


async def plan(*, limit: int, max_orphan_age_days: int) -> dict[str, Any]:
    """Work out what would be written, and whether it may be. Read-only."""
    scope = list(backfill_scope())
    blockers: list[str] = []
    cutoff = datetime.now(timezone.utc) - timedelta(days=max_orphan_age_days)

    async with await open_session() as db:
        reflected = await db.run_sync(_reflect, scope)
        blinded = await db.run_sync(_rls_blinded, scope)
        parent_keys = await db.run_sync(_primary_keys, _parent_tables())
        pks = await db.run_sync(_primary_keys, scope)

        if blinded:
            blockers.append(
                "row-level security hides NULL-tenant rows from this role in "
                f"{', '.join(sorted(blinded))}; re-run as a role with rolsuper or rolbypassrls"
            )

        default_tenant: Optional[int]
        try:
            default_tenant, tenant_detail = await resolve_tenant(db, None)
        except TenantAmbiguous as exc:
            default_tenant, tenant_detail = None, {"error": str(exc)}

        per_table: list[dict[str, Any]] = []
        assignments: dict[str, list[dict[str, Any]]] = {}
        manifest_rows: dict[str, list[dict[str, Any]]] = {}
        not_countable: list[str] = []
        needs_default_total = 0

        for table in scope:
            info = reflected[table]
            if not info.get("exists"):
                not_countable.append(f"{table} (not present in this database)")
                continue
            if not info.get("has_tenant_id"):
                not_countable.append(f"{table} (no tenant_id column — ADD COLUMN drift, tracked as C-9)")
                continue
            if table in blinded:
                continue

            pk = pks.get(table)
            if pk is None:
                count = (
                    await db.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NULL"))  # noqa: S608
                ).scalar()
                if count:
                    blockers.append(
                        f"{table} holds {count} orphan(s) but has no single-column primary key, so rows "
                        "cannot be updated individually against a reviewed manifest"
                    )
                continue

            rows = await _orphan_rows(db, table, pk)
            if not rows:
                continue

            columns = set(info["columns"])
            rules = PROVENANCE_RULES.get(table, ())
            if not rules:
                blockers.append(
                    f"{table} holds {len(rows)} orphan(s) but has no PROVENANCE_RULES entry, so every row "
                    "would take the blanket default without anyone having looked for a parent. Add a "
                    "reviewed rule (or record that none applies) before backfilling this table"
                )
                continue

            resolved, skipped = await _attribute(
                db, table=table, pk=pk, rules=rules, columns=columns, parent_keys=parent_keys
            )
            age = await _age_evidence(db, table=table, columns=columns)
            cohesion = await _orphans_under_orphan_parent(
                db, table=table, rule=rules[0], columns=columns, parent_keys=parent_keys
            )

            if not age["created_at_available"]:
                blockers.append(
                    f"{table} holds {len(rows)} orphan(s) and has no created_at column, so they cannot be "
                    "shown to be historical rather than a live write-path defect"
                )
                continue
            newest = age["newest_orphan"]
            if isinstance(newest, datetime):
                naive_cutoff = cutoff if newest.tzinfo else cutoff.replace(tzinfo=None)
                if newest >= naive_cutoff:
                    blockers.append(
                        f"{table}'s newest orphan was created {newest.isoformat()}, within the last "
                        f"{max_orphan_age_days} day(s). Recent orphans mean the write path is still "
                        "producing them; backfilling would mask a live defect. Fix the writer first"
                    )
                    continue

            creator_column = _creator_column(rules)
            creators = (
                await _creators(db, table=table, column=creator_column)
                if creator_column and creator_column in columns
                else {}
            )

            table_rows: list[dict[str, Any]] = []
            needs_default = 0
            for row in rows:
                key = row[pk]
                decided = resolved.get(key)
                if decided is None:
                    if default_tenant is None:
                        needs_default += 1
                        continue
                    decided = {
                        "tenant_id": int(default_tenant),
                        "attribution": "default",
                        "source": "the only active tenant in this database",
                        "why": "no parent row or creating user held a tenant_id",
                    }
                table_rows.append({"pk": key, **decided, "row": row})
            needs_default_total += needs_default

            inherited = sum(1 for entry in table_rows if entry["attribution"] == "inherited")
            defaulted = sum(1 for entry in table_rows if entry["attribution"] == "default")
            per_table.append(
                {
                    "table": table,
                    "orphans": len(rows),
                    "would_inherit": inherited,
                    "would_take_default": defaulted,
                    "inheritance_sources": sorted(
                        {entry["source"] for entry in table_rows if entry["attribution"] == "inherited"}
                    ),
                    "rules_skipped": skipped,
                    "orphans_whose_strongest_parent_is_also_an_orphan": cohesion,
                    "debris_signals": _debris_signals(rows, creators, creator_column, pk),
                    **{key: value for key, value in age.items() if key != "created_at_available"},
                }
            )
            if table_rows:
                assignments[table] = [{"pk": entry["pk"], "tenant_id": entry["tenant_id"]} for entry in table_rows]
                manifest_rows[table] = table_rows

        if needs_default_total:
            blockers.append(
                f"{needs_default_total} row(s) have no inheritable tenant and the blanket default is "
                f"unavailable: {tenant_detail.get('error', 'no single active tenant')} "
                "(disregard that message's suggestion of --tenant-id; this script does not accept it). "
                "The default is only defensible while exactly one tenant could possibly own these rows. "
                "Assigning them now would be inventing attribution, which is what the migration "
                "fail-safes exist to prevent"
            )

    return {
        "database": dsn_label(require_database_url()),
        "tables_in_scope": len(scope),
        "excluded_case_action_tables": sorted(migration_target_tables()),
        "rows_to_backfill": sum(len(rows) for rows in assignments.values()),
        "rows_inherited": sum(
            1 for rows in manifest_rows.values() for entry in rows if entry["attribution"] == "inherited"
        ),
        "rows_defaulted": sum(
            1 for rows in manifest_rows.values() for entry in rows if entry["attribution"] == "default"
        ),
        "tenant": tenant_detail,
        "per_table": per_table,
        "tables_hidden_by_rls": sorted(blinded),
        "tables_not_countable": not_countable,
        "sample": truncate(
            [
                {
                    "table": table,
                    "pk": entry["pk"],
                    "tenant_id": entry["tenant_id"],
                    "attribution": entry["attribution"],
                }
                for table, rows in sorted(manifest_rows.items())
                for entry in rows
            ],
            limit,
        ),
        "blockers": blockers,
        "_assignments": assignments,
        "_manifest_rows": manifest_rows,
        "_pks": pks,
    }


async def apply_plan(assignments: dict[str, list[dict[str, Any]]], pks: dict[str, Optional[str]]) -> dict[str, int]:
    """Write exactly the reviewed rows, by primary key, in one transaction.

    A blanket ``WHERE tenant_id IS NULL`` would also catch anything written between
    the dry run and the apply, which is precisely what the manifest is supposed to
    rule out. So the planned keys are locked, checked against the plan, and only
    then updated; any divergence rolls the whole thing back.
    """
    updated: dict[str, int] = {}
    async with await open_session() as db:
        dialect = await db.run_sync(lambda session: session.get_bind().dialect.name)
        # Lock the planned rows so nothing can change them between the check below
        # and the UPDATE. SQLite has no row locks and rejects the clause.
        lock = " FOR UPDATE" if dialect == "postgresql" else ""

        drifted: dict[str, list[Any]] = {}
        for table, rows in sorted(assignments.items()):
            pk = pks[table]
            planned = [row["pk"] for row in rows]
            statement = sa.text(  # noqa: S608
                f"SELECT {pk} FROM {table} WHERE tenant_id IS NULL AND {pk} IN :planned{lock}"
            ).bindparams(sa.bindparam("planned", expanding=True))
            still_null = set((await db.execute(statement, {"planned": planned})).scalars().all())
            missing = [key for key in planned if key not in still_null]
            if missing:
                drifted[table] = missing

        if drifted:
            await db.rollback()
            raise RowSetDrifted(
                "these rows are no longer NULL-tenant, so the manifest no longer describes the "
                f"database: {json.dumps(drifted, default=str)}. Re-run the dry run"
            )

        for table, rows in sorted(assignments.items()):
            pk = pks[table]
            by_tenant: dict[int, list[Any]] = defaultdict(list)
            for row in rows:
                by_tenant[int(row["tenant_id"])].append(row["pk"])
            written = 0
            for tenant_id, keys in sorted(by_tenant.items()):
                statement = sa.text(  # noqa: S608
                    f"UPDATE {table} SET tenant_id = :tenant_id WHERE tenant_id IS NULL AND {pk} IN :keys"
                ).bindparams(sa.bindparam("keys", expanding=True))
                result = await db.execute(statement, {"tenant_id": tenant_id, "keys": keys})
                written += result.rowcount or 0
            if written != len(rows):
                await db.rollback()
                raise RowSetDrifted(f"{table}: updated {written} row(s) but planned {len(rows)}; rolled back")
            updated[table] = written

        await db.commit()
    return updated


def _write_manifest(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")


async def _amain(args: argparse.Namespace) -> int:
    if args.tenant_id is not None:
        print(
            "REFUSING: --tenant-id is not accepted here. The blanket default is only defensible "
            "because production has exactly one active tenant, so it is derived from the database "
            "and the run refuses when that stops being true. Naming a tenant by hand would put back "
            "the guess the migration fail-safes exist to prevent.",
            file=sys.stderr,
        )
        return 2

    mode = enforce_apply_safety(apply=args.apply, i_understand_prod=args.i_understand_prod)
    require_database_url()

    result = await plan(limit=args.limit, max_orphan_age_days=args.max_orphan_age_days)
    assignments = result.pop("_assignments")
    manifest_rows = result.pop("_manifest_rows")
    pks = result.pop("_pks")
    payload: dict[str, Any] = {"script": "backfill_tenant_orphan_rows", "mode": mode, **result}

    if args.manifest:
        _write_manifest(
            Path(args.manifest),
            {
                "script": "backfill_tenant_orphan_rows",
                "mode": mode,
                "database": result["database"],
                "captured_at": utc_now_iso(),
                "per_table": result["per_table"],
                "tenant": result["tenant"],
                "rows": manifest_rows,
                "blockers": result["blockers"],
                "note": (
                    "Full contents of every row proposed for backfill, with the tenant it would "
                    "receive and whether that came from a parent row or the single-tenant default, "
                    "captured before any write. These rows belong to no tenant, so the change cannot "
                    "be recorded in the per-tenant hash-chained audit_log_entries without inventing "
                    "the very attribution under review. Attach this file to the change record."
                ),
            },
        )
        payload["manifest_written_to"] = str(args.manifest)

    if result["blockers"]:
        payload["outcome"] = "refused"
        payload["note"] = "Nothing was written. Resolve every blocker above, then re-run the dry run."
        emit_report(payload, as_json=args.json)
        return 3

    if not assignments:
        payload["outcome"] = "nothing-to-do"
        payload["note"] = "No NULL-tenant rows outside the case/action migration scope."
        emit_report(payload, as_json=args.json)
        return 0

    if not args.apply:
        payload["outcome"] = "dry-run"
        payload["note"] = (
            f"No writes performed. {result['rows_to_backfill']} row(s) would be attributed "
            f"({result['rows_inherited']} inherited from a parent, {result['rows_defaulted']} from the "
            "single-tenant default). Review 'per_table' — especially debris_signals — keep the manifest "
            "with the change record, then re-run with --apply (plus --i-understand-prod on production)."
        )
        emit_report(payload, as_json=args.json)
        return 1

    if not args.manifest:
        payload["outcome"] = "refused"
        payload["note"] = "--apply requires --manifest: an unrecorded rewrite of audited rows is not acceptable."
        emit_report(payload, as_json=args.json)
        return 2

    try:
        payload["updated"] = await apply_plan(assignments, pks)
    except RowSetDrifted as exc:
        payload["outcome"] = "refused"
        payload["note"] = f"Rolled back, nothing written: {exc}"
        emit_report(payload, as_json=args.json)
        return 3

    payload["outcome"] = "applied"
    payload["note"] = (
        "Rows attributed. Re-run inventory_tenant_id_nulls to confirm, and note the nine "
        "still-nullable columns remain a schema question (C-9), not a data one."
    )
    emit_report(payload, as_json=args.json)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_safety_args(parser)
    parser.add_argument(
        "--manifest",
        default=None,
        help="Path to write the full pre-backfill row contents. Required with --apply.",
    )
    parser.add_argument(
        "--max-orphan-age-days",
        type=int,
        default=DEFAULT_MAX_ORPHAN_AGE_DAYS,
        dest="max_orphan_age_days",
        help=(
            "Refuse any table whose newest orphan is younger than this, on the basis that recent "
            f"orphans indicate a live write-path defect (default {DEFAULT_MAX_ORPHAN_AGE_DAYS})."
        ),
    )
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
