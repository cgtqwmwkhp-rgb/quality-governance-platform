#!/usr/bin/env python3
"""WI-2 / L-32 — read-only migrate prep / dry-run planner.

Plans how occurrence rows would link to Register ``documents.id`` **without**
writing, and **without** requiring the deferred WI-2 alembic head.

Inputs are in-memory fixtures (unit tests / steward review). An optional
``--from-json PATH`` loads a steward export with the shapes below.

Carbon evidence row::

    {"id": 1, "tenant_id": 1, "document_name": "...", "storage_key": "...",
     "file_path": "...", "file_hash": "..."}

UVDB response row::

    {"id": 9, "tenant_id": 1, "documents_presented": ["Policy.pdf", 12, {"title": "X"}]}

Evidence asset row::

    {"id": 3, "tenant_id": 1, "storage_key": "...", "original_filename": "...",
     "checksum_sha256": "..."}

Register document row (match corpus)::

    {"id": 12, "tenant_id": 1, "file_name": "Policy.pdf", "file_path": "...",
     "checksum_sha256": "..."}

Match order (never silent-create Register rows in this prep)::

1. Exact content hash (``file_hash`` / ``checksum_sha256``)
2. Exact ``storage_key`` or ``file_path``
3. Same tenant + case-insensitive filename / label
4. Else ``unmatched`` → steward queue

Usage::

    PYTHONPATH=. python3 -m scripts.governance.library.file_homes_migrate_prep --demo
    PYTHONPATH=. python3 -m scripts.governance.library.file_homes_migrate_prep --from-json export.json

Exit ``0`` always on successful planning (informational). Exit ``2`` on bad args.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass
class LinkPlan:
    home: str
    source_id: int | str | None
    tenant_id: int | str | None
    status: str  # matched | unmatched | already_shaped | empty
    match_method: str | None
    document_id: int | None
    label: str | None = None
    notes: str | None = None
    projected: dict[str, Any] | None = None


@dataclass
class PrepReport:
    carbon_evidence: list[LinkPlan] = field(default_factory=list)
    uvdb_presented: list[LinkPlan] = field(default_factory=list)
    evidence_assets: list[LinkPlan] = field(default_factory=list)
    counters: dict[str, int] = field(default_factory=dict)
    deferred: list[str] = field(default_factory=list)

    def summarise(self) -> None:
        buckets = {
            "carbon_matched": 0,
            "carbon_unmatched": 0,
            "uvdb_matched": 0,
            "uvdb_unmatched": 0,
            "uvdb_already_shaped": 0,
            "uvdb_empty": 0,
            "ea_matched": 0,
            "ea_unmatched": 0,
        }
        for plan in self.carbon_evidence:
            key = "carbon_matched" if plan.status == "matched" else "carbon_unmatched"
            buckets[key] += 1
        for plan in self.uvdb_presented:
            if plan.status == "matched":
                buckets["uvdb_matched"] += 1
            elif plan.status == "already_shaped":
                buckets["uvdb_already_shaped"] += 1
            elif plan.status == "empty":
                buckets["uvdb_empty"] += 1
            else:
                buckets["uvdb_unmatched"] += 1
        for plan in self.evidence_assets:
            key = "ea_matched" if plan.status == "matched" else "ea_unmatched"
            buckets[key] += 1
        self.counters = buckets
        self.deferred = [
            "Live alembic revising 20261030_lib_wi1_cel (held until WI-1 LIVE)",
            "ORM document_id columns on carbon_evidence / evidence_assets",
            "Production dual-write + promote routes",
            "F-3 allowlist shrink for carbon_evidence / evidence_assets",
            "CEL evidences wiring for UVDB/PM occurrence rows (uses WI-1 cover_kind)",
        ]


def _norm_name(value: Any) -> str:
    return str(value or "").strip().lower()


def _as_int(value: Any) -> int | None:
    if value is None or value is False:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    return None


def index_documents(documents: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Build match indexes: hash / path / filename → document rows."""
    by_hash: dict[str, list[dict[str, Any]]] = {}
    by_path: dict[str, list[dict[str, Any]]] = {}
    by_name: dict[str, list[dict[str, Any]]] = {}
    for doc in documents:
        tenant = doc.get("tenant_id")
        digest = doc.get("checksum_sha256") or doc.get("file_hash")
        if digest:
            by_hash.setdefault(f"{tenant}:{str(digest).lower()}", []).append(doc)
        for path_key in ("file_path", "storage_key"):
            path = doc.get(path_key)
            if path:
                by_path.setdefault(f"{tenant}:{path}", []).append(doc)
        name = doc.get("file_name") or doc.get("title")
        if name:
            by_name.setdefault(f"{tenant}:{_norm_name(name)}", []).append(doc)
    return {"hash": by_hash, "path": by_path, "name": by_name}


