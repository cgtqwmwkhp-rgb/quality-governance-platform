#!/usr/bin/env python3
"""Ratchet the drift `alembic check` is configured not to fail on.

Why this exists
---------------
``alembic check`` in CI runs with ``ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1``, which
strips seven operation types from the autogenerate result, and with a 41-name
``include_object`` exclusion list that removes whole tables from the comparison
before it starts. On the current main that combination turns 1060 detected
operations across 209 tables into 0, so the gate passes and the log says "No new
upgrade operations detected".

Every part of that is deliberate and documented
(``docs/governance/alembic_check_excluded_tables.md``). The problem is not the
deferral, it is that the deferral is unbounded: nothing measured how large it was,
and nothing stopped it growing. A gate that is muted across the surface it exists
to watch, with no record of how much it is muting, has stopped being a gate.

This script does not remove the mute. It makes it a ratchet:

* **Reports** the pre-filter and post-filter operation counts and their breakdown,
  so a green run states its own cost instead of hiding it.
* **Fails** when the suppressed set grows -- a table that had no drift acquiring
  some, a table acquiring an operation type it did not have, or a count rising
  above the committed baseline.
* **Fails on any AddColumnOp at all**, regardless of the baseline. See
  ``_check_add_column_ops`` for why that class is treated separately.
* **Fails** if a name is added to the exclusion list in ``alembic/env.py`` without
  a matching row in the governance inventory, so the register cannot be widened
  silently.

What it deliberately does not fail on
-------------------------------------
Drift *shrinking*. If a migration lands that removes drift, the baseline is now
overstated and this script says so loudly and exits 0. Failing there would make a
red gate the reward for fixing schema drift, which is how mutes get widened in the
first place. The same reasoning applies to an exclusion-list entry whose drift has
gone: reported as stale and removable, not failed on.

Refreshing the baseline
-----------------------
    unset DATABASE_URL
    DATABASE_URL=postgresql+asyncpg://... alembic upgrade head
    DATABASE_URL=postgresql+asyncpg://... \
      ALEMBIC_FILTER_FK_TENANT_INDEX_DRIFT=1 \
      ALEMBIC_DRIFT_INVENTORY_FILE=alembic-drift-inventory.json alembic check
    python3 scripts/validate_alembic_drift_ratchet.py --write-baseline

A refresh that *raises* a count needs the same review as any other widening of the
deferral register; the diff on the baseline file is the artefact reviewers read.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_INVENTORY = REPO_ROOT / "alembic-drift-inventory.json"
DEFAULT_BASELINE = REPO_ROOT / "docs" / "governance" / "alembic_drift_baseline.json"
EXCLUSION_DOC = REPO_ROOT / "docs" / "governance" / "alembic_check_excluded_tables.md"

#: Operations whose absence from the database makes a table unreadable rather than
#: merely differently shaped. See ``_check_add_column_ops``.
QUERY_BREAKING_OPS = ("AddColumnOp",)


def _ensure_repo_importable() -> None:
    """Put the repository on ``sys.path`` without shadowing the Alembic package.

    ``REPO_ROOT`` holds a directory called ``alembic`` with an ``__init__.py``, so
    prepending it makes ``import alembic.autogenerate`` resolve to the migration
    environment instead of the installed library. Appending leaves site-packages
    ahead of it, which is what both need.
    """
    path = str(REPO_ROOT)
    if path not in sys.path:
        sys.path.append(path)


class RatchetFailure(Exception):
    """A drift condition that must block the merge."""


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def load_inventory(path: Path) -> dict[str, Any]:
    """Read the artifact ``alembic check`` publishes via ALEMBIC_DRIFT_INVENTORY_FILE."""
    if not path.is_file():
        raise RatchetFailure(
            f"drift inventory not found at {path}. It is written by `alembic check` "
            "when ALEMBIC_DRIFT_INVENTORY_FILE is set; if that step failed, fix it "
            "first -- this check cannot report on a comparison that did not run."
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    for key in ("before_filter", "after_filter"):
        if key not in data:
            raise RatchetFailure(f"{path} has no {key!r} key; it was not written by alembic/env.py")
    return data


def documented_exclusions() -> set[str]:
    """Table names with a row in the governance inventory document."""
    if not EXCLUSION_DOC.is_file():
        raise RatchetFailure(f"exclusion inventory document not found at {EXCLUSION_DOC}")
    text = EXCLUSION_DOC.read_text(encoding="utf-8")
    return set(re.findall(r"^\|\s*`([a-z0-9_]+)`\s*\|", text, re.MULTILINE))


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------


def _check_unsuppressed_drift(after: dict[str, Any]) -> list[str]:
    """Drift the filter did not remove.

    ``alembic check`` fails on this by itself, so reaching here means either the
    check step was allowed to continue or the filter changed. Restated rather than
    assumed, because the whole point of this file is not to trust that a gate
    upstream is still doing what its name says.
    """
    if not after["total_operations"]:
        return []
    return [
        f"{after['total_operations']} operation(s) survived the filter across "
        f"{after['tables_with_drift']} table(s): {after['by_operation']}. "
        "`alembic check` should already have failed on this."
    ]


def _check_add_column_ops(before: dict[str, Any]) -> list[str]:
    """No column a model declares may be absent from the migrated schema.

    This class is failed on unconditionally rather than ratcheted, for two
    reasons. First, severity: SQLAlchemy emits every mapped column for a
    whole-entity load, so one absent column makes the entire table unreadable
    through the ORM, not just the queries that name the column -- the failure is
    ``UndefinedColumn`` on any ``select(Model)``. Second, cost: the count on the
    current main is zero, so a zero-tolerance rule here defers nothing that exists
    and blocks the entire class from returning. If a legitimate case ever needs
    deferring, it belongs in the exclusion register with an owner, where it is
    visible, and not in a baseline number that quietly accumulates.
    """
    failures = []
    for op_type in QUERY_BREAKING_OPS:
        count = before["by_operation"].get(op_type, 0)
        if not count:
            continue
        tables = sorted(t for t, ops in before["by_table"].items() if ops.get(op_type))
        failures.append(
            f"{count} {op_type} on {len(tables)} table(s): {', '.join(tables)}. "
            "A declared column the database does not have makes the whole table "
            "unreadable to a whole-entity ORM load. Add a migration; do not "
            "baseline this."
        )
    return failures


def _check_ratchet(before: dict[str, Any], baseline: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Compare per-table, per-operation counts against the committed baseline."""
    failures: list[str] = []
    warnings: list[str] = []
    baseline_tables: dict[str, dict[str, int]] = baseline.get("tables", {})
    current: dict[str, dict[str, int]] = before["by_table"]

    for table in sorted(current):
        recorded = baseline_tables.get(table)
        if recorded is None:
            failures.append(
                f"new drift on {table!r}, which the baseline records no drift for: "
                f"{current[table]}. Either migrate it or refresh the baseline in a "
                "PR that says why the deferral grew."
            )
            continue
        for op_type in sorted(current[table]):
            was = recorded.get(op_type, 0)
            now = current[table][op_type]
            if was == 0:
                failures.append(f"new {op_type} drift on {table!r} ({now}); the baseline records none for that table")
            elif now > was:
                failures.append(f"{op_type} drift on {table!r} rose from {was} to {now}")

    for table in sorted(baseline_tables):
        if table not in current:
            warnings.append(
                f"{table!r} has no drift any more (baseline: {baseline_tables[table]}) -- baseline is stale"
            )
            continue
        for op_type in sorted(baseline_tables[table]):
            was = baseline_tables[table][op_type]
            now = current[table].get(op_type, 0)
            if now < was:
                warnings.append(f"{op_type} drift on {table!r} fell from {was} to {now} -- baseline is stale")

    return failures, warnings


