#!/usr/bin/env python3
"""Library F-3 / L-49 anti-dupe CI gate.

Fails when the ORM / Python tree introduces parallel document homes or coverage
SoT twins. Enhance existing infrastructure — never invent a second file store,
coverage claims table, free-text standards column on documents-like models, or
SPA document URL builder outside ``href_registry``.

Checks
------
1. **File homes** — mapped tables with ``file_path`` or ``storage_key`` must be
   listed in ``docs/governance/library_anti_dupe_baseline.json`` →
   ``file_home_tables``.
2. **Coverage twins** — mapped ``__tablename__`` matching ``*coverage*`` /
   ``*framework*`` / ``*scheme*`` must be allowlisted (CEL SoT remains
   ``compliance_evidence_links``).
3. **Free-text standards** — documents-like models must not grow String/Text/JSON
   columns named like ``iso_clause`` / ``clause_text`` / ``applicable_standards``
   (use CEL / ``clauses`` FK).
4. **Document URLs** (optional static grep) — Python under ``src/`` must not
   f-string-build SPA ``/documents/{id}`` paths outside the URL allowlist
   (``href_registry`` is the SoT).

Exit ``1`` on any CRITICAL finding. Advisory messages do not fail the gate.

Run::

    python3 scripts/governance/library/anti_dupe_gate.py
    PYTHONPATH=. python3 -m pytest tests/unit/test_library_anti_dupe_gate.py -q
"""

from __future__ import annotations

import importlib
import inspect
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[3]
BASELINE_PATH = REPO_ROOT / "docs/governance/library_anti_dupe_baseline.json"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FILE_HOME_COLUMNS = frozenset({"file_path", "storage_key"})

# Glob-style *coverage* / *framework* / *scheme* on snake_case table names.
COVERAGE_TWIN_TABLE_RE = re.compile(
    r"(coverage|frameworks?|schemes?)",
    re.IGNORECASE,
)

# Free-text standards / clause bags that twin CEL / clauses catalogue.
FREETEXT_STANDARDS_COL_RE = re.compile(
    r"^(applicable_standards|standard_refs?|standards_text|standards_covered|"
    r"all_clauses|clause_codes|standard_codes|"
    r"clause_text|clause_refs?|clause_string|free_text_clause|"
    r"iso_clause|iso_clauses|framework_name|framework_code|framework_refs?)$",
    re.IGNORECASE,
)

DOCUMENTS_LIKE_TABLE_RE = re.compile(
    r"^(documents?|document_.+|controlled_documents?|controlled_document_.+|"
    r"polic(y|ies)|policy_.+|carbon_evidence|evidence_assets)$",
    re.IGNORECASE,
)

# SPA deep-link builders — not API routes (/api/v1/...) and not regex scanners.
SPA_DOCUMENT_URL_RE = re.compile(
    r"""f["']/documents/\{""",
)

_META_KEYS = frozenset({"_comment", "_notes", "comment", "notes"})


def _load_baseline() -> dict[str, Any]:
    if not BASELINE_PATH.exists():
        print(f"CRITICAL: missing baseline {BASELINE_PATH}", file=sys.stderr)
        raise SystemExit(1)
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        print(f"CRITICAL: {BASELINE_PATH} must be a JSON object", file=sys.stderr)
        raise SystemExit(1)
    return payload


def _table_map(payload: dict[str, Any], key: str) -> dict[str, str]:
    raw = payload.get(key, {})
    if isinstance(raw, list):
        return {str(item): "" for item in raw if str(item) not in _META_KEYS}
    if not isinstance(raw, dict):
        print(f"CRITICAL: baseline key {key!r} must be object or list", file=sys.stderr)
        raise SystemExit(1)
    return {str(k): str(v) for k, v in raw.items() if str(k) not in _META_KEYS}


def _path_list(payload: dict[str, Any], key: str) -> set[str]:
    raw = payload.get(key, [])
    if not isinstance(raw, list):
        print(f"CRITICAL: baseline key {key!r} must be a list", file=sys.stderr)
        raise SystemExit(1)
    out: set[str] = set()
    for item in raw:
        text = str(item).replace("\\", "/").lstrip("./")
        if text and text not in _META_KEYS:
            out.add(text)
    return out


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


def _is_stringish_or_json(column: Any) -> bool:
    from sqlalchemy import JSON, String, Text
    from sqlalchemy.sql.type_api import TypeDecorator

    t = column.type
    visited = 0
    while isinstance(t, TypeDecorator) and visited < 8:
        visited += 1
        inner = t.impl
        if isinstance(inner, type):
            return False
        t = inner
    return isinstance(t, (String, Text, JSON)) or type(t).__name__ in {
        "String",
        "Text",
        "VARCHAR",
        "JSON",
    }


def _is_documents_like(table_name: str, file_home_tables: set[str]) -> bool:
    if table_name in file_home_tables:
        return True
    return bool(DOCUMENTS_LIKE_TABLE_RE.match(table_name))


