"""Library WK-1 / L-47 — framework evidence pack builder (pure, fixture-backed).

Builds ISO 9001 / UVDB B2 / Planet Mark evidence packs from **typed row dicts**.
This module is intentionally isolated from ``compliance.py``, CEL ORM models,
standards/clauses migrations, and governed_knowledge writers so it can land
while WI-1 (#1687) owns those conflict paths.

Post-WI-1 LIVE: wire a thin adapter that projects CEL rows (incl. ``cover_kind``,
``confirmed_by_id`` / ``confirmed_at``, scheme shells) into
:class:`FrameworkEvidenceRow` and call these builders. Do **not** invent
``document_coverage_claims`` / frameworks twin tables (F-3 / D15).
"""

from __future__ import annotations

from typing import Any, Literal, Mapping, Sequence, TypedDict

FrameworkId = Literal["iso9001", "uvdb_b2", "planet_mark"]

PACK_VERSION = "lib-wk1-framework-1.0"

FRAMEWORK_META: dict[FrameworkId, dict[str, str]] = {
    "iso9001": {
        "code": "ISO_9001",
        "label": "ISO 9001:2015",
        "kind": "iso",
        "scheme_aliases": "iso9001,iso_9001,iso 9001,9001",
    },
    "uvdb_b2": {
        "code": "UVDB_B2",
        "label": "UVDB Verify B2",
        "kind": "scheme",
        "scheme_aliases": "uvdb_b2,uvdb-b2,uvdb b2,uvdb",
    },
    "planet_mark": {
        "code": "PLANET_MARK",
        "label": "Planet Mark",
        "kind": "scheme",
        "scheme_aliases": "planet_mark,planet-mark,planet mark,pm",
    },
}

_CONFORMANCE_SIGNALS = frozenset({"evidence", "", "none"})
# legacy null/empty signal_type remains conformance-eligible (GKB WL1 honesty)


class FrameworkEvidenceRow(TypedDict, total=False):
    """Typed CEL-shaped export row (dict-only; no ORM dependency)."""

    id: str
    entity_type: str
    entity_id: str
    clause_id: str
    catalogue_key: str | None
    cover_kind: str  # covers | evidences (WI-1); default evidences when absent
    signal_type: str | None
    scheme: str | None
    standard: str | None
    status: str | None
    confirmed_at: str | None
    confirmed_by_id: int | None
    confirmed_by: str | None
    created_at: str | None
    created_by: str | None
    rationale: str | None
    confidence: float | None
    title: str | None
    notes: str | None
    document_issue_state: str | None  # CURRENT | SUPERSEDED | DRAFT | …


def _norm(value: str | None) -> str:
    return (value or "").strip().lower().replace("-", "_").replace(" ", "_")


def _aliases(framework: FrameworkId) -> set[str]:
    raw = FRAMEWORK_META[framework]["scheme_aliases"]
    return {_norm(part) for part in raw.split(",")} | {_norm(FRAMEWORK_META[framework]["code"])}


def row_matches_framework(row: Mapping[str, Any], framework: FrameworkId) -> bool:
    """True when scheme/standard aliases match the target framework."""
    aliases = _aliases(framework)
    scheme = _norm(row.get("scheme") if isinstance(row.get("scheme"), str) else None)
    standard = _norm(row.get("standard") if isinstance(row.get("standard"), str) else None)
    return scheme in aliases or standard in aliases


def _normalize_signal(signal_type: str | None) -> str:
    if signal_type is None:
        return ""
    return str(signal_type).strip().lower()


def counts_toward_conformance(signal_type: str | None) -> bool:
    signal = _normalize_signal(signal_type)
    if signal in {"nonconformity", "gap", "opportunity"}:
        return False
    return signal in _CONFORMANCE_SIGNALS or signal == "evidence"


