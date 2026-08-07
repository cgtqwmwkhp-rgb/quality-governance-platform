"""Curated UK health & safety regulation map for Compliance Schedule AI assist.

Used when no matching ``standards`` catalogue row exists. Codes are stable
identifiers for dedupe/reconcile against DB ``Standard.code`` when a row is
later seeded. Labels must fit ``compliance_requirements.regulatory_basis``
(String 255).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional, Sequence, Tuple


@dataclass(frozen=True)
class UkRegulationEntry:
    code: str
    label: str
    keywords: Tuple[str, ...]
    taxonomy_prefixes: Tuple[str, ...] = ()
    statutory_boost: bool = True


# ~16 common UK H&S / premises obligations. Keyword match is lowercased substring.
UK_REGULATORY_BASIS_MAP: Tuple[UkRegulationEntry, ...] = (
    UkRegulationEntry(
        code="FSO2005",
        label="Regulatory Reform (Fire Safety) Order 2005",
        keywords=(
            "fire risk assessment",
            "fire risk",
            "fra",
            "fire safety order",
            "fire drill",
            "evacuation",
            "fire inspection",
            "fire alarm",
            "emergency lighting",
            "extinguisher",
        ),
        taxonomy_prefixes=("03",),
    ),
    UkRegulationEntry(
        code="HASAWA1974",
        label="Health and Safety at Work etc. Act 1974",
        keywords=(
            "health and safety at work",
            "hasawa",
            "hswa",
            "general duties",
            "safe system of work",
        ),
    ),
    UkRegulationEntry(
        code="MHSWR1999",
        label="Management of Health and Safety at Work Regulations 1999",
        keywords=(
            "management of health and safety",
            "mhswr",
            "risk assessment programme",
            "competent person",
        ),
    ),
    UkRegulationEntry(
        code="EAWR1989",
        label="Electricity at Work Regulations 1989",
        keywords=(
            "eicr",
            "fixed electrical",
            "fixed wire",
            "electrical inspection",
            "electricity at work",
            "eawr",
        ),
        taxonomy_prefixes=("04.02",),
    ),
    UkRegulationEntry(
        code="LOLER1998",
        label="Lifting Operations and Lifting Equipment Regulations 1998",
        keywords=(
            "loler",
            "thorough examination",
            "lifting equipment",
            "lifting operations",
        ),
    ),
    UkRegulationEntry(
        code="PUWER1998",
        label="Provision and Use of Work Equipment Regulations 1998",
        keywords=("puwer", "work equipment", "machinery guarding"),
    ),
    UkRegulationEntry(
        code="PSSR2000",
        label="Pressure Systems Safety Regulations 2000",
        keywords=("pssr", "pressure system", "pressure vessel", "written scheme"),
    ),
    UkRegulationEntry(
        code="COSHH2002",
        label="Control of Substances Hazardous to Health Regulations 2002",
        keywords=("coshh", "hazardous substance", "lev", "local exhaust"),
        taxonomy_prefixes=("04.06",),
    ),
    UkRegulationEntry(
        code="CAR2012",
        label="Control of Asbestos Regulations 2012",
        keywords=("asbestos", "acm", "asbestos management"),
    ),
    UkRegulationEntry(
        code="L8",
        label="ACOP L8 — Legionnaires' disease: The control of legionella bacteria",
        keywords=("legionella", "l8", "water hygiene", "cooling tower"),
    ),
    UkRegulationEntry(
        code="RIDDOR2013",
        label="Reporting of Injuries, Diseases and Dangerous Occurrences Regulations 2013",
        keywords=("riddor", "reportable injury", "dangerous occurrence"),
    ),
    UkRegulationEntry(
        code="WHSWR1992",
        label="Workplace (Health, Safety and Welfare) Regulations 1992",
        keywords=("workplace regulations", "whswr", "welfare facilities"),
    ),
    UkRegulationEntry(
        code="GSIUR1998",
        label="Gas Safety (Installation and Use) Regulations 1998",
        keywords=("gas safety", "gsiur", "gas appliance", "boiler inspection"),
    ),
    UkRegulationEntry(
        code="DSEAR2002",
        label="Dangerous Substances and Explosive Atmospheres Regulations 2002",
        keywords=("dsear", "explosive atmosphere", "flammable substance"),
    ),
    UkRegulationEntry(
        code="WAHR2005",
        label="Work at Height Regulations 2005",
        keywords=("work at height", "wahr", "working at height", "fall from height"),
    ),
    UkRegulationEntry(
        code="FA1981",
        label="Health and Safety (First-Aid) Regulations 1981",
        keywords=("first aid", "first-aid", "first aider"),
    ),
    UkRegulationEntry(
        code="ELCI1969",
        label="Employers' Liability (Compulsory Insurance) Act 1969",
        keywords=("employers liability", "elci", "employers' liability"),
    ),
)


def match_uk_regulations(
    text: str,
    *,
    taxonomy_id: Optional[str] = None,
    statutory: bool = False,
    min_score: float = 0.5,
) -> list[tuple[UkRegulationEntry, float]]:
    """Return ranked curated matches for free-text obligation context.

    Scoring is deterministic (no AI): keyword hits and taxonomy prefix boosts.
    """
    normalised = _normalise(text)
    if not normalised:
        return []

    hits: list[tuple[UkRegulationEntry, float]] = []
    for entry in UK_REGULATORY_BASIS_MAP:
        score = _score_entry(entry, normalised, taxonomy_id=taxonomy_id, statutory=statutory)
        if score >= min_score:
            hits.append((entry, round(min(score, 0.99), 3)))

    hits.sort(key=lambda item: (-item[1], item[0].code))
    return hits


def lookup_by_code(code: str) -> Optional[UkRegulationEntry]:
    needle = (code or "").strip().upper()
    for entry in UK_REGULATORY_BASIS_MAP:
        if entry.code.upper() == needle:
            return entry
    return None


def all_codes() -> Sequence[str]:
    return tuple(entry.code for entry in UK_REGULATORY_BASIS_MAP)


def _normalise(text: str) -> str:
    return " ".join((text or "").lower().replace("-", " ").split())


def _score_entry(
    entry: UkRegulationEntry,
    text: str,
    *,
    taxonomy_id: Optional[str],
    statutory: bool,
) -> float:
    keyword_hits = sum(1 for kw in entry.keywords if kw in text)
    if keyword_hits == 0 and not _taxonomy_boost(entry, taxonomy_id):
        return 0.0

    score = 0.55 + (0.12 * min(keyword_hits, 3))
    if keyword_hits >= 2:
        score += 0.08
    # Strong single keyword that is itself a distinctive phrase
    for kw in entry.keywords:
        if len(kw) >= 12 and kw in text:
            score = max(score, 0.9)
            break
    if _taxonomy_boost(entry, taxonomy_id):
        score = max(score, 0.82 if keyword_hits else 0.72)
        score += 0.05
    if statutory and entry.statutory_boost and keyword_hits:
        score += 0.03
    return score


def _taxonomy_boost(entry: UkRegulationEntry, taxonomy_id: Optional[str]) -> bool:
    if not taxonomy_id or not entry.taxonomy_prefixes:
        return False
    tid = taxonomy_id.strip()
    return any(
        tid == prefix or tid.startswith(f"{prefix}.") or tid.startswith(prefix) for prefix in entry.taxonomy_prefixes
    )


def assert_map_integrity(entries: Iterable[UkRegulationEntry] = UK_REGULATORY_BASIS_MAP) -> None:
    """Structural checks used by unit tests."""
    codes = [e.code for e in entries]
    if len(codes) != len(set(codes)):
        raise AssertionError("UK regulatory map codes must be unique")
    for entry in entries:
        if not entry.label or len(entry.label) > 255:
            raise AssertionError(f"invalid label for {entry.code}")
        if not entry.keywords:
            raise AssertionError(f"keywords required for {entry.code}")
