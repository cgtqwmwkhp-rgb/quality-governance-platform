#!/usr/bin/env python3
"""Inventory ORM ``tenant_id`` nullability (WCS C-01 Phase 1).

Scans public mapped models under ``src.domain.models`` and reports:

* tables with required (``nullable=False``) ``tenant_id``
* tables with nullable ``tenant_id`` (owned vs catalog exceptions)
* tables with no ``tenant_id`` column

Optionally writes Markdown (``--markdown PATH``) and/or refreshes the
grandfather baseline JSON (``--write-baseline``) used by
``validate_tenant_id_not_null.py``.

Exit code ``0`` always on successful inventory (this script is informational).
"""

from __future__ import annotations

import argparse
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

# Highest-risk tenant-owned cores for Phase 2+ backfill (not enforced here).
PHASE2_CANDIDATES = (
    "incidents",
    "incident_actions",
    "audit_runs",
    "audit_findings",
    "risks",
    "risks_v2",
    "risk_assessments",
    "complaints",
)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def inventory() -> dict[str, Any]:
    importlib.import_module("src.domain.models")
    catalog = _load_json(CATALOG_PATH).get("tables") or {}
    catalog_tables = set(catalog.keys()) if isinstance(catalog, dict) else set(catalog)

    nullable: list[dict[str, str]] = []
    required: list[dict[str, str]] = []
    no_tenant: list[dict[str, str]] = []

    for cls in _collect_models():
        table = cls.__table__
        row = {"model": cls.__name__, "table": cls.__tablename__}
        if "tenant_id" not in table.c:
            no_tenant.append(row)
            continue
        if table.c["tenant_id"].nullable:
            nullable.append(row)
        else:
            required.append(row)

    nullable_sorted = sorted(nullable, key=lambda r: r["table"])
    owned_nullable = [r for r in nullable_sorted if r["table"] not in catalog_tables]
    catalog_nullable = [r for r in nullable_sorted if r["table"] in catalog_tables]
    phase2 = [r for r in owned_nullable if r["table"] in PHASE2_CANDIDATES]

    return {
        "required": sorted(required, key=lambda r: r["table"]),
        "owned_nullable": owned_nullable,
        "catalog_nullable": catalog_nullable,
        "no_tenant": sorted(no_tenant, key=lambda r: r["table"]),
        "phase2_candidates": phase2,
        "counts": {
            "required": len(required),
            "owned_nullable": len(owned_nullable),
            "catalog_nullable": len(catalog_nullable),
            "no_tenant": len(no_tenant),
            "nullable_total": len(nullable),
        },
    }


