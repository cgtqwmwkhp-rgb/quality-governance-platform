"""Own-axis Evidence for loaded scheme catalogues (CE / CE+ / IiP).

Int-W5 already seeded requirement axes. This module exposes them as Evidence
trees without stuffing schemes into ``ISOStandard`` and without granting EXACT
share or auto-confirm.

Isolation: ``standards_trap_guard`` and ``standards_ingest_gate`` must not import
this module. Catalogue presence does not flip ingest.
"""

from __future__ import annotations

from typing import Any, Iterable, Optional

from src.domain.services.iso_compliance_service import counts_toward_compliance_coverage
from src.domain.services.standards_requirement_axis import axis_rows, requirement_catalogue_key

#: Publisher-loaded axes that may render Evidence Full/Partial/Gaps.
LOADED_SCHEME_EVIDENCE_IDS: frozenset[str] = frozenset({"ce", "cep", "iip"})

_SCHEME_LABELS: dict[str, dict[str, str]] = {
    "ce": {
        "code": "Cyber Essentials",
        "name": "NCSC Cyber Essentials",
        "description": "Five technical controls. Own axis — not an ISO clause tree. No EXACT share.",
    },
    "cep": {
        "code": "Cyber Essentials Plus",
        "name": "NCSC Cyber Essentials Plus",
        "description": "Same five controls, Plus-verified. Own axis — not an ISO clause tree. No EXACT share.",
    },
    "iip": {
        "code": "Investors in People",
        "name": "We invest in people",
        "description": "Nine 2018 indicators. Own axis — not an ISO clause tree. No EXACT share.",
    },
}


def loaded_scheme_id(standard: Optional[str]) -> Optional[str]:
    if not standard:
        return None
    key = standard.strip().lower()
    return key if key in LOADED_SCHEME_EVIDENCE_IDS else None


def scheme_labels(framework: str) -> dict[str, str]:
    return dict(_SCHEME_LABELS[framework])


def scheme_clause_records(framework: Optional[str] = None) -> list[dict[str, Any]]:
    """Clause-shaped dicts for Evidence trees (id = catalogue_key)."""
    frameworks = (framework,) if framework else tuple(sorted(LOADED_SCHEME_EVIDENCE_IDS))
    out: list[dict[str, Any]] = []
    for fw in frameworks:
        if fw not in LOADED_SCHEME_EVIDENCE_IDS:
            continue
        for row in axis_rows(fw):
            number = str(row.get("clause_number") or "").strip()
            if not number:
                continue
            key = str(row.get("catalogue_key") or requirement_catalogue_key(fw, number))
            out.append(
                {
                    "id": key,
                    "standard": fw,
                    "clause_number": number,
                    "title": str(row.get("title") or number),
                    "description": f"source=requirement-axes-v1; status={row.get('content_status')}",
                    "keywords": [],
                    "parent_clause": None,
                    "level": int(row.get("level") or 1),
                }
            )
    return out


def scheme_clause_by_id(clause_id: str) -> Optional[dict[str, Any]]:
    wanted = (clause_id or "").strip()
    if not wanted:
        return None
    for row in scheme_clause_records():
        if row["id"] == wanted:
            return row
    return None


