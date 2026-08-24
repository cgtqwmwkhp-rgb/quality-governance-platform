#!/usr/bin/env python3
"""WI-2 / L-32 — static inventory of parallel file homes (read-only).

Reports ORM shape for the three WI-2 homes that must converge onto Register
``documents.id``:

* ``carbon_evidence`` — Planet Mark evidence blobs (``file_path`` / ``storage_key``)
* ``uvdb_audit_response.documents_presented`` — JSON presentation refs (not a blob column)
* ``evidence_assets`` — case/investigation blobs (optional Library link later)

This script does **not** require WI-1's alembic head and does **not** mutate
schema or data. It is the prep counterpart to
``docs/governance/library-file-homes-l32.md``.

Usage::

    PYTHONPATH=. python3 -m scripts.governance.library.file_homes_inventory
    PYTHONPATH=. python3 -m scripts.governance.library.file_homes_inventory --json

Exit ``0`` on successful inventory. Exit ``1`` if a scoped home is missing from
the ORM (regression against F-7).
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

# WI-2 scope — keep in lockstep with library-file-homes-l32.md / F-7.
WI2_HOMES: tuple[tuple[str, str, str], ...] = (
    ("carbon_evidence", "CarbonEvidence", "Planet Mark evidence blobs → documents.id"),
    (
        "uvdb_audit_response",
        "UVDBAuditResponse",
        "documents_presented JSON → Register id projection",
    ),
    ("evidence_assets", "EvidenceAsset", "Case blobs; optional documents.id when filed"),
)

FILE_HOME_COLUMNS = frozenset({"file_path", "storage_key", "thumbnail_storage_key"})
LINK_TARGET_COLUMNS = frozenset({"document_id", "library_document_id"})
PRESENTED_COLUMNS = frozenset({"documents_presented"})


@dataclass
class ColumnFact:
    name: str
    nullable: bool
    type_name: str
    fk_targets: list[str] = field(default_factory=list)


@dataclass
class HomeInventory:
    table: str
    model: str
    role: str
    columns: list[ColumnFact]
    file_home_columns: list[str]
    presented_columns: list[str]
    existing_document_fks: list[str]
    disposition: str
    wi2_action: str


def _fk_targets(column: Any) -> list[str]:
    out: list[str] = []
    for fk in getattr(column, "foreign_keys", ()) or ():
        col = getattr(fk, "column", None)
        if col is None:
            continue
        table = getattr(getattr(col, "table", None), "name", None)
        if table:
            out.append(f"{table}.{col.name}")
    return sorted(set(out))


def _type_name(column: Any) -> str:
    t = getattr(column, "type", None)
    if t is None:
        return "unknown"
    return type(t).__name__


def _model_by_tablename() -> dict[str, type]:
    import src.domain.models as models_pkg

    out: dict[str, type] = {}
    for name in getattr(models_pkg, "__all__", []):
        obj = getattr(models_pkg, name, None)
        table = getattr(obj, "__tablename__", None)
        if table and getattr(obj, "__table__", None) is not None:
            out[str(table)] = obj
    return out


def inventory_homes() -> list[HomeInventory]:
    """Build static inventories for the three WI-2 homes."""
    by_table = _model_by_tablename()
    results: list[HomeInventory] = []

    for table, model_name, role in WI2_HOMES:
        cls = by_table.get(table)
        if cls is None:
            results.append(
                HomeInventory(
                    table=table,
                    model=model_name,
                    role=role,
                    columns=[],
                    file_home_columns=[],
                    presented_columns=[],
                    existing_document_fks=[],
                    disposition="MISSING",
                    wi2_action="CRITICAL: model missing from ORM export",
                )
            )
            continue

        cols: list[ColumnFact] = []
        file_cols: list[str] = []
        presented: list[str] = []
        doc_fks: list[str] = []

        for column in cls.__table__.columns:
            fact = ColumnFact(
                name=column.name,
                nullable=bool(column.nullable),
                type_name=_type_name(column),
                fk_targets=_fk_targets(column),
            )
            cols.append(fact)
            if column.name in FILE_HOME_COLUMNS:
                file_cols.append(column.name)
            if column.name in PRESENTED_COLUMNS:
                presented.append(column.name)
            if column.name in LINK_TARGET_COLUMNS or any(
                t.startswith("documents.") for t in fact.fk_targets
            ):
                doc_fks.append(column.name)

        # The action is derived from the ORM, not asserted, so this report stops
        # telling a reader to add a column that WI-2 has already added.
        linked = bool(doc_fks)
        if table == "uvdb_audit_response":
            action = (
                "Normalise documents_presented elements to "
                "{document_id, label}; JSON stays projection not blob SoT"
            )
            disposition = "migrate"
        elif table == "carbon_evidence":
            action = (
                "LINKED: document_id FK present; promote remaining NULL rows via "
                "steward or proven match (F-3 allowlist shrink later)"
                if linked
                else "ADD nullable document_id FK → documents.id; keep PM metadata"
            )
            disposition = "linked" if linked else "migrate"
        else:
            action = (
                "LINKED: optional document_id FK present; case storage_key retained "
                "short-term (F-3 allowlist shrink later)"
                if linked
                else "ADD optional nullable document_id FK → documents.id when filed"
            )
            disposition = "linked" if linked else "migrate"

        results.append(
            HomeInventory(
                table=table,
                model=cls.__name__,
                role=role,
                columns=cols,
                file_home_columns=sorted(file_cols),
                presented_columns=sorted(presented),
                existing_document_fks=sorted(set(doc_fks)),
                disposition=disposition,
                wi2_action=action,
            )
        )
    return results


def inventory_report() -> dict[str, Any]:
    homes = inventory_homes()
    return {
        "programme": "WI-2 / L-32",
        "title": "File homes → documents.id",
        "depends_on": "WI-1 PROD (alembic 20261030_lib_wi1_cel)",
        "alembic_head": "20261031_lib_wi2_homes",
        "register_sot": "documents.id",
        "homes": [asdict(h) for h in homes],
        "summary": {
            "home_count": len(homes),
            "missing": [h.table for h in homes if h.disposition == "MISSING"],
            "already_linked": [
                h.table for h in homes if h.existing_document_fks and h.disposition != "MISSING"
            ],
            "needs_document_fk": [
                h.table
                for h in homes
                if h.table in {"carbon_evidence", "evidence_assets"} and not h.existing_document_fks
            ],
            "needs_presented_normalise": [
                h.table for h in homes if h.table == "uvdb_audit_response" and h.presented_columns
            ],
        },
    }


def _print_human(report: dict[str, Any]) -> None:
    print(f"WI-2 / L-32 file-homes inventory — Register SoT: {report['register_sot']}")
    print(f"Depends on: {report['depends_on']}")
    print()
    for home in report["homes"]:
        print(f"## {home['table']} ({home['model']})")
        print(f"  role:          {home['role']}")
        print(f"  disposition:   {home['disposition']}")
        print(f"  file columns:  {', '.join(home['file_home_columns']) or '—'}")
        print(f"  presented:     {', '.join(home['presented_columns']) or '—'}")
        print(f"  document FKs:  {', '.join(home['existing_document_fks']) or '(none yet)'}")
        print(f"  wi2 action:    {home['wi2_action']}")
        print()
    summary = report["summary"]
    print("Summary")
    print(f"  needs document_id FK:     {', '.join(summary['needs_document_fk']) or '—'}")
    print(f"  needs presented rewrite:  {', '.join(summary['needs_presented_normalise']) or '—'}")
    if summary["missing"]:
        print(f"  MISSING models:           {', '.join(summary['missing'])}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    args = parser.parse_args(argv)

    report = inventory_report()
    if args.json:
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        _print_human(report)

    if report["summary"]["missing"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