def match_document(
    *,
    tenant_id: Any,
    file_hash: Any = None,
    storage_key: Any = None,
    file_path: Any = None,
    name: Any = None,
    indexes: dict[str, list[dict[str, Any]]],
) -> tuple[dict[str, Any] | None, str | None]:
    if file_hash:
        hits = indexes["hash"].get(f"{tenant_id}:{str(file_hash).lower()}") or []
        if len(hits) == 1:
            return hits[0], "content_hash"
    for path in (storage_key, file_path):
        if not path:
            continue
        hits = indexes["path"].get(f"{tenant_id}:{path}") or []
        if len(hits) == 1:
            return hits[0], "storage_or_file_path"
    if name:
        hits = indexes["name"].get(f"{tenant_id}:{_norm_name(name)}") or []
        if len(hits) == 1:
            return hits[0], "filename"
    return None, None


def plan_carbon_evidence(
    rows: Iterable[dict[str, Any]],
    indexes: dict[str, list[dict[str, Any]]],
) -> list[LinkPlan]:
    plans: list[LinkPlan] = []
    for row in rows:
        doc, method = match_document(
            tenant_id=row.get("tenant_id"),
            file_hash=row.get("file_hash"),
            storage_key=row.get("storage_key"),
            file_path=row.get("file_path"),
            name=row.get("document_name"),
            indexes=indexes,
        )
        if doc is not None:
            plans.append(
                LinkPlan(
                    home="carbon_evidence",
                    source_id=row.get("id"),
                    tenant_id=row.get("tenant_id"),
                    status="matched",
                    match_method=method,
                    document_id=_as_int(doc.get("id")),
                    label=row.get("document_name"),
                    notes="Would set carbon_evidence.document_id after WI-2 schema",
                )
            )
        else:
            plans.append(
                LinkPlan(
                    home="carbon_evidence",
                    source_id=row.get("id"),
                    tenant_id=row.get("tenant_id"),
                    status="unmatched",
                    match_method=None,
                    document_id=None,
                    label=row.get("document_name"),
                    notes="Steward promote to Register — no silent create",
                )
            )
    return plans


def normalise_presented_element(
    element: Any,
    *,
    tenant_id: Any,
    indexes: dict[str, list[dict[str, Any]]],
    response_id: Any,
) -> LinkPlan:
    """Project one documents_presented element toward {document_id, label}."""
    if element is None or element == "":
        return LinkPlan(
            home="uvdb_documents_presented",
            source_id=response_id,
            tenant_id=tenant_id,
            status="empty",
            match_method=None,
            document_id=None,
            projected=None,
            notes="Empty element skipped",
        )

    if isinstance(element, dict):
        doc_id = _as_int(element.get("document_id") if "document_id" in element else element.get("id"))
        label = element.get("label") or element.get("title") or element.get("name")
        if doc_id is not None and (
            "document_id" in element or set(element.keys()) <= {"document_id", "label", "id", "title", "name"}
        ):
            # Prefer explicit document_id key; plain {"id": N} counts as already shaped.
            projected = {"document_id": doc_id, "label": label}
            return LinkPlan(
                home="uvdb_documents_presented",
                source_id=response_id,
                tenant_id=tenant_id,
                status="already_shaped" if "document_id" in element else "matched",
                match_method="embedded_document_id",
                document_id=doc_id,
                label=str(label) if label is not None else None,
                projected=projected,
            )
        # Dict without resolvable id — try label match.
        doc, method = match_document(tenant_id=tenant_id, name=label, indexes=indexes)
        if doc is not None:
            projected = {"document_id": _as_int(doc.get("id")), "label": label}
            return LinkPlan(
                home="uvdb_documents_presented",
                source_id=response_id,
                tenant_id=tenant_id,
                status="matched",
                match_method=method,
                document_id=_as_int(doc.get("id")),
                label=str(label) if label is not None else None,
                projected=projected,
            )
        return LinkPlan(
            home="uvdb_documents_presented",
            source_id=response_id,
            tenant_id=tenant_id,
            status="unmatched",
            match_method=None,
            document_id=None,
            label=str(label) if label is not None else None,
            projected={"document_id": None, "label": label},
            notes="Steward file then re-run",
        )

    if isinstance(element, int) or (isinstance(element, str) and element.strip().isdigit()):
        doc_id = _as_int(element)
        return LinkPlan(
            home="uvdb_documents_presented",
            source_id=response_id,
            tenant_id=tenant_id,
            status="matched",
            match_method="numeric_document_id",
            document_id=doc_id,
            projected={"document_id": doc_id, "label": None},
        )

    # Free-text title / filename
    label = str(element)
    doc, method = match_document(tenant_id=tenant_id, name=label, indexes=indexes)
    if doc is not None:
        return LinkPlan(
            home="uvdb_documents_presented",
            source_id=response_id,
            tenant_id=tenant_id,
            status="matched",
            match_method=method,
            document_id=_as_int(doc.get("id")),
            label=label,
            projected={"document_id": _as_int(doc.get("id")), "label": label},
        )
    return LinkPlan(
        home="uvdb_documents_presented",
        source_id=response_id,
        tenant_id=tenant_id,
        status="unmatched",
        match_method=None,
        document_id=None,
        label=label,
        projected={"document_id": None, "label": label},
        notes="Steward file then re-run",
    )