def _counts_for_keys(evidence_links: Iterable[Any], keys: set[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for link in evidence_links:
        if not counts_toward_compliance_coverage(
            getattr(link, "signal_type", None),
            getattr(link, "status", None),
        ):
            continue
        clause_id = str(getattr(link, "clause_id", "") or "")
        if clause_id in keys:
            counts[clause_id] = counts.get(clause_id, 0) + 1
    return counts


def scheme_standard_coverage(evidence_links: Iterable[Any], framework: str) -> dict[str, Any]:
    """ISO-shaped by_standard block, scored only against this scheme's axis."""
    clauses = scheme_clause_records(framework)
    keys = {c["id"] for c in clauses}
    counts = _counts_for_keys(evidence_links, keys)
    full = sum(1 for c in clauses if counts.get(c["id"], 0) >= 2)
    partial = sum(1 for c in clauses if counts.get(c["id"], 0) == 1)
    total = len(clauses)
    return {
        "total": total,
        "covered": full,
        "partial_coverage": partial,
        "percentage": round((full + partial * 0.5) / total * 100, 1) if total else 0,
    }


def scheme_coverage_payload(evidence_links: Iterable[Any], framework: Optional[str] = None) -> dict[str, Any]:
    frameworks = (framework,) if framework else tuple(sorted(LOADED_SCHEME_EVIDENCE_IDS))
    clauses: list[dict[str, Any]] = []
    for fw in frameworks:
        clauses.extend(scheme_clause_records(fw))
    keys = {c["id"] for c in clauses}
    counts = _counts_for_keys(evidence_links, keys)
    full = [c for c in clauses if counts.get(c["id"], 0) >= 2]
    partial = [c for c in clauses if counts.get(c["id"], 0) == 1]
    gaps = [c for c in clauses if counts.get(c["id"], 0) == 0]
    total = len(clauses)
    by_standard = {fw: scheme_standard_coverage(evidence_links, fw) for fw in frameworks}
    return {
        "total_clauses": total,
        "full_coverage": len(full),
        "partial_coverage": len(partial),
        "gaps": len(gaps),
        "coverage_percentage": round((len(full) + len(partial) * 0.5) / total * 100, 1) if total else 0,
        "gap_clauses": [
            {
                "clause_id": c["id"],
                "clause_number": c["clause_number"],
                "title": c["title"],
                "standard": c["standard"],
            }
            for c in gaps
        ],
        "by_standard": by_standard,
    }


def scheme_audit_report(
    evidence_links: Iterable[Any],
    framework: Optional[str] = None,
    *,
    include_evidence_details: bool = True,
) -> dict[str, Any]:
    coverage = scheme_coverage_payload(evidence_links, framework)
    links = list(evidence_links)
    by_clause: dict[str, list[Any]] = {}
    for link in links:
        by_clause.setdefault(str(getattr(link, "clause_id", "") or ""), []).append(link)

    clause_details = []
    for clause in scheme_clause_records(framework):
        evidence = by_clause.get(clause["id"], [])
        conformance = [
            e
            for e in evidence
            if counts_toward_compliance_coverage(getattr(e, "signal_type", None), getattr(e, "status", None))
        ]
        status = "full" if len(conformance) >= 2 else "partial" if len(conformance) == 1 else "gap"
        detail: dict[str, Any] = {
            "clause_id": clause["id"],
            "clause_number": clause["clause_number"],
            "title": clause["title"],
            "description": clause["description"],
            "standard": clause["standard"],
            "status": status,
            "evidence_count": len(conformance),
            "operational_signal_count": len(evidence) - len(conformance),
        }
        if include_evidence_details:
            detail["evidence"] = [
                {
                    "entity_type": getattr(e, "entity_type", None),
                    "entity_id": getattr(e, "entity_id", None),
                    "clause_id": getattr(e, "clause_id", None),
                    "signal_type": getattr(e, "signal_type", None),
                }
                for e in evidence
            ]
        clause_details.append(detail)

    return {
        **coverage,
        "clauses": clause_details,
        "honesty_note": (
            "Scheme report uses the loaded requirement axis only. "
            "It does not invent EXACT share or ISO clause coverage."
        ),
    }


def merge_scheme_into_iso_coverage(iso_payload: dict[str, Any], evidence_links: Iterable[Any]) -> dict[str, Any]:
    """Keep ISO totals; add loaded-scheme keys to by_standard for Evidence cards."""
    merged = dict(iso_payload)
    by_standard = dict(iso_payload.get("by_standard") or {})
    scheme = scheme_coverage_payload(evidence_links)
    by_standard.update(scheme["by_standard"])
    merged["by_standard"] = by_standard
    return merged
