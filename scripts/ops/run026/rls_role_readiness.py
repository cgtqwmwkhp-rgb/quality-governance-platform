#!/usr/bin/env python3
"""Decide whether this database is ready for the app to stop bypassing RLS (C-27).

Read-only. ``--apply`` is rejected outright: there is no mutation here, and the
cutover itself is a human step in the runbook, not something a script should do.

The problem this exists to prevent
----------------------------------
The application connects as a role holding ``rolbypassrls``, so PostgreSQL skips
row-level security for it and every ``tenant_isolation`` policy on the estate is
currently inert. The instant the connection role changes, all of those policies
begin enforcing at once, for the first time ever. Three separate things can turn
that into an outage, and all three are invisible from the application side today:

1. **Rows the policies do not match become invisible.** A NULL ``tenant_id`` can
   never satisfy ``tenant_id = <tenant>``, so any such row disappears from the
   application. Only the tables that actually carry a policy matter here — a
   tenant-less row in a table with no RLS is unaffected, which is why this script
   counts NULLs *per policy table* rather than across the whole schema.
2. **The predicate can fail loud instead of closed.** See
   ``TENANT_ISOLATION_PREDICATE``: a policy reading
   ``current_setting(...)::int`` without a ``NULLIF`` guard raises 22P02 on any
   pooled connection that has already served one tenant-scoped request, because
   the transaction-local GUC reverts to the empty string rather than to unset.
3. **The app role may not be able to read the row it needs to learn the tenant.**
   Authentication looks a user up by email, and ``users`` is under FORCE RLS. With
   no tenant bound yet there is nothing to bind, so the lookup matches nothing and
   nobody can log in. This is a code-shape problem, not a data problem, and no
   amount of backfilling fixes it.

Exit status is 0 only when every gate passes. Anything else exits 1, so this can
gate a runbook step.

Usage:
  env -u DATABASE_URL -u PRODDB -u STAGING_DB \\
    DATABASE_URL=postgresql+asyncpg://admin@host/db \\
    python -m scripts.ops.run026.rls_role_readiness --json
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any, Optional

import sqlalchemy as sa

from scripts.ops.run021._common import (
    add_safety_args,
    emit_report,
    enforce_apply_safety,
    open_session,
    require_database_url,
)
from scripts.ops.run025.inventory_tenant_id_nulls import dsn_label
from src.infrastructure.middleware.tenant_context import RLS_TABLES, TENANT_GUC, TENANT_ISOLATION_PREDICATE

DEFAULT_CANDIDATE_ROLE = "qgp_app"

# Privileges the request path needs on every table it touches.
REQUIRED_TABLE_PRIVILEGES: tuple[str, ...] = ("SELECT", "INSERT", "UPDATE", "DELETE")

# Role attributes that would make the whole exercise pointless if the candidate
# held them. rolsuper implies RLS bypass even without rolbypassrls.
DISQUALIFYING_ATTRIBUTES: tuple[str, ...] = (
    "rolsuper",
    "rolbypassrls",
    "rolcreatedb",
    "rolcreaterole",
    "rolreplication",
)

# The marker that distinguishes an empty-GUC-safe predicate from the legacy one.
EMPTY_GUC_GUARD_MARKER = "NULLIF"


async def _connection_identity(db: Any) -> dict[str, Any]:
    """Who are we, and can we be trusted to see every row?"""
    row = (
        (
            await db.execute(
                sa.text(
                    "SELECT current_user AS role, current_database() AS database, "
                    "       r.rolsuper, r.rolbypassrls "
                    "FROM pg_roles AS r WHERE r.rolname = current_user"
                )
            )
        )
        .mappings()
        .first()
    )
    bypasses = bool(row and (row["rolsuper"] or row["rolbypassrls"]))
    return {
        "role": row["role"] if row else None,
        "database": row["database"] if row else None,
        "rolsuper": bool(row["rolsuper"]) if row else None,
        "rolbypassrls": bool(row["rolbypassrls"]) if row else None,
        "sees_all_rows": bypasses,
        "note": (
            "This connection bypasses RLS, so its counts can be trusted."
            if bypasses
            else "This connection does NOT bypass RLS. Every NULL-tenant count below would be "
            "filtered to zero by the very policies under test. Re-run as an admin role."
        ),
    }


async def _policy_inventory(db: Any) -> dict[str, Any]:
    """What is actually deployed, read from pg_policy rather than from migrations."""
    rows = (await db.execute(sa.text("""
                SELECT c.relname AS table_name,
                       c.relrowsecurity AS enabled,
                       c.relforcerowsecurity AS forced,
                       pg_get_expr(p.polqual, p.polrelid) AS using_expr,
                       pg_get_expr(p.polwithcheck, p.polrelid) AS check_expr
                FROM pg_class AS c
                JOIN pg_namespace AS n ON n.oid = c.relnamespace
                JOIN pg_policy AS p ON p.polrelid = c.oid
                WHERE n.nspname = current_schema() AND p.polname = 'tenant_isolation'
                ORDER BY c.relname
                """))).mappings().all()

    deployed = {row["table_name"]: row for row in rows}
    per_table: list[dict[str, Any]] = []
    unguarded: list[str] = []
    not_forced: list[str] = []
    missing_check: list[str] = []

    for name, row in sorted(deployed.items()):
        using_expr = row["using_expr"] or ""
        check_expr = row["check_expr"]
        guarded = EMPTY_GUC_GUARD_MARKER in using_expr and EMPTY_GUC_GUARD_MARKER in (check_expr or "")
        if not guarded:
            unguarded.append(name)
        if not (row["enabled"] and row["forced"]):
            not_forced.append(name)
        if check_expr is None:
            missing_check.append(name)
        per_table.append(
            {
                "table": name,
                "enabled": bool(row["enabled"]),
                "forced": bool(row["forced"]),
                "empty_guc_safe": guarded,
                "using": using_expr,
            }
        )

    registry = set(RLS_TABLES)
    return {
        "deployed_policy_tables": len(deployed),
        "registry_tables": len(registry),
        "in_registry_but_no_policy": sorted(registry - set(deployed)),
        "has_policy_but_not_in_registry": sorted(set(deployed) - registry),
        "policies_without_empty_guc_guard": sorted(unguarded),
        "policies_not_enabled_and_forced": sorted(not_forced),
        "policies_without_with_check": sorted(missing_check),
        "per_table": per_table,
    }


async def _null_tenant_rows(db: Any, policy_tables: list[str], *, trusted: bool) -> dict[str, Any]:
    """Count NULL ``tenant_id`` rows in the policy tables — the real blast radius.

    Refuses to report numbers it cannot trust. Under a non-bypass role these
    counts are filtered to zero by the policies being assessed, which would produce
    a confident and completely wrong "nothing to backfill".
    """
    if not trusted:
        return {
            "trusted": False,
            "note": "Skipped: this connection does not bypass RLS, so every count would be a filtered zero.",
        }

    per_table: list[dict[str, Any]] = []
    total = 0
    for table in policy_tables:
        nullable = (
            await db.execute(
                sa.text(
                    "SELECT a.attnotnull FROM pg_attribute AS a "
                    "WHERE a.attrelid = CAST(:t AS regclass) AND a.attname = 'tenant_id'"
                ),
                {"t": table},
            )
        ).scalar()
        if nullable is None:
            per_table.append({"table": table, "null_tenant_rows": "no tenant_id column"})
            continue
        if nullable is True:
            # Column is NOT NULL, so the count is structurally zero. Say so rather
            # than issuing a scan that can only return 0.
            per_table.append({"table": table, "null_tenant_rows": 0, "column_not_null": True})
            continue
        # Table name comes from pg_policy / RLS_TABLES, never from argv.
        count = (await db.execute(sa.text(f"SELECT COUNT(*) FROM {table} WHERE tenant_id IS NULL"))).scalar()
        count = int(count or 0)
        total += count
        per_table.append({"table": table, "null_tenant_rows": count, "column_not_null": False})

    return {
        "trusted": True,
        "total_rows_that_would_become_invisible": total,
        "tables_affected": sorted(row["table"] for row in per_table if row.get("null_tenant_rows")),
        "per_table": [row for row in per_table if row.get("null_tenant_rows") or row.get("column_not_null") is False],
    }


async def _candidate_role(db: Any, role: str) -> dict[str, Any]:
    """Does the candidate exist, is it actually least-privilege, can it reach everything?"""
    attributes = (
        (
            await db.execute(
                sa.text(
                    "SELECT rolsuper, rolbypassrls, rolcreatedb, rolcreaterole, rolreplication, rolcanlogin "
                    "FROM pg_roles WHERE rolname = :r"
                ),
                {"r": role},
            )
        )
        .mappings()
        .first()
    )
    if attributes is None:
        return {
            "role": role,
            "exists": False,
            "note": "Role does not exist. Apply migration 20260903_app_lp_role, or create it per the runbook.",
        }

    escalations = [name for name in DISQUALIFYING_ATTRIBUTES if attributes[name]]

    missing_grants = (
        (
            await db.execute(
                sa.text("""
                SELECT t.table_name
                FROM information_schema.tables AS t
                WHERE t.table_schema = 'public'
                  AND t.table_type = 'BASE TABLE'
                  AND EXISTS (
                        SELECT 1 FROM unnest(CAST(:required AS text[])) AS need(priv)
                        WHERE NOT EXISTS (
                            SELECT 1 FROM information_schema.role_table_grants AS g
                            WHERE g.table_schema = 'public'
                              AND g.table_name = t.table_name
                              AND g.grantee = :role
                              AND g.privilege_type = need.priv
                        )
                  )
                ORDER BY t.table_name
                """),
                {"required": list(REQUIRED_TABLE_PRIVILEGES), "role": role},
            )
        )
        .scalars()
        .all()
    )

    missing_sequences = (
        (
            await db.execute(
                sa.text("""
                SELECT s.sequence_name
                FROM information_schema.sequences AS s
                WHERE s.sequence_schema = 'public'
                  AND NOT has_sequence_privilege(:role, quote_ident(s.sequence_name), 'USAGE')
                ORDER BY s.sequence_name
                """),
                {"role": role},
            )
        )
        .scalars()
        .all()
    )

    return {
        "role": role,
        "exists": True,
        "can_login": bool(attributes["rolcanlogin"]),
        "disqualifying_attributes": escalations,
        "tables_missing_required_grants": list(missing_grants),
        "sequences_missing_usage": list(missing_sequences),
        "note": (
            "Role cannot log in yet. That is the intended post-migration state; an operator "
            "grants LOGIN and a password from Key Vault at cutover."
            if not attributes["rolcanlogin"]
            else "Role can log in."
        ),
    }


async def _auth_bootstrap(db: Any, role: str) -> dict[str, Any]:
    """Can the candidate role read ``users`` with no tenant bound? Auth depends on it.

    ``get_current_user`` selects a user by id, and login selects one by email,
    *before* either knows the tenant — the tenant is a column on the row being
    fetched. Under FORCE RLS with no GUC there is nothing that can match, so the
    lookup returns nothing and every request 401s.

    Executed inside a transaction that is always rolled back, with ``SET LOCAL
    ROLE`` so the identity change cannot leak onto a pooled connection.
    """
    result: dict[str, Any] = {"probe_role": role}
    try:
        await db.execute(sa.text("SAVEPOINT run026_auth_probe"))
        await db.execute(sa.text(f"SET LOCAL ROLE {role}"))
        try:
            visible = (await db.execute(sa.text("SELECT count(*) FROM users"))).scalar()
            result["users_visible_without_tenant_guc"] = int(visible or 0)
            result["query_raised"] = None
        except Exception as exc:  # noqa: BLE001 - the failure mode is the finding
            result["users_visible_without_tenant_guc"] = None
            result["query_raised"] = f"{type(exc).__name__}: {exc}"
    finally:
        await db.execute(sa.text("ROLLBACK TO SAVEPOINT run026_auth_probe"))
        await db.execute(sa.text("RELEASE SAVEPOINT run026_auth_probe"))

    visible = result.get("users_visible_without_tenant_guc")
    result["auth_would_work"] = bool(visible)
    result["note"] = (
        "Authentication would break: the app cannot read the users row it needs in order to "
        "discover which tenant to bind. Fix the auth bootstrap before changing the role. "
        "See docs/governance/rls-least-privilege-rollout.md, gate 2."
        if not visible
        else "The candidate role can read users without a tenant bound."
    )
    return result


def _verdict(report: dict[str, Any]) -> dict[str, Any]:
    """Collapse the gates into a single go / no-go with named blockers."""
    blockers: list[str] = []
    warnings: list[str] = []

    policies = report["policies"]
    if policies["policies_without_empty_guc_guard"]:
        blockers.append(
            f"{len(policies['policies_without_empty_guc_guard'])} policy table(s) still use the "
            f"unguarded predicate and would raise 22P02 on a reused pooled connection: "
            f"{', '.join(policies['policies_without_empty_guc_guard'][:10])}"
        )
    if policies["policies_not_enabled_and_forced"]:
        blockers.append(
            f"policy present but RLS not both enabled and forced on: "
            f"{', '.join(policies['policies_not_enabled_and_forced'])}"
        )
    if policies["policies_without_with_check"]:
        blockers.append(
            f"policy has no WITH CHECK (writes unconstrained) on: "
            f"{', '.join(policies['policies_without_with_check'])}"
        )
    if policies["in_registry_but_no_policy"]:
        blockers.append(
            f"RLS_TABLES claims these are protected but no policy exists: "
            f"{', '.join(policies['in_registry_but_no_policy'])}"
        )
    if policies["has_policy_but_not_in_registry"]:
        warnings.append(
            f"policy deployed on tables absent from RLS_TABLES: "
            f"{', '.join(policies['has_policy_but_not_in_registry'])}"
        )

    candidate = report["candidate_role"]
    if not candidate.get("exists"):
        blockers.append(f"candidate role {candidate['role']} does not exist")
    else:
        if candidate["disqualifying_attributes"]:
            blockers.append(
                f"candidate role holds {', '.join(candidate['disqualifying_attributes'])}, "
                f"which defeats row-level security"
            )
        if candidate["tables_missing_required_grants"]:
            blockers.append(
                f"candidate role lacks required privileges on "
                f"{len(candidate['tables_missing_required_grants'])} table(s), which will 500 on first "
                f"access: {', '.join(candidate['tables_missing_required_grants'][:10])}"
            )
        if candidate["sequences_missing_usage"]:
            blockers.append(
                f"candidate role lacks USAGE on {len(candidate['sequences_missing_usage'])} sequence(s), "
                f"so inserts into those tables will fail"
            )
        if not candidate["can_login"]:
            warnings.append(
                "candidate role has no LOGIN yet — expected until cutover, but it must be granted "
                "(with a password from Key Vault) before the app can use it"
            )

    auth = report["auth_bootstrap"]
    if not auth.get("auth_would_work"):
        blockers.append(
            "authentication would break under the candidate role: users cannot be read without a "
            "tenant already bound, and the tenant is only knowable from the users row itself"
        )

    nulls = report["null_tenant_rows"]
    if not nulls.get("trusted"):
        blockers.append("NULL-tenant blast radius could not be measured from this connection")
    elif nulls.get("total_rows_that_would_become_invisible"):
        blockers.append(
            f"{nulls['total_rows_that_would_become_invisible']} row(s) in policy-protected tables have a "
            f"NULL tenant_id and would become invisible to the application: "
            f"{', '.join(nulls['tables_affected'])}"
        )

    return {
        "ready_for_role_change": not blockers,
        "blockers": blockers,
        "warnings": warnings,
    }


async def collect(*, candidate_role: str) -> dict[str, Any]:
    """Build the readiness report. Performs SELECTs only."""
    async with await open_session() as db:
        bind = db.get_bind()
        if getattr(getattr(bind, "dialect", None), "name", None) != "postgresql":
            return {
                "database": dsn_label(require_database_url()),
                "skipped": "Row-level security is PostgreSQL-only; nothing to assess on this dialect.",
            }

        identity = await _connection_identity(db)
        policies = await _policy_inventory(db)
        policy_tables = [row["table"] for row in policies["per_table"]]
        nulls = await _null_tenant_rows(db, policy_tables, trusted=bool(identity["sees_all_rows"]))
        candidate = await _candidate_role(db, candidate_role)
        if candidate.get("exists"):
            auth = await _auth_bootstrap(db, candidate_role)
        else:
            auth = {
                "probe_role": candidate_role,
                "auth_would_work": False,
                "note": "Cannot probe: candidate role does not exist.",
            }

        report: dict[str, Any] = {
            "database": dsn_label(require_database_url()),
            "tenant_guc": TENANT_GUC,
            "expected_predicate": TENANT_ISOLATION_PREDICATE,
            "connection": identity,
            "policies": policies,
            "null_tenant_rows": nulls,
            "candidate_role": candidate,
            "auth_bootstrap": auth,
        }
        report["verdict"] = _verdict(report)
        return report


async def _amain(args: argparse.Namespace) -> int:
    if args.apply:
        print(
            "rls_role_readiness is read-only by design; there is no --apply. Changing the "
            "application's database role is a human-authorised cutover with an ordering "
            "requirement, not a scripted mutation. See "
            "docs/governance/rls-least-privilege-rollout.md.",
            file=sys.stderr,
        )
        return 2

    mode = enforce_apply_safety(apply=False, i_understand_prod=False)
    require_database_url()

    payload: dict[str, Any] = {"script": "rls_role_readiness", "mode": mode}
    payload.update(await collect(candidate_role=args.candidate_role))
    emit_report(payload, as_json=args.json)

    if payload.get("skipped"):
        return 0
    return 0 if payload["verdict"]["ready_for_role_change"] else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_safety_args(parser)
    parser.add_argument(
        "--candidate-role",
        default=DEFAULT_CANDIDATE_ROLE,
        dest="candidate_role",
        help=f"Role the application would connect as after the cutover (default {DEFAULT_CANDIDATE_ROLE}).",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