def _check_exclusion_register(declared: set[str], documented: set[str]) -> list[str]:
    """The frozenset in env.py and the governance document must agree.

    ``docs/governance/alembic_check_excluded_tables.md`` already asks for a row in
    the same PR as the code change. Nothing enforced it, which is how a mute
    becomes permanent: the entry is cheap to add and the owner and reason are
    optional in practice. Enforced in both directions, because a documented row
    with no code entry is a claim the gate is muted where it is not.
    """
    failures = []
    undocumented = sorted(declared - documented)
    if undocumented:
        failures.append(
            f"{len(undocumented)} name(s) in _ALEMBIC_CHECK_EXCLUDED_TABLES have no row in "
            f"{EXCLUSION_DOC.relative_to(REPO_ROOT)}: {', '.join(undocumented)}. "
            "Add owner + reason in this PR."
        )
    orphaned = sorted(documented - declared)
    if orphaned:
        failures.append(
            f"{len(orphaned)} row(s) in {EXCLUSION_DOC.relative_to(REPO_ROOT)} name a table that is "
            f"not excluded in alembic/env.py: {', '.join(orphaned)}. Delete the row."
        )
    return failures


def audit_excluded_tables(database_url: str, declared: set[str]) -> dict[str, dict[str, int]]:
    """Drift that would surface if the excluded tables were compared.

    ``include_object`` returning ``False`` removes the table from the comparison
    entirely, columns included, so none of this appears in the published inventory
    at any stage -- not even before the filter. That is worth measuring separately
    because it is where the one real query-breaking case on this repository lives:
    ``soa_control_entries`` declares four columns the database does not have, and
    the table-level exclusion is why no gate mentions it.

    Imports are local: this is the only part of the script that needs the
    application and a live database, and the rest must stay runnable without them.
    """
    import sqlalchemy as sa
    from alembic.autogenerate import produce_migrations
    from alembic.migration import MigrationContext
    from alembic.operations import ops as alembic_ops

    _ensure_repo_importable()
    from scripts.ops.run025._models import load_metadata

    metadata = load_metadata()
    engine = sa.create_engine(database_url.replace("+asyncpg", "").replace("+aiosqlite", ""))
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection=connection, opts={"compare_type": True})
            script = produce_migrations(context, metadata)
    finally:
        engine.dispose()

    counts: dict[str, dict[str, int]] = {}

    def walk(ops: list) -> None:
        for op in ops:
            if isinstance(op, alembic_ops.ModifyTableOps):
                walk(list(op.ops))
                continue
            for attribute in ("table_name", "source_table", "target_table"):
                value = getattr(op, attribute, None)
                name = value if isinstance(value, str) else getattr(value, "name", None)
                if isinstance(name, str) and name:
                    break
            else:
                name = None
            if name in declared:
                counts.setdefault(name, {})
                counts[name][type(op).__name__] = counts[name].get(type(op).__name__, 0) + 1

    walk(list(script.upgrade_ops.ops))
    return {t: dict(sorted(ops.items())) for t, ops in sorted(counts.items())}


