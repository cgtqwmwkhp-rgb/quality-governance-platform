"""Assemble investigation content for a customer pack (INV-C13).

The generated pack used to copy ``investigation.data["sections"]`` only — usually
the source incident. Findings rows (C7), 5-Whys/RCA (C10) and CAPA (C11) never
entered that map under the HSG245 ids the UI omits (``findings``, ``root-cause``,
``capa``, ``event-details``), so an approved omit could remove nothing and the PDF
reprinted the incident.

This module is the pack generator's investigation half:

* serialise findings / RCA / CAPA into those pack keys without inventing text
* map HSG245 omit ids onto the keys the pack actually emits, including the source
  ``section_*`` keys that stand in for ``event-details``
* load those rows tenant-scoped for the generate path

INV-C16 adds one more overlay to the same RCA key: the stored ICAM contributing
factors, structured, so the pack renderer can draw the diagram from the payload
it already has. They are serialised **into the stored content** rather than read
at render time on purpose — the renderer sees only the stored, already-redacted
pack, which is the property that stops it showing what an omit withheld, and the
content checksum then covers the diagram as well as the text.

The PDF renderer still only draws what it is handed. This module does not query
the timeline (C15) and does not invent a fishbone or a fifth taxonomy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Optional, Sequence

from sqlalchemy import String, cast, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.capa import CAPAAction, CAPASource
from src.domain.models.investigation import InvestigationRun
from src.domain.services.investigation_factors_service import FactorSnapshot, InvestigationFactorsService
from src.domain.services.investigation_findings_service import InvestigationFindingsService
from src.domain.services.investigation_rca_service import InvestigationRcaService

# Pack keys this PR introduces. UI HSG245 ids stay as they are (C12 owns Detail).
PACK_SECTION_FINDINGS = "findings"
PACK_SECTION_ROOT_CAUSE = "root-cause"
PACK_SECTION_CAPA = "capa"

# Structured ICAM factors inside the RCA pack section (INV-C16). A field on the
# existing section, not a section of its own: contributing factors are part of
# the root-cause analysis, and giving them their own pack key would need a new
# HSG245 omit id for something an existing omit already withholds.
PACK_FIELD_ICAM_FACTORS = "icam_factors"

# Template keys that correspond to each HSG245 pack section. Findings and RCA
# are dual-write sources, so their legacy strings are skipped when an overlay is
# supplied. Corrective-action prose is independent of CAPAAction rows and must
# remain visible alongside the CAPA overlay.
_FINDINGS_SOURCE_KEYS = frozenset({"section_3_investigation_findings", PACK_SECTION_FINDINGS})
_RCA_SOURCE_KEYS = frozenset({"section_4_root_cause", "rca", PACK_SECTION_ROOT_CAUSE})
_CAPA_SOURCE_KEYS = frozenset({"section_5_corrective_actions", PACK_SECTION_CAPA})

# HSG245 omit id → pack keys that withholding that id must actually remove.
# ``event-details`` also expands to residual source ``section_*`` keys present on
# the run (see :func:`expand_omitted_pack_keys`).
HSG245_PACK_ALIASES: dict[str, frozenset[str]] = {
    "event-details": frozenset({"section_1_details", "event-details"}),
    "immediate-actions": frozenset({"section_2_immediate_actions", "immediate-actions"}),
    "findings": _FINDINGS_SOURCE_KEYS,
    "root-cause": _RCA_SOURCE_KEYS,
    "hsg245-analysis": frozenset({"section_4b_hsg245_analysis", "hsg245-analysis"}),
    "capa": _CAPA_SOURCE_KEYS,
    "fishbone": frozenset({"section_6_fishbone", "fishbone"}),
    "management-review": frozenset({"section_7_management_system_review", "management-review"}),
    "signoff": frozenset({"section_signoff", "signoff"}),
}

_OVERLAY_KEYS = frozenset({PACK_SECTION_FINDINGS, PACK_SECTION_ROOT_CAUSE, PACK_SECTION_CAPA})

# Keys claimed by a named HSG245 omit other than event-details. Residual source
# keys (typically ``section_1_details``) are what an event-details omit withholds.
_CLAIMED_BY_NAMED_OMIT: frozenset[str] = frozenset().union(
    *(aliases for omit_id, aliases in HSG245_PACK_ALIASES.items() if omit_id != "event-details")
)


@dataclass(frozen=True)
class InvestigationPackSources:
    """Tenant-scoped rows the pack generator may render. Empty is empty, not invented."""

    findings: list[Any]
    rca: Optional[dict[str, Any]]
    capa_actions: list[Any]
    #: INV-C12 ICAM factors for the C16 diagram. ``None`` means they were not
    #: consulted — a fail-closed load and an investigation with no factors are
    #: not the same fact, and only the second one can honestly print "none".
    factors: Optional[FactorSnapshot] = None


def _tenants_match(investigation: Any, tenant_id: Any) -> bool:
    record_tenant = getattr(investigation, "tenant_id", None)
    investigation_id = getattr(investigation, "id", None)
    if investigation_id is None or record_tenant is None or tenant_id is None:
        return False
    try:
        return int(record_tenant) == int(tenant_id)
    except (TypeError, ValueError):
        return False


def _usable_text(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    return ""


def iter_source_section_items(investigation: Any) -> list[tuple[str, Any]]:
    """The source ``data.sections`` entries, in stored order. Dict or list shape."""
    source_data: Any = getattr(investigation, "data", None)
    if not isinstance(source_data, dict):
        return []
    raw_sections = source_data.get("sections", {})
    if isinstance(raw_sections, dict):
        return [(str(key), value) for key, value in raw_sections.items()]
    if not isinstance(raw_sections, list):
        return []
    items: list[tuple[str, Any]] = []
    for idx, entry in enumerate(raw_sections):
        if not isinstance(entry, dict):
            continue
        section_key = str(entry.get("id") or entry.get("section_id") or f"section_{idx}")
        fields = entry.get("fields") if isinstance(entry.get("fields"), dict) else entry
        items.append((section_key, fields))
    return items


def event_details_pack_keys(present_keys: Iterable[str]) -> set[str]:
    """Source keys an ``event-details`` omit must withhold.

    The UI id is ``event-details``; stored incident sections are ``section_1_details``
    (and any other ``section_*`` key not claimed by findings / RCA / CAPA / the
    other named HSG245 omits). Only keys actually present are returned, so the
    mapping cannot invent a section to remove.
    """
    present = {str(key) for key in present_keys}
    matched = set(HSG245_PACK_ALIASES["event-details"]) & present
    for key in present:
        if key in _CLAIMED_BY_NAMED_OMIT or key in _OVERLAY_KEYS:
            continue
        if key.startswith("section_"):
            matched.add(key)
    return matched


def expand_omitted_pack_keys(approved_omits: Iterable[str], present_keys: Iterable[str]) -> set[str]:
    """Turn approved omit ids (HSG245 or stored keys) into pack keys to withhold.

    Each approved id is kept as a literal so a stored ``section_1_details`` omit
    still matches. HSG245 ids expand to their aliases. ``event-details`` also
    expands to the source ``section_*`` keys actually present.
    """
    present = {str(key) for key in present_keys}
    withheld: set[str] = set()
    for raw in approved_omits:
        if raw is None:
            continue
        omit_id = str(raw)
        if not omit_id:
            continue
        withheld.add(omit_id)
        aliases = HSG245_PACK_ALIASES.get(omit_id)
        if aliases:
            withheld.update(aliases)
        if omit_id == "event-details":
            withheld.update(event_details_pack_keys(present))
    return withheld


def source_keys_replaced_by_overlay(
    *,
    findings: Optional[Sequence[Any]],
    rca: Optional[Mapping[str, Any]],
    capa_actions: Optional[Sequence[Any]],
) -> set[str]:
    """Dual-write source keys replaced by an overlay.

    ``section_5_corrective_actions`` is not a CAPAAction dual-write target, so
    loading CAPA rows (including the usual empty list) must not hide its prose.
    """
    replaced: set[str] = set()
    if findings is not None:
        replaced.update(_FINDINGS_SOURCE_KEYS - {PACK_SECTION_FINDINGS})
    if rca is not None:
        replaced.update(_RCA_SOURCE_KEYS - {PACK_SECTION_ROOT_CAUSE})
    return replaced


def _finding_body(row: Any) -> str:
    if isinstance(row, str):
        return row.strip()
    if isinstance(row, Mapping):
        return _usable_text(row.get("body"))
    return _usable_text(getattr(row, "body", None))


def serialize_findings_section(findings: Sequence[Any]) -> dict[str, Any]:
    """Findings as a list of bodies. Empty list is empty — nothing is invented."""
    items = [{"body": body} for row in findings if (body := _finding_body(row))]
    return {"items": items}


def _optional_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _why_entry(raw: Any) -> Optional[dict[str, Any]]:
    if not isinstance(raw, Mapping):
        return None
    level = _optional_int(raw.get("level"))
    if level is None:
        return None
    why = _usable_text(raw.get("why"))
    answer = _usable_text(raw.get("answer"))
    evidence = _usable_text(raw.get("evidence"))
    if not why and not answer and not evidence:
        return None
    entry: dict[str, Any] = {"level": level, "why": why, "answer": answer}
    if evidence:
        entry["evidence"] = evidence
    return entry


def _stored_enum_value(value: Any) -> Any:
    """The stored value behind an enum member; anything else is itself."""
    return value.value if hasattr(value, "value") else value


def serialize_icam_factors(snapshot: FactorSnapshot) -> dict[str, Any]:
    """The stored ICAM factors as the pack payload carries them (INV-C16).

    Keys mirror :meth:`InvestigationFactor.as_payload` minus ``investigation_id``
    — the pack is already about one investigation, and repeating its primary key
    on every factor would put a database id in front of a customer for nothing.

    ``unmapped_categories`` and ``unpresentable`` are INV-C12's own counts of
    what that surface could not present: a cause stored under a pre-DEC-1 6M
    key, an entry that is not an object, an entry with no words. They are
    carried so the pack can state the count. Nothing is recategorised here, and
    nothing is dropped without being counted.

    Order is the snapshot's order — ICAM category order, then the order the
    investigator added them — so regenerating a pack cannot reshuffle the
    diagram or change the content checksum for no reason.
    """
    return {
        "factors": [
            {
                "id": int(factor.id or 0),
                "category": _stored_enum_value(factor.category),
                "cause": factor.cause,
                "sub_causes": list(factor.sub_causes),
                "depth": _stored_enum_value(factor.depth) if factor.depth is not None else None,
            }
            for factor in snapshot.factors
        ],
        "unmapped_categories": list(snapshot.unmapped_categories),
        "unpresentable": int(snapshot.unreadable_total or 0),
    }


def serialize_rca_section(rca: Mapping[str, Any], *, factors: Optional[FactorSnapshot] = None) -> dict[str, Any]:
    """5-Whys, root cause, leftover contributing-factor *text*, and the ICAM factors.

    ``factors`` is the tenant-scoped INV-C12 snapshot. ``None`` means the factors
    were not consulted, and then no ``icam_factors`` key is emitted at all —
    which is not the same as an empty diagram. A pack generated before INV-C16
    never asked, so claiming "no contributing factors are recorded" for it would
    be asserting a fact about the investigation that nothing checked.

    The leftover ``contributing_factors`` text stays alongside the structure
    until C18 retires the string readers. The two are not independent: INV-C12
    derives that text from these same factors on every mutation, so they say the
    same thing in two shapes rather than disagreeing.
    """
    contributing = rca.get("contributing_factors")
    if isinstance(contributing, list):
        contributing_text = "\n".join(_usable_text(part) for part in contributing if _usable_text(part))
    else:
        contributing_text = _usable_text(contributing)

    whys: list[dict[str, Any]] = []
    raw_whys = rca.get("whys")
    if isinstance(raw_whys, list):
        for raw in raw_whys:
            entry = _why_entry(raw)
            if entry is not None:
                whys.append(entry)

    section: dict[str, Any] = {
        "problem_statement": _usable_text(rca.get("problem_statement")),
        "whys": whys,
        "root_cause": _usable_text(rca.get("root_cause")),
        "contributing_factors": contributing_text,
    }
    if factors is not None:
        section[PACK_FIELD_ICAM_FACTORS] = serialize_icam_factors(factors)
    return section


def _capa_item(row: Any) -> Optional[dict[str, Any]]:
    if isinstance(row, Mapping):
        title = _usable_text(row.get("title"))
        reference = _usable_text(row.get("reference") or row.get("reference_number"))
        why_level = row.get("why_level")
    else:
        title = _usable_text(getattr(row, "title", None))
        reference = _usable_text(getattr(row, "reference_number", None) or getattr(row, "reference", None))
        why_level = getattr(row, "why_level", None)
    if not title and not reference:
        return None
    item: dict[str, Any] = {"title": title, "reference": reference}
    parsed_why = _optional_int(why_level)
    if parsed_why is not None:
        item["why_level"] = parsed_why
    return item


def serialize_capa_section(capa_actions: Sequence[Any]) -> dict[str, Any]:
    """CAPA title / reference / why_level. Empty list is empty — no invented CAPA."""
    items = [item for row in capa_actions if (item := _capa_item(row)) is not None]
    return {"items": items}


def overlay_investigation_sections(
    *,
    findings: Optional[Sequence[Any]] = None,
    rca: Optional[Mapping[str, Any]] = None,
    capa_actions: Optional[Sequence[Any]] = None,
    factors: Optional[FactorSnapshot] = None,
) -> dict[str, dict[str, Any]]:
    """Investigation sections keyed by HSG245 pack ids. ``None`` means that overlay was not loaded.

    ``factors`` rides on the RCA section rather than being a section of its own,
    so it is emitted only when the RCA overlay is. On the generate path the two
    always arrive together — :func:`load_investigation_pack_sources` returns an
    RCA payload whenever the tenant matches — and a caller that loads factors
    without RCA gets no diagram rather than an invented root-cause section.
    """
    overlay: dict[str, dict[str, Any]] = {}
    if findings is not None:
        overlay[PACK_SECTION_FINDINGS] = serialize_findings_section(findings)
    if rca is not None:
        overlay[PACK_SECTION_ROOT_CAUSE] = serialize_rca_section(rca, factors=factors)
    if capa_actions is not None:
        overlay[PACK_SECTION_CAPA] = serialize_capa_section(capa_actions)
    return overlay


async def load_investigation_pack_sources(
    db: AsyncSession,
    *,
    investigation: InvestigationRun,
    tenant_id: int,
    actor_id: Optional[int] = None,
) -> InvestigationPackSources:
    """Load tenant-scoped findings, RCA, CAPA and ICAM factors for this run.

    Fail closed: a missing tenant, a mismatch, or another organisation's rows
    are empty sources, never a leak. Findings and RCA conversion is the same
    lazy path the workspace uses — leftover strings become rows rather than
    being invented as pack prose.

    The ICAM factors come from the same tenant-scoped reader the C12 editor uses
    (``InvestigationFactorsService.snapshot``), which re-filters on ``tenant_id``
    itself and returns an empty snapshot for another organisation's diagram. The
    diagram is therefore built from the same rows the investigator edits, not
    from a second copy of them.
    """
    if not _tenants_match(investigation, tenant_id):
        return InvestigationPackSources(findings=[], rca=None, capa_actions=[], factors=None)

    scoped_tenant = int(tenant_id)
    findings = await InvestigationFindingsService.list_findings(
        db, investigation=investigation, tenant_id=scoped_tenant
    )
    rca = await InvestigationRcaService.get_workspace(
        db,
        investigation=investigation,
        tenant_id=scoped_tenant,
        actor_id=actor_id,
    )
    factors = await InvestigationFactorsService.snapshot(
        db,
        investigation=investigation,
        tenant_id=scoped_tenant,
    )
    capa_result = await db.execute(
        select(CAPAAction)
        .where(
            CAPAAction.tenant_id == scoped_tenant,
            cast(CAPAAction.source_type, String) == CAPASource.INVESTIGATION.value,
            CAPAAction.source_id == int(investigation.id),
        )
        .order_by(CAPAAction.id.asc())
    )
    capa_actions = list(capa_result.scalars().all())
    return InvestigationPackSources(
        findings=list(findings),
        rca=rca,
        capa_actions=capa_actions,
        factors=factors,
    )


__all__ = [
    "HSG245_PACK_ALIASES",
    "InvestigationPackSources",
    "PACK_FIELD_ICAM_FACTORS",
    "PACK_SECTION_CAPA",
    "PACK_SECTION_FINDINGS",
    "PACK_SECTION_ROOT_CAUSE",
    "event_details_pack_keys",
    "expand_omitted_pack_keys",
    "iter_source_section_items",
    "load_investigation_pack_sources",
    "overlay_investigation_sections",
    "serialize_capa_section",
    "serialize_findings_section",
    "serialize_icam_factors",
    "serialize_rca_section",
    "source_keys_replaced_by_overlay",
]
