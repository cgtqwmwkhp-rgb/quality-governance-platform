"""Persist ALL_CLAUSES onto standards/clauses (D14 / WI-1).

CEL keeps the string ``clause_id`` (e.g. ``9001-7.2``). This module upserts a
matching ``clauses.catalogue_key`` so SoA / Standards Library can join without
inventing a second clause registry.

Scheme shells (UVDB B2, Planet Mark) land as ``standards.kind = scheme`` identity
anchors only — UVDB/PM question trees stay in ``uvdb_*`` / ``planet_mark_*`` and
crosswalk via CEL / ``documents.id`` (L-26; no frameworks twin).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, Sequence

from src.domain.services.iso_compliance_service import ALL_CLAUSES, ISOStandard

STANDARD_KIND_ISO = "iso"
STANDARD_KIND_SCHEME = "scheme"
STANDARD_KINDS = frozenset({STANDARD_KIND_ISO, STANDARD_KIND_SCHEME})

COVER_KIND_COVERS = "covers"
COVER_KIND_EVIDENCES = "evidences"
COVER_KINDS = frozenset({COVER_KIND_COVERS, COVER_KIND_EVIDENCES})

# Canonical ISO rows the in-memory catalogue maps onto. Existing DB rows that
# already contain the matcher token are reused (kind stamped iso) rather than
# duplicating under a second code.
ISO_STANDARD_SPECS: tuple[dict[str, Any], ...] = (
    {
        "iso": ISOStandard.ISO_9001,
        "code": "ISO9001",
        "name": "ISO 9001:2015",
        "full_name": "Quality management systems — Requirements",
        "version": "2015",
        "description": "Requirements for a quality management system",
        "matchers": ("9001",),
    },
    {
        "iso": ISOStandard.ISO_14001,
        "code": "ISO14001",
        "name": "ISO 14001:2015",
        "full_name": "Environmental management systems — Requirements with guidance for use",
        "version": "2015",
        "description": "Requirements for an environmental management system",
        "matchers": ("14001",),
    },
    {
        "iso": ISOStandard.ISO_45001,
        "code": "ISO45001",
        "name": "ISO 45001:2018",
        "full_name": "Occupational health and safety management systems — Requirements with guidance for use",
        "version": "2018",
        "description": "Requirements for an OH&S management system",
        "matchers": ("45001",),
    },
    {
        "iso": ISOStandard.ISO_27001,
        "code": "ISO27001",
        "name": "ISO 27001:2022",
        "full_name": "Information security, cybersecurity and privacy protection — Information security management systems — Requirements",
        "version": "2022",
        "description": "Requirements for an information security management system",
        "matchers": ("27001",),
    },
)

SCHEME_STANDARD_SPECS: tuple[dict[str, str], ...] = (
    {
        "code": "UVDB_B2",
        "name": "UVDB Verify B2",
        "full_name": "UVDB Achilles Verify B2 Audit Protocol",
        "version": "11.2",
        "description": "Utilities Vendor Database Verify B2 scheme identity (questions remain in uvdb_*)",
    },
    {
        "code": "PLANET_MARK",
        "name": "Planet Mark",
        "full_name": "Planet Mark Business Certification",
        "version": "GHG",
        "description": "Planet Mark carbon scheme identity (reporting remains in planet_mark_*)",
    },
)


def _normalize(*values: Optional[str]) -> str:
    return " ".join(value or "" for value in values).lower()


def match_iso_standard_row(row: Mapping[str, Any]) -> Optional[ISOStandard]:
    """Return the ISO enum for a standards row, or None when it is not an ISO edition."""
    normalized = _normalize(row.get("code"), row.get("name"), row.get("full_name"))
    for spec in ISO_STANDARD_SPECS:
        if any(token in normalized for token in spec["matchers"]):
            return spec["iso"]
    return None


def catalogue_keys() -> list[str]:
    """Stable list of ALL_CLAUSES ids (the CEL join keys)."""
    return [clause.id for clause in ALL_CLAUSES]


def build_iso_standard_upserts(
    existing_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], dict[ISOStandard, int]]:
    """Plan ISO standard inserts / kind stamps.

    Returns ``(rows_to_insert, iso_to_existing_id)``. Callers that already have a
    matching row should UPDATE ``kind='iso'`` rather than inserting.
    """
    iso_to_id: dict[ISOStandard, int] = {}
    for row in existing_rows:
        matched = match_iso_standard_row(row)
        if matched is not None and matched not in iso_to_id:
            iso_to_id[matched] = int(row["id"])

    to_insert: list[dict[str, Any]] = []
    existing_codes = {str(row["code"]) for row in existing_rows}
    for spec in ISO_STANDARD_SPECS:
        iso: ISOStandard = spec["iso"]
        if iso in iso_to_id:
            continue
        if spec["code"] in existing_codes:
            # Exact code present but matcher missed — treat as found via code.
            continue
        to_insert.append(
            {
                "code": spec["code"],
                "name": spec["name"],
                "full_name": spec["full_name"],
                "version": spec["version"],
                "description": spec["description"],
                "kind": STANDARD_KIND_ISO,
                "is_active": True,
            }
        )
    return to_insert, iso_to_id


def build_scheme_standard_upserts(
    existing_rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return scheme shell rows not already present by code."""
    existing_codes = {str(row["code"]) for row in existing_rows}
    return [
        {
            "code": spec["code"],
            "name": spec["name"],
            "full_name": spec["full_name"],
            "version": spec["version"],
            "description": spec["description"],
            "kind": STANDARD_KIND_SCHEME,
            "is_active": True,
        }
        for spec in SCHEME_STANDARD_SPECS
        if spec["code"] not in existing_codes
    ]


def build_clause_catalogue_rows(
    iso_to_standard_id: Mapping[ISOStandard, int],
) -> list[dict[str, Any]]:
    """Materialise ALL_CLAUSES as clause rows keyed by catalogue_key.

    ``parent_clause_id`` is left null here; callers resolve parent FK in a second
    pass once catalogue_key → id is known.
    """
    rows: list[dict[str, Any]] = []
    for index, clause in enumerate(ALL_CLAUSES):
        standard_id = iso_to_standard_id.get(clause.standard)
        if standard_id is None:
            raise ValueError(f"No standards.id for {clause.standard.value} while seeding catalogue_key={clause.id}")
        rows.append(
            {
                "standard_id": standard_id,
                "catalogue_key": clause.id,
                "clause_number": clause.clause_number[:20],
                "title": clause.title[:300],
                "description": clause.description,
                "level": clause.level,
                "sort_order": index,
                "is_active": True,
                "parent_catalogue_key": clause.parent_clause,
            }
        )
    return rows
