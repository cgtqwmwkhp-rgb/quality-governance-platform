#!/usr/bin/env python3
"""CI lint: forbid NEW owned entities with nullable ``tenant_id`` (WCS C-01).

Policy (Phase 1 — safe, no mass migration):

* Every mapped model with a ``tenant_id`` column must be either:
  - ``nullable=False``, or
  - listed in the grandfather baseline
    (``docs/governance/tenant_id_nullable_baseline.json``), or
  - listed as a catalog/global exception
    (``docs/governance/tenant_id_catalog_exceptions.json``).
* **New** owned tables (not in baseline, not in catalog) with
  ``tenant_id`` nullable → **CRITICAL** (exit 1).
* Baseline / catalog entries that no longer exist in the ORM → advisory
  (printed; do not fail — cleanup is encouraged in follow-up PRs).
* Shrinking the baseline (after a real NOT NULL migration) is allowed and
  expected; growing it requires an explicit baseline edit in the same PR
  (reviewers should reject silent growth).

This does **not** migrate existing tables to ``NOT NULL``.
"""

from __future__ import annotations

import importlib
import inspect
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = REPO_ROOT / "docs/governance/tenant_id_nullable_baseline.json"
CATALOG_PATH = REPO_ROOT / "docs/governance/tenant_id_catalog_exceptions.json"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _load_tables(path: Path) -> set[str]:
    if not path.exists():
        print(f"CRITICAL: missing policy file {path}", file=sys.stderr)
        raise SystemExit(1)
    payload = json.loads(path.read_text(encoding="utf-8"))
    tables = payload.get("tables")
    if isinstance(tables, dict):
        return set(tables.keys())
    if isinstance(tables, list):
        return set(tables)
    print(f"CRITICAL: {path} has invalid 'tables' payload", file=sys.stderr)
    raise SystemExit(1)


def _collect_models() -> list[type]:
    import src.domain.models as models_pkg

    out: list[type] = []
    for name in getattr(models_pkg, "__all__", []):
        obj = getattr(models_pkg, name, None)
        if not inspect.isclass(obj):
            continue
        if getattr(obj, "__tablename__", None) is None:
            continue
        if getattr(obj, "__table__", None) is None:
            continue
        out.append(obj)
    return out


def audit() -> tuple[list[str], list[str], dict[str, Any]]:
    importlib.import_module("src.domain.models")

    baseline = _load_tables(BASELINE_PATH)
    catalog = _load_tables(CATALOG_PATH)
    models = _collect_models()

    critical: list[str] = []
    advisory: list[str] = []

    orm_tables: set[str] = set()
    nullable_owned: set[str] = set()
    nullable_catalog: set[str] = set()
    required: set[str] = set()

    for cls in models:
        table_name = cls.__tablename__
        orm_tables.add(table_name)
        table = cls.__table__
        if "tenant_id" not in table.c:
            continue
        col = table.c["tenant_id"]
        if not col.nullable:
            required.add(table_name)
            continue
        if table_name in catalog:
            nullable_catalog.add(table_name)
            continue
        if table_name in baseline:
            nullable_owned.add(table_name)
            continue
        critical.append(
            f"{cls.__name__} (__tablename__={table_name!r}): "
            "tenant_id is nullable but table is not in the C-01 grandfather "
            f"baseline ({BASELINE_PATH.relative_to(REPO_ROOT)}) or catalog "
            f"exceptions ({CATALOG_PATH.relative_to(REPO_ROOT)}). "
            "New owned entities must use nullable=False (or document a "
            "catalog exception with owner + reason)."
        )

    stale_baseline = sorted(baseline - orm_tables)
    for name in stale_baseline:
        advisory.append(
            f"baseline lists {name!r} but no mapped model uses that "
            "__tablename__ — remove after confirming drop/rename"
        )

    stale_catalog = sorted(catalog - orm_tables)
    for name in stale_catalog:
        advisory.append(
            f"catalog exceptions list {name!r} but no mapped model uses that "
            "__tablename__ — remove after confirming drop/rename"
        )

    # Tables that became NOT NULL should leave the baseline (advisory nudge).
    for name in sorted(baseline & required):
        advisory.append(
            f"{name!r} is nullable=False in ORM but still in baseline — "
            "remove from baseline in this or a follow-up PR"
        )

    stats = {
        "models": len(models),
        "required": len(required),
        "nullable_owned_grandfathered": len(nullable_owned),
        "nullable_catalog": len(nullable_catalog),
        "critical": len(critical),
        "advisory": len(advisory),
    }
    return critical, advisory, stats


def main() -> int:
    critical, advisory, stats = audit()

    for msg in critical:
        print(f"CRITICAL: {msg}")
    for msg in advisory:
        print(f"advisory: {msg}")

    print(
        f"\nChecked {stats['models']} mapped model(s): "
        f"required={stats['required']}, "
        f"grandfathered_nullable={stats['nullable_owned_grandfathered']}, "
        f"catalog_nullable={stats['nullable_catalog']}, "
        f"critical={stats['critical']}, advisory={stats['advisory']}"
    )

    if critical:
        print(
            "\nValidation finished with CRITICAL violations "
            "(new owned nullable tenant_id).",
            file=sys.stderr,
        )
        return 1

    print("\nNo new owned nullable tenant_id columns.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