def _scan_document_url_builders(allowlist: set[str]) -> list[str]:
    """Static grep for SPA document URL f-strings outside href_registry allowlist."""
    critical: list[str] = []
    src_root = REPO_ROOT / "src"
    if not src_root.is_dir():
        return critical

    for path in sorted(src_root.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in allowlist:
            continue
        # API route modules declare FastAPI paths — not SPA href builders.
        if "/api/routes/" in rel or rel.startswith("src/api/routes/"):
            continue
        if "/authz/route_declarations.py" in rel:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            critical.append(f"could not read {rel}: {exc}")
            continue
        for line_no, line in enumerate(text.splitlines(), start=1):
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if SPA_DOCUMENT_URL_RE.search(line):
                critical.append(
                    f"{rel}:{line_no}: SPA document URL f-string outside "
                    f"href_registry allowlist. Use "
                    f"src.domain.services.href_registry.document_href / href_for, "
                    f"or add this path to document_url_builder_allowlist with reason."
                )
    return critical


def audit() -> tuple[list[str], list[str], dict[str, Any]]:
    """Run all anti-dupe checks. Returns (critical, advisory, stats)."""
    importlib.import_module("src.domain.models")

    baseline = _load_baseline()
    file_homes = _table_map(baseline, "file_home_tables")
    twin_allow = _table_map(baseline, "coverage_twin_table_allowlist")
    freetext_allow = _table_map(baseline, "documents_like_freetext_allowlist")
    url_allow = _path_list(baseline, "document_url_builder_allowlist")

    # href_registry is always permitted even if baseline is edited down.
    url_allow.add("src/domain/services/href_registry.py")

    models = _collect_models()
    critical: list[str] = []
    advisory: list[str] = []

    orm_tables: set[str] = set()
    file_home_hits: set[str] = set()
    twin_hits: set[str] = set()
    freetext_hits: set[str] = set()

    for cls in models:
        table_name = cls.__tablename__
        orm_tables.add(table_name)
        table = cls.__table__
        col_names = set(table.c.keys())

        found_homes = sorted(col_names & FILE_HOME_COLUMNS)
        if found_homes:
            file_home_hits.add(table_name)
            if table_name not in file_homes:
                critical.append(
                    f"{cls.__name__} (__tablename__={table_name!r}): "
                    f"has {found_homes} but is not in file_home_tables baseline "
                    f"({BASELINE_PATH.relative_to(REPO_ROOT)}). "
                    "Do not add a parallel document home — store files on "
                    "documents / document_versions (or document an F-7 disposition)."
                )

        if COVERAGE_TWIN_TABLE_RE.search(table_name):
            twin_hits.add(table_name)
            if table_name not in twin_allow:
                critical.append(
                    f"{cls.__name__} (__tablename__={table_name!r}): "
                    "name matches *coverage* / *framework* / *scheme* and is not "
                    "allowlisted. Coverage SoT is compliance_evidence_links (CEL); "
                    "scheme identity converges on standards / clauses — do not twin."
                )

        if _is_documents_like(table_name, set(file_homes)):
            for col in table.columns:
                if not FREETEXT_STANDARDS_COL_RE.match(col.name):
                    continue
                if not _is_stringish_or_json(col):
                    continue
                key = f"{table_name}.{col.name}"
                freetext_hits.add(key)
                if key not in freetext_allow:
                    critical.append(
                        f"{cls.__name__}.{col.name} (__tablename__={table_name!r}): "
                        "free-text standards/clause column on a documents-like model. "
                        "Use compliance_evidence_links / clauses FK — do not store "
                        "ALL_CLAUSES-style strings on the document home."
                    )

    for name in sorted(set(file_homes) - orm_tables):
        advisory.append(
            f"file_home_tables lists {name!r} but no mapped model uses that "
            "__tablename__ — remove after confirming drop/rename"
        )
    for name in sorted(set(twin_allow) - orm_tables):
        advisory.append(
            f"coverage_twin_table_allowlist lists {name!r} but no mapped model "
            "uses that __tablename__ — remove after confirming drop/rename"
        )
    for key in sorted(set(freetext_allow) - freetext_hits):
        advisory.append(
            f"documents_like_freetext_allowlist lists {key!r} but it was not "
            "observed on documents-like models — remove if obsolete"
        )
    for rel in sorted(url_allow):
        if rel == "src/domain/services/href_registry.py":
            continue
        if not (REPO_ROOT / rel).is_file():
            advisory.append(f"document_url_builder_allowlist lists {rel!r} but file is missing")

    critical.extend(_scan_document_url_builders(url_allow))

    stats = {
        "models": len(models),
        "file_home_tables_observed": len(file_home_hits),
        "file_home_tables_baseline": len(file_homes),
        "coverage_twin_hits": len(twin_hits),
        "freetext_hits": len(freetext_hits),
        "url_allowlist": len(url_allow),
        "critical": len(critical),
        "advisory": len(advisory),
    }
    return critical, advisory, stats


def main() -> int:
    critical, advisory, stats = audit()

    print("=== Library anti-dupe gate (F-3 / L-49) ===\n")
    for msg in critical:
        print(f"CRITICAL: {msg}")
    for msg in advisory:
        print(f"advisory: {msg}")

    print(
        f"\nChecked {stats['models']} mapped model(s): "
        f"file_homes={stats['file_home_tables_observed']}/"
        f"{stats['file_home_tables_baseline']}, "
        f"coverage_twins={stats['coverage_twin_hits']}, "
        f"freetext={stats['freetext_hits']}, "
        f"url_allowlist={stats['url_allowlist']}, "
        f"critical={stats['critical']}, advisory={stats['advisory']}"
    )

    if critical:
        print(
            "\nValidation finished with CRITICAL anti-dupe violations.",
            file=sys.stderr,
        )
        return 1

    print("\nNo anti-dupe CRITICAL violations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
