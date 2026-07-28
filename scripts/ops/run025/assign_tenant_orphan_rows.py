#!/usr/bin/env python3
"""Assign NULL-tenant case/action rows to a single tenant. **Staging only.**

The product owner's decision for staging is to bulk-assign every orphan to
staging's default tenant, because staging data carries no confidentiality weight
and this is the fastest route to a passing deploy. The decision for production is
deliberately different — those rows get deleted, see
``purge_tenant_orphan_rows`` — so this script must not become the tool that is
reached for on production by habit.

Why this refuses to run against production, even with ``--i-understand-prod``
----------------------------------------------------------------------------
Assigning a record to a tenant is a claim about who owns it. On staging that claim
is meaningless because the data is synthetic. On production it would attach one
client's road traffic collision to whichever tenant happened to be handy, which is
the precise failure ``20260901_case_tenant_nn`` exists to prevent. A flag that
lets an operator do it anyway is a flag that will eventually be used, so there
isn't one. Production remediation is a different script with a different decision
behind it.

Choosing the tenant
-------------------
Never hardcoded. The tenant is resolved from the data, and the script fails loudly
rather than picking:

* exactly one active tenant  -> that one is used;
* several active tenants     -> refuse unless ``--tenant-id`` names one explicitly;
* ``--tenant-id`` given      -> must exist and be active;
* ``DEFAULT_TENANT_ID`` set  -> must agree with the resolved tenant, or refuse.

The ``DEFAULT_TENANT_ID`` cross-check matters because #1386 declares that variable
for staging and production. If the environment and the database disagree about
which tenant is default, that disagreement is the finding — resolving it silently
in favour of either one would hide it.

Usage:
  env -u DATABASE_URL -u PRODDB -u STAGING_DB \\
    DATABASE_URL=postgresql+asyncpg://user@host/db \\
    python -m scripts.ops.run025.assign_tenant_orphan_rows --json
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any, Optional

import sqlalchemy as sa

from scripts.ops.run021._common import (
    add_safety_args,
    emit_report,
    enforce_apply_safety,
    looks_like_prod,
    open_session,
    require_database_url,
)
from scripts.ops.run025._models import migration_target_tables
from scripts.ops.run025.inventory_tenant_id_nulls import IDENTIFYING_COLUMNS, _reflect, _rls_blinded, dsn_label


class TenantAmbiguous(RuntimeError):
    """Raised when the target tenant cannot be established beyond doubt."""


async def resolve_tenant(db: Any, requested: Optional[int]) -> tuple[int, dict[str, Any]]:
    """Establish the tenant to assign to, or refuse."""
    rows = (await db.execute(sa.text("SELECT id, name, is_active FROM tenants ORDER BY id"))).mappings().all()
    tenants = [dict(row) for row in rows]
    active = [t for t in tenants if t["is_active"]]

    declared_raw = os.environ.get("DEFAULT_TENANT_ID")
    declared: Optional[int]
    try:
        declared = int(declared_raw) if declared_raw not in (None, "") else None
    except ValueError:
        raise TenantAmbiguous(f"DEFAULT_TENANT_ID={declared_raw!r} is not an integer; refusing to guess") from None

    if not tenants:
        raise TenantAmbiguous("this database has no tenants at all, so there is nothing to assign rows to")

    if requested is not None:
        match = next((t for t in tenants if t["id"] == requested), None)
        if match is None:
            raise TenantAmbiguous(f"--tenant-id {requested} does not exist in this database")
        if not match["is_active"]:
            raise TenantAmbiguous(
                f"--tenant-id {requested} ({match['name']!r}) is not active; refusing to assign to it"
            )
        chosen = requested
    elif len(active) == 1:
        chosen = active[0]["id"]
    elif not active:
        raise TenantAmbiguous(f"none of the {len(tenants)} tenants in this database are active")
    else:
        names = ", ".join(f"{t['id']}={t['name']!r}" for t in active)
        raise TenantAmbiguous(
            f"{len(active)} active tenants ({names}); which one owns these rows is a human decision. "
            "Re-run with --tenant-id to name it explicitly"
        )

    if declared is not None and declared != chosen:
        raise TenantAmbiguous(
            f"DEFAULT_TENANT_ID={declared} but this run resolved tenant {chosen}. The environment and "
            "the database disagree about which tenant is default; resolve that before assigning rows"
        )

    return chosen, {
        "tenants_in_database": tenants,
        "default_tenant_id_env": declared,
        "resolved_tenant_id": chosen,
        "resolution": "explicit --tenant-id" if requested is not None else "the only active tenant",
    }


async def plan(*, requested_tenant: Optional[int], limit: int) -> dict[str, Any]:
    """Report what would be reassigned. Read-only."""
    targets = list(migration_target_tables())
    blockers: list[str] = []

    async with await open_session() as db:
        reflected = await db.run_sync(_reflect, targets)
        blinded = await db.run_sync(_rls_blinded, targets)
        if blinded:
            blockers.append(
                "row-level security hides NULL-tenant rows from this role in "
                f"{', '.join(sorted(blinded))}; re-run as a role with rolsuper or rolbypassrls"
            )

        try:
            tenant_id, tenant_detail = await resolve_tenant(db, requested_tenant)
        except TenantAmbiguous as exc:
            tenant_id, tenant_detail = None, {"error": str(exc)}
            blockers.append(str(exc))

        per_table: dict[str, int] = {}
        samples: list[dict[str, Any]] = []
        for table in targets:
            info = reflected[table]
            if not info.get("exists") or not info.get("has_tenant_id"):
                continue
            count = (
                await db.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NULL"))  # noqa: S608
            ).scalar()
            if not count:
                continue
            per_table[table] = int(count)
            projected = ["id"] + [c for c in IDENTIFYING_COLUMNS if c in info["columns"]]
            rows = (
                (
                    await db.execute(
                        sa.text(  # noqa: S608
                            f"SELECT {', '.join(projected)} FROM {table} WHERE tenant_id IS NULL "
                            "ORDER BY id LIMIT :row_limit"
                        ),
                        {"row_limit": max(1, limit)},
                    )
                )
                .mappings()
                .all()
            )
            samples.extend({"table": table, **{key: row[key] for key in projected}} for row in rows)

    return {
        "database": dsn_label(require_database_url()),
        "target_tables": targets,
        "rows_to_assign": sum(per_table.values()),
        "rows_per_table": dict(sorted(per_table.items())),
        "tenant": tenant_detail,
        "rows": samples,
        "tables_hidden_by_rls": sorted(blinded),
        "blockers": blockers,
        "_tenant_id": tenant_id,
        "_tables": sorted(per_table),
    }


async def apply_plan(tables: list[str], tenant_id: int) -> dict[str, int]:
    """Set ``tenant_id`` on every NULL-tenant row in one transaction."""
    updated: dict[str, int] = {}
    async with await open_session() as db:
        for table in tables:
            result = await db.execute(
                sa.text(f"UPDATE {table} SET tenant_id = :tenant_id WHERE tenant_id IS NULL"),  # noqa: S608
                {"tenant_id": tenant_id},
            )
            updated[table] = result.rowcount or 0
        await db.commit()
    return updated


async def _amain(args: argparse.Namespace) -> int:
    if looks_like_prod():
        print(
            "REFUSING: this script bulk-assigns records to a tenant, and the environment looks like "
            f"production (APP_ENV={os.environ.get('APP_ENV')!r} ENVIRONMENT={os.environ.get('ENVIRONMENT')!r}).\n"
            "Assigning a production record to a tenant that may not own it is the exact failure the "
            "20260901_case_tenant_nn migration exists to prevent, so there is no override flag.\n"
            "Production orphans are handled by scripts.ops.run025.purge_tenant_orphan_rows.",
            file=sys.stderr,
        )
        return 2

    mode = enforce_apply_safety(apply=args.apply, i_understand_prod=args.i_understand_prod)
    require_database_url()

    result = await plan(requested_tenant=args.tenant_id, limit=args.limit)
    tenant_id = result.pop("_tenant_id")
    tables = result.pop("_tables")
    payload: dict[str, Any] = {"script": "assign_tenant_orphan_rows", "mode": mode, **result}

    if result["blockers"]:
        payload["outcome"] = "refused"
        payload["note"] = "Nothing was written. Resolve every blocker above, then re-run the dry run."
        emit_report(payload, as_json=args.json)
        return 3

    if not tables:
        payload["outcome"] = "nothing-to-do"
        payload["note"] = "No NULL-tenant rows in the migration's target tables."
        emit_report(payload, as_json=args.json)
        return 0

    if not args.apply:
        payload["outcome"] = "dry-run"
        payload["note"] = (
            f"No writes performed. {result['rows_to_assign']} row(s) would be assigned to tenant "
            f"{tenant_id}. Review 'rows', then re-run with --apply."
        )
        emit_report(payload, as_json=args.json)
        return 1

    payload["updated"] = await apply_plan(tables, int(tenant_id))
    payload["outcome"] = "applied"
    payload["note"] = "Rows assigned. Re-run inventory_tenant_id_nulls to confirm zero orphans."
    emit_report(payload, as_json=args.json)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_safety_args(parser)
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