def _check_excluded_table_ratchet(
    current: dict[str, dict[str, int]], baseline: dict[str, dict[str, int]]
) -> tuple[list[str], list[str]]:
    """Ratchet the excluded tables too, at the counts the register already carries.

    Zero tolerance for ``AddColumnOp`` is not applied here: ``soa_control_entries``
    already has four, deferred to a named owner because the physical table is a
    rename carrying a different design and guessing the mapping would mis-file
    compliance evidence (see ``scripts/ops/run026/audit_attribution_schema.py``).
    Failing on it would redden main over a decision that is already recorded. It
    is ratcheted instead, so a *second* table joining that class fails.
    """
    failures: list[str] = []
    warnings: list[str] = []
    for table in sorted(current):
        recorded = baseline.get(table, {})
        for op_type in sorted(current[table]):
            was = recorded.get(op_type, 0)
            now = current[table][op_type]
            if now > was:
                severity = " (query-breaking)" if op_type in QUERY_BREAKING_OPS else ""
                failures.append(f"excluded table {table!r}: {op_type} rose from {was} to {now}{severity}")
    for table in sorted(baseline):
        if table not in current:
            warnings.append(
                f"excluded table {table!r} has no drift at all -- the exclusion is stale and the "
                "name can be removed from _ALEMBIC_CHECK_EXCLUDED_TABLES"
            )
    return failures, warnings


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------


def _print_report(before: dict[str, Any], after: dict[str, Any], excluded: set[str], audit: Optional[dict]) -> None:
    print("=== Alembic drift ratchet ===")
    print(
        f"operations detected (before filter): {before['total_operations']} across {before['tables_with_drift']} table(s)"
    )
    print(f"operations remaining (after filter): {after['total_operations']}")
    print(f"operations suppressed by the op-type filter: {before['total_operations'] - after['total_operations']}")
    print("breakdown before filter:")
    for op_type, count in before["by_operation"].items():
        print(f"  {op_type}: {count}")
    print(f"tables removed from the comparison entirely by include_object: {len(excluded)}")
    if audit is not None:
        total = sum(sum(ops.values()) for ops in audit.values())
        add_columns = {t: ops["AddColumnOp"] for t, ops in audit.items() if ops.get("AddColumnOp")}
        print(f"  drift hidden on those tables: {total} operation(s) across {len(audit)} table(s)")
        print(f"  of which query-breaking AddColumnOp: {sum(add_columns.values())} on {sorted(add_columns)}")
        print(f"  exclusions with no drift left (removable): {sorted(set(excluded) - set(audit))}")
    else:
        print("  (not measured: no database URL given, so the hidden drift is unquantified in this run)")