def plan_uvdb_presented(
    rows: Iterable[dict[str, Any]],
    indexes: dict[str, list[dict[str, Any]]],
) -> list[LinkPlan]:
    plans: list[LinkPlan] = []
    for row in rows:
        presented = row.get("documents_presented")
        if presented is None:
            plans.append(
                LinkPlan(
                    home="uvdb_documents_presented",
                    source_id=row.get("id"),
                    tenant_id=row.get("tenant_id"),
                    status="empty",
                    match_method=None,
                    document_id=None,
                    notes="NULL documents_presented",
                )
            )
            continue
        if not isinstance(presented, list):
            plans.append(
                LinkPlan(
                    home="uvdb_documents_presented",
                    source_id=row.get("id"),
                    tenant_id=row.get("tenant_id"),
                    status="unmatched",
                    match_method=None,
                    document_id=None,
                    notes=f"Unexpected type {type(presented).__name__} — expected list",
                )
            )
            continue
        if not presented:
            plans.append(
                LinkPlan(
                    home="uvdb_documents_presented",
                    source_id=row.get("id"),
                    tenant_id=row.get("tenant_id"),
                    status="empty",
                    match_method=None,
                    document_id=None,
                    notes="Empty list",
                )
            )
            continue
        for element in presented:
            plans.append(
                normalise_presented_element(
                    element,
                    tenant_id=row.get("tenant_id"),
                    indexes=indexes,
                    response_id=row.get("id"),
                )
            )
    return plans


def plan_evidence_assets(
    rows: Iterable[dict[str, Any]],
    indexes: dict[str, list[dict[str, Any]]],
) -> list[LinkPlan]:
    plans: list[LinkPlan] = []
    for row in rows:
        # Only plan a Library link when the row opts in (filed) or matches a Register blob.
        filed = bool(row.get("filed_to_library") or row.get("document_id"))
        existing = _as_int(row.get("document_id"))
        if existing is not None:
            plans.append(
                LinkPlan(
                    home="evidence_assets",
                    source_id=row.get("id"),
                    tenant_id=row.get("tenant_id"),
                    status="matched",
                    match_method="existing_document_id",
                    document_id=existing,
                    label=row.get("original_filename") or row.get("title"),
                    notes="Already carries document_id (post-schema or export)",
                )
            )
            continue
        doc, method = match_document(
            tenant_id=row.get("tenant_id"),
            file_hash=row.get("checksum_sha256"),
            storage_key=row.get("storage_key"),
            name=row.get("original_filename") or row.get("title"),
            indexes=indexes,
        )
        if doc is not None and (filed or method in {"content_hash", "storage_or_file_path"}):
            plans.append(
                LinkPlan(
                    home="evidence_assets",
                    source_id=row.get("id"),
                    tenant_id=row.get("tenant_id"),
                    status="matched",
                    match_method=method,
                    document_id=_as_int(doc.get("id")),
                    label=row.get("original_filename") or row.get("title"),
                    notes="Optional Library link — case storage_key retained",
                )
            )
        else:
            plans.append(
                LinkPlan(
                    home="evidence_assets",
                    source_id=row.get("id"),
                    tenant_id=row.get("tenant_id"),
                    status="unmatched",
                    match_method=None,
                    document_id=None,
                    label=row.get("original_filename") or row.get("title"),
                    notes=(
                        "Remain case-scoped (no Library link required)"
                        if not filed
                        else "Filed flag set but no Register match — steward promote"
                    ),
                )
            )
    return plans