def serialize_framework_pack_row(row: Mapping[str, Any]) -> dict[str, Any]:
    """Project one typed row into the stable pack export shape."""
    signal = _normalize_signal(row.get("signal_type") if isinstance(row.get("signal_type"), str) else None)
    cover_kind = row.get("cover_kind") or "evidences"
    if not isinstance(cover_kind, str) or not cover_kind.strip():
        cover_kind = "evidences"
    return {
        "id": row.get("id"),
        "entity_type": row.get("entity_type"),
        "entity_id": row.get("entity_id"),
        "clause_id": row.get("clause_id"),
        "catalogue_key": row.get("catalogue_key"),
        "cover_kind": cover_kind.strip().lower(),
        "signal_type": signal or "evidence",
        "conformance_eligible": counts_toward_conformance(
            row.get("signal_type") if isinstance(row.get("signal_type"), str) else None
        ),
        "scheme": row.get("scheme"),
        "standard": row.get("standard"),
        "status": row.get("status"),
        "confirmed_at": row.get("confirmed_at"),
        "confirmed_by_id": row.get("confirmed_by_id"),
        "confirmed_by": row.get("confirmed_by"),
        "created_at": row.get("created_at"),
        "created_by": row.get("created_by"),
        "rationale": row.get("rationale") or row.get("notes"),
        "confidence": row.get("confidence"),
        "title": row.get("title"),
        "notes": row.get("notes"),
        "document_issue_state": row.get("document_issue_state"),
    }


def build_framework_evidence_pack(
    rows: Sequence[Mapping[str, Any]],
    *,
    framework: FrameworkId,
    generated_at: str,
    exported_by: str | None = None,
    organization_name: str | None = None,
    include_nonconformity: bool = False,
) -> dict[str, Any]:
    """Build a deterministic framework evidence pack from typed rows.

    ``generated_at`` is caller-supplied so fixtures can freeze timestamps.
    """
    if framework not in FRAMEWORK_META:
        raise ValueError(f"Unsupported framework: {framework}")

    meta = FRAMEWORK_META[framework]
    matched = [row for row in rows if row_matches_framework(row, framework)]

    conformance_rows: list[dict[str, Any]] = []
    operational_rows: list[dict[str, Any]] = []
    for row in matched:
        serialized = serialize_framework_pack_row(row)
        if counts_toward_conformance(
            row.get("signal_type") if isinstance(row.get("signal_type"), str) else None
        ):
            conformance_rows.append(serialized)
        else:
            operational_rows.append(serialized)

    if include_nonconformity:
        evidence_export = conformance_rows + operational_rows
        exclusion_mode = "labelled_in_pack"
    else:
        evidence_export = list(conformance_rows)
        exclusion_mode = "excluded_from_conformance_evidence"

    current_count = sum(
        1
        for row in evidence_export
        if str(row.get("document_issue_state") or "").upper() == "CURRENT"
    )

    return {
        "pack_version": PACK_VERSION,
        "framework": {
            "id": framework,
            "code": meta["code"],
            "label": meta["label"],
            "kind": meta["kind"],
        },
        "generated_at": generated_at,
        "exported_by": exported_by,
        "organization_name": organization_name,
        "provenance_policy": {
            "source": "typed_cel_rows",
            "wi1_fields": ["cover_kind", "confirmed_by_id", "confirmed_at", "catalogue_key"],
            "wire_status": "builder_ready_awaiting_wi1_adapter",
            "signal_honesty": (
                "Only signal_type=evidence (and legacy null/empty) is conformance-eligible. "
                "nonconformity/gap/opportunity are operational assessor signals."
            ),
            "nonconformity_mode": exclusion_mode,
            "include_nonconformity": include_nonconformity,
            "no_coverage_twin_tables": True,
        },
        "counts": {
            "matched_rows": len(matched),
            "conformance_evidence_links": len(conformance_rows),
            "operational_signal_links": len(operational_rows),
            "exported_evidence_links": len(evidence_export),
            "current_issue_links": current_count,
        },
        "evidence_links": evidence_export,
        "operational_signals": operational_rows,
    }


def build_iso9001_evidence_pack(
    rows: Sequence[Mapping[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    return build_framework_evidence_pack(rows, framework="iso9001", **kwargs)


def build_uvdb_b2_evidence_pack(
    rows: Sequence[Mapping[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    return build_framework_evidence_pack(rows, framework="uvdb_b2", **kwargs)


def build_planet_mark_evidence_pack(
    rows: Sequence[Mapping[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    return build_framework_evidence_pack(rows, framework="planet_mark", **kwargs)