def build_baseline(before: dict[str, Any], audit: Optional[dict], excluded: set[str]) -> dict[str, Any]:
    baseline = {
        "_comment": (
            "Committed inventory of the migration drift CI is configured not to fail on. "
            "Generated by scripts/validate_alembic_drift_ratchet.py --write-baseline. "
            "Counts here are a ceiling, not a target: the gate fails when one rises."
        ),
        "total_operations": before["total_operations"],
        "tables_with_drift": before["tables_with_drift"],
        "by_operation": before["by_operation"],
        "tables": before["by_table"],
        "excluded_tables": sorted(excluded),
    }
    if audit is not None:
        baseline["excluded_table_drift"] = audit
    return baseline


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument(
        "--database-url",
        default=None,
        help="Measure the drift hidden by include_object as well. Requires the migrated database.",
    )
    parser.add_argument("--write-baseline", action="store_true", help="Rewrite the baseline from this run.")
    parser.add_argument("--json", type=Path, default=None, help="Write the machine-readable report here.")
    args = parser.parse_args(argv)

    _ensure_repo_importable()
    from scripts.ops.run025._models import alembic_check_excluded_tables

    try:
        inventory = load_inventory(args.inventory)
    except RatchetFailure as exc:
        print(f"[FAIL] {exc}", file=sys.stderr)
        return 1

    before = inventory.get("summary_before_filter")
    after = inventory.get("summary_after_filter")
    if before is None or after is None:
        print(
            "[FAIL] the inventory carries no summary. Regenerate it with the current "
            "alembic/env.py, which writes summary_before_filter / summary_after_filter.",
            file=sys.stderr,
        )
        return 1

    declared = set(alembic_check_excluded_tables())

    audit: Optional[dict] = None
    if args.database_url:
        try:
            audit = audit_excluded_tables(args.database_url, declared)
        except Exception as exc:  # noqa: BLE001 - the reason must reach the log, whatever it is
            print(f"[FAIL] could not measure drift on the excluded tables: {exc!r}", file=sys.stderr)
            return 1

    _print_report(before, after, declared, audit)

    if args.write_baseline:
        payload = build_baseline(before, audit, declared)
        args.baseline.parent.mkdir(parents=True, exist_ok=True)
        args.baseline.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        print(f"[OK] baseline written to {args.baseline}")
        return 0

    if not args.baseline.is_file():
        print(f"[FAIL] no baseline at {args.baseline}; generate one with --write-baseline", file=sys.stderr)
        return 1
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))

    failures: list[str] = []
    warnings: list[str] = []

    failures += _check_unsuppressed_drift(after)
    failures += _check_add_column_ops(before)
    ratchet_failures, ratchet_warnings = _check_ratchet(before, baseline)
    failures += ratchet_failures
    warnings += ratchet_warnings
    try:
        failures += _check_exclusion_register(declared, documented_exclusions())
    except RatchetFailure as exc:
        failures.append(str(exc))
    if audit is not None:
        excluded_failures, excluded_warnings = _check_excluded_table_ratchet(
            audit, baseline.get("excluded_table_drift", {})
        )
        failures += excluded_failures
        warnings += excluded_warnings

    for warning in warnings:
        print(f"[WARN] {warning}")
    if warnings:
        print(
            f"[WARN] {len(warnings)} warning(s): drift has shrunk since the baseline was taken. "
            "Refresh it with --write-baseline so the ratchet tightens."
        )

    for failure in failures:
        print(f"[FAIL] {failure}", file=sys.stderr)

    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "summary_before_filter": before,
                    "summary_after_filter": after,
                    "excluded_tables": sorted(declared),
                    "excluded_table_drift": audit,
                    "failures": failures,
                    "warnings": warnings,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    if failures:
        print(f"[FAIL] {len(failures)} ratchet violation(s); the suppressed drift set grew.", file=sys.stderr)
        return 1

    print(
        f"[OK] {before['total_operations']} suppressed operation(s) across "
        f"{before['tables_with_drift']} table(s), all within the committed baseline; "
        f"0 AddColumnOp; exclusion register matches its documentation."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