def render_markdown(data: dict[str, Any]) -> str:
    c = data["counts"]
    lines = [
        "# Tenant ID nullability inventory (C-01 Phase 1)",
        "",
        "Generated from public SQLAlchemy models in `src.domain.models`.",
        "",
        "## Summary",
        "",
        f"| Category | Count |",
        f"| --- | ---: |",
        f"| Required `tenant_id` (`nullable=False`) | {c['required']} |",
        f"| Owned nullable `tenant_id` | {c['owned_nullable']} |",
        f"| Catalog/global nullable `tenant_id` | {c['catalog_nullable']} |",
        f"| No `tenant_id` column | {c['no_tenant']} |",
        f"| **Nullable total** | **{c['nullable_total']}** |",
        "",
        "## Phase 1 decision",
        "",
        "Mass `NOT NULL` across ~170 tables is **deferred**. Live NULL-row risk is",
        "unknown without environment-specific counts, and document-control already",
        "uses a phased backfill pattern (`docs/data/document-control-tenant-backfill.md`).",
        "",
        "This phase lands:",
        "",
        "1. This inventory + grandfather baseline for owned nullable tables.",
        "2. CI lint forbidding **new** owned entities with nullable `tenant_id`.",
        "3. Explicit catalog/global exception list.",
        "",
        "## Phase 2 progress",
        "",
        "| Table | Status | Notes |",
        "| --- | --- | --- |",
        "| `audit_findings` | **Done (incremental)** | Fail-safe backfill from `audit_runs` + conditional `NOT NULL` (`20260710_af_tenant_nn`). ORM `nullable=False`. See `docs/data/audit-findings-tenant-backfill.md`. |",
        "| `incident_actions` | **Done (incremental)** | Fail-safe backfill from `incidents` + conditional `NOT NULL` (`20260710_ia_tenant_nn`). ORM `nullable=False`. See `docs/data/incident-actions-tenant-backfill.md`. |",
        "| `complaint_actions` | **Done (incremental)** | Fail-safe backfill from `complaints` + conditional `NOT NULL` (`20260710_ca_tenant_nn`). ORM `nullable=False`. See `docs/data/complaint-actions-tenant-backfill.md`. |",
        "| `audit_runs` | **Done (incremental)** | Fail-safe backfill from `audit_templates` + conditional `NOT NULL` (`20260710_ar_tenant_nn`). ORM `nullable=False`. See `docs/data/audit-runs-tenant-backfill.md`. |",
        "| `rta_actions` | **Done (incremental)** | Fail-safe backfill from `road_traffic_collisions` + conditional `NOT NULL` (`20260710_rta_act_nn`). ORM `nullable=False`. See `docs/data/rta-actions-tenant-backfill.md`. |",
        "| `capa_actions` | **Done (incremental)** | Fail-safe backfill from `users` (creator) + conditional `NOT NULL` (`20260710_capa_act_nn`). ORM `nullable=False`. See `docs/data/capa-actions-tenant-backfill.md`. |",
        "| `investigation_actions` | **Done (incremental)** | Fail-safe backfill from `investigation_runs` + conditional `NOT NULL` (`20260710_inv_act_nn`). ORM `nullable=False`. See `docs/data/investigation-actions-tenant-backfill.md`. |",
        "| `investigation_comments` | **Done (incremental)** | Fail-safe backfill from `investigation_runs` + conditional `NOT NULL` (`20260710_inv_cmt_nn`). ORM `nullable=False`. See `docs/data/investigation-comments-tenant-backfill.md`. |",
        "| `investigation_revision_events` | **Done (incremental)** | Fail-safe backfill from `investigation_runs` + conditional `NOT NULL` (`20260710_inv_rev_evt_nn`). ORM `nullable=False`. See `docs/data/investigation-revision-events-tenant-backfill.md`. |",
        "| `investigation_runs` | **Done (incremental)** | Fail-safe backfill from `investigation_templates` + conditional `NOT NULL` (`20260710_ir_tenant_nn`). ORM `nullable=False`. See `docs/data/investigation-runs-tenant-backfill.md`. |",
        "| `investigation_customer_packs` | **Done (incremental)** | Fail-safe backfill from `investigation_runs` + conditional `NOT NULL` (`20260710_inv_pack_nn`). ORM `nullable=False`. See `docs/data/investigation-customer-packs-tenant-backfill.md`. |",
        "| `incidents` / `risks` / `risks_v2` / `risk_assessments` / `complaints` | Deferred | Parent cores remain nullable; child action families hardened incrementally. |",
        "",
        "## Highest-risk Phase 2 candidates (backfill + NOT NULL when safe)",
        "",
        "Do **not** enforce `NOT NULL` until NULL counts are zero in every environment",
        "and ownership attribution is approved (no silent `tenant_id=1` backfill).",
        "",
        "| Table | Model |",
        "| --- | --- |",
    ]
    for row in data["phase2_candidates"]:
        lines.append(f"| `{row['table']}` | `{row['model']}` |")
    if not data["phase2_candidates"]:
        lines.append("| _(none currently nullable)_ | |")

    lines.extend(
        [
            "",
            "## Required `tenant_id`",
            "",
            "| Table | Model |",
            "| --- | --- |",
        ]
    )
    for row in data["required"]:
        lines.append(f"| `{row['table']}` | `{row['model']}` |")

    lines.extend(
        [
            "",
            "## Owned nullable `tenant_id` (grandfathered)",
            "",
            "| Table | Model |",
            "| --- | --- |",
        ]
    )
    for row in data["owned_nullable"]:
        lines.append(f"| `{row['table']}` | `{row['model']}` |")

    lines.extend(
        [
            "",
            "## Catalog / global exceptions (nullable allowed)",
            "",
            "| Table | Model |",
            "| --- | --- |",
        ]
    )
    for row in data["catalog_nullable"]:
        lines.append(f"| `{row['table']}` | `{row['model']}` |")

    lines.extend(
        [
            "",
            "## No `tenant_id` column",
            "",
            "| Table | Model |",
            "| --- | --- |",
        ]
    )
    for row in data["no_tenant"]:
        lines.append(f"| `{row['table']}` | `{row['model']}` |")

    lines.append("")
    return "\n".join(lines)


def write_baseline(data: dict[str, Any]) -> None:
    payload = {
        "version": 1,
        "wcs_finding": "C-01",
        "description": (
            "Grandfathered tenant-owned ORM tables that currently declare nullable "
            "tenant_id. CI forbids NEW owned tables with nullable tenant_id. Shrink "
            "this list only when a table is backfilled and migrated to nullable=False."
        ),
        "generated_from": "src.domain.models public exports",
        "tables": [r["table"] for r in data["owned_nullable"]],
    }
    BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--markdown",
        type=Path,
        help="Write Markdown inventory to this path",
    )
    parser.add_argument(
        "--write-baseline",
        action="store_true",
        help=f"Refresh {BASELINE_PATH.relative_to(REPO_ROOT)} from current ORM",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON to stdout",
    )
    args = parser.parse_args()

    data = inventory()
    if args.write_baseline:
        write_baseline(data)
        print(f"Wrote baseline ({data['counts']['owned_nullable']} tables) → {BASELINE_PATH}")

    if args.markdown:
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(render_markdown(data), encoding="utf-8")
        print(f"Wrote Markdown → {args.markdown}")

    if args.json:
        print(json.dumps(data, indent=2))
    else:
        c = data["counts"]
        print(
            f"tenant_id inventory: required={c['required']} "
            f"owned_nullable={c['owned_nullable']} "
            f"catalog_nullable={c['catalog_nullable']} "
            f"no_tenant={c['no_tenant']} "
            f"nullable_total={c['nullable_total']}"
        )
        phase2 = ", ".join(r["table"] for r in data["phase2_candidates"]) or "(none)"
        print(f"Phase 2 candidates: {phase2}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