def build_report(payload: dict[str, Any]) -> PrepReport:
    documents = list(payload.get("documents") or [])
    indexes = index_documents(documents)
    report = PrepReport(
        carbon_evidence=plan_carbon_evidence(payload.get("carbon_evidence") or [], indexes),
        uvdb_presented=plan_uvdb_presented(payload.get("uvdb_audit_responses") or [], indexes),
        evidence_assets=plan_evidence_assets(payload.get("evidence_assets") or [], indexes),
    )
    report.summarise()
    return report


def demo_payload() -> dict[str, Any]:
    return {
        "documents": [
            {
                "id": 100,
                "tenant_id": 1,
                "file_name": "Fuel Card July.pdf",
                "file_path": "library/tenant-1/fuel-card-july.pdf",
                "checksum_sha256": "abc123",
            },
            {
                "id": 101,
                "tenant_id": 1,
                "file_name": "H&S Policy.pdf",
                "file_path": "library/tenant-1/hs-policy.pdf",
                "checksum_sha256": "def456",
            },
        ],
        "carbon_evidence": [
            {
                "id": 1,
                "tenant_id": 1,
                "document_name": "Fuel Card July.pdf",
                "storage_key": "planet-mark/tenant-1/year-2025/abc12345-Fuel Card July.pdf",
                "file_hash": "abc123",
            },
            {
                "id": 2,
                "tenant_id": 1,
                "document_name": "Orphan Utility Bill.pdf",
                "storage_key": "planet-mark/tenant-1/year-2025/zzzz-orphan.pdf",
                "file_hash": "orphan999",
            },
        ],
        "uvdb_audit_responses": [
            {
                "id": 9,
                "tenant_id": 1,
                "documents_presented": [
                    "H&S Policy.pdf",
                    100,
                    {"document_id": 101, "label": "H&S Policy.pdf"},
                    {"title": "Missing Doc.docx"},
                ],
            },
            {"id": 10, "tenant_id": 1, "documents_presented": []},
        ],
        "evidence_assets": [
            {
                "id": 3,
                "tenant_id": 1,
                "storage_key": "library/tenant-1/fuel-card-july.pdf",
                "original_filename": "Fuel Card July.pdf",
                "checksum_sha256": "abc123",
                "filed_to_library": True,
            },
            {
                "id": 4,
                "tenant_id": 1,
                "storage_key": "evidence/near-miss/4/photo.jpg",
                "original_filename": "photo.jpg",
                "checksum_sha256": "photo111",
            },
        ],
    }


def report_as_dict(report: PrepReport) -> dict[str, Any]:
    return {
        "programme": "WI-2 / L-32",
        "mode": "dry-run (no writes)",
        "carbon_evidence": [asdict(p) for p in report.carbon_evidence],
        "uvdb_presented": [asdict(p) for p in report.uvdb_presented],
        "evidence_assets": [asdict(p) for p in report.evidence_assets],
        "counters": report.counters,
        "deferred_until_wi1_live": report.deferred,
    }


def _print_human(report: PrepReport) -> None:
    data = report_as_dict(report)
    print("WI-2 / L-32 migrate prep (dry-run — no writes)")
    print()
    for section in ("carbon_evidence", "uvdb_presented", "evidence_assets"):
        print(f"## {section}")
        for plan in data[section]:
            print(
                f"  source={plan['source_id']!r} status={plan['status']} "
                f"method={plan['match_method']} document_id={plan['document_id']} "
                f"label={plan['label']!r}"
            )
        print()
    print("Counters:", json.dumps(data["counters"], sort_keys=True))
    print("Deferred until WI-1 LIVE:")
    for item in data["deferred_until_wi1_live"]:
        print(f"  - {item}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--demo", action="store_true", help="Run against built-in fixture payload")
    parser.add_argument("--from-json", type=Path, help="Load steward export JSON")
    parser.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    parser.add_argument(
        "--apply",
        action="store_true",
        help=argparse.SUPPRESS,  # deliberately unsupported — refuse loudly
    )
    args = parser.parse_args(argv)

    if args.apply:
        print("ERROR: read-only migrate prep — --apply is not supported", file=sys.stderr)
        return 2

    if args.from_json and args.demo:
        print("ERROR: choose --demo or --from-json, not both", file=sys.stderr)
        return 2
    if not args.from_json and not args.demo:
        print("ERROR: provide --demo or --from-json PATH", file=sys.stderr)
        return 2

    if args.from_json:
        payload = json.loads(args.from_json.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            print("ERROR: export root must be a JSON object", file=sys.stderr)
            return 2
    else:
        payload = demo_payload()

    report = build_report(payload)
    if args.json:
        print(json.dumps(report_as_dict(report), indent=2, sort_keys=True))
    else:
        _print_human(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
