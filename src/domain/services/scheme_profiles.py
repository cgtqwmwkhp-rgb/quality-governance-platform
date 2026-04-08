"""Scheme-specific validation profiles for audit document analysis.

Each profile defines domain constraints (valid score ranges, expected sections,
outcome rules) that catch extraction errors a generic parser would miss.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)


@dataclass
class SchemeSection:
    name: str
    min_score: float = 0
    max_score: float = 100
    required: bool = False


@dataclass
class SchemeProfile:
    scheme_id: str
    label: str
    score_type: str | None  # "percentage", "numeric", or None (no scores)
    overall_min: float | None = None
    overall_max: float | None = None
    sections: list[SchemeSection] = field(default_factory=list)
    typical_section_count: int | None = None
    valid_outcomes: list[str] = field(default_factory=lambda: ["pass", "fail", "review_required"])
    notes: str = ""


SCHEME_PROFILES: dict[str, SchemeProfile] = {
    "achilles_uvdb": SchemeProfile(
        scheme_id="achilles_uvdb",
        label="Achilles / UVDB",
        score_type="percentage",
        overall_min=0,
        overall_max=100,
        sections=[
            SchemeSection("Health & Safety", 0, 100, required=True),
            SchemeSection("Environment", 0, 100, required=True),
            SchemeSection("Quality", 0, 100, required=True),
            SchemeSection("Corporate Social Responsibility", 0, 100, required=True),
        ],
        typical_section_count=4,
    ),
    "iso": SchemeProfile(
        scheme_id="iso",
        label="ISO Audit",
        score_type=None,
        valid_outcomes=["pass", "fail", "review_required"],
        notes="ISO audits use conformity/nonconformity status, not numeric scores.",
    ),
    "planet_mark": SchemeProfile(
        scheme_id="planet_mark",
        label="Planet Mark",
        score_type="percentage",
        overall_min=0,
        overall_max=100,
        sections=[
            SchemeSection("Scope 1 – Direct Emissions", 0, 16, required=False),
            SchemeSection("Scope 2 – Indirect Energy", 0, 16, required=False),
            SchemeSection("Scope 3 – Value Chain", 0, 16, required=False),
            SchemeSection("Data Quality", 0, 16, required=False),
            SchemeSection("Improvement Actions", 0, 100, required=False),
        ],
        valid_outcomes=["pass", "fail", "review_required", "certified", "in_progress", "not_certified"],
        notes=(
            "Planet Mark uses a carbon footprint certification model. "
            "Score represents reduction % vs baseline. Data quality is scored 0-16 "
            "(Scope 1&2 target ≥12/16, Scope 3 target ≥11/16). "
            "Outcomes: 'certified' = certification awarded, 'in_progress' = assessment underway."
        ),
    ),
    "smeta": SchemeProfile(
        scheme_id="smeta",
        label="SMETA / SEDEX",
        score_type=None,
        sections=[
            SchemeSection("Labour Standards", required=True),
            SchemeSection("Health & Safety", required=True),
            SchemeSection("Environment", required=True),
            SchemeSection("Business Ethics", required=True),
        ],
        typical_section_count=4,
        notes="SMETA uses finding-based assessment, not numeric scores.",
    ),
    "ecovadis": SchemeProfile(
        scheme_id="ecovadis",
        label="EcoVadis",
        score_type="numeric",
        overall_min=0,
        overall_max=100,
        sections=[
            SchemeSection("Environment", 0, 100),
            SchemeSection("Labor & Human Rights", 0, 100),
            SchemeSection("Ethics", 0, 100),
            SchemeSection("Sustainable Procurement", 0, 100),
        ],
        typical_section_count=4,
    ),
    "customer_other": SchemeProfile(
        scheme_id="customer_other",
        label="Customer / Third-Party Audit",
        score_type="percentage",
        overall_min=0,
        overall_max=100,
        notes="Generic profile for customer/supplier audits. Sections vary by customer.",
    ),
}


def canonical_scheme_id(scheme: str) -> str:
    """Map granular or hyphenated ISO ids onto the shared ISO validation profile."""
    s = (scheme or "").strip().lower()
    if s == "iso" or s.startswith("iso_") or s.startswith("iso-"):
        return "iso"
    return s


def get_profile(scheme: str) -> SchemeProfile | None:
    return SCHEME_PROFILES.get(canonical_scheme_id(scheme))


def validate_against_scheme(
    scheme: str,
    overall_score: float | None,
    max_score: float | None,
    score_percentage: float | None,
    score_breakdown: list[dict] | None,
) -> list[str]:
    """Validate extracted scores against scheme constraints. Returns warnings."""
    profile = get_profile(scheme)
    if not profile:
        return []

    warnings: list[str] = []

    if profile.score_type is None and overall_score is not None:
        warnings.append(
            f"{profile.label} audits typically do not use numeric scores. "
            f"Extracted score {overall_score} may be a date or reference number."
        )

    if profile.score_type == "percentage" and score_percentage is not None:
        if profile.overall_min is not None and score_percentage < profile.overall_min:
            warnings.append(f"Score {score_percentage}% is below minimum {profile.overall_min}% for {profile.label}")
        if profile.overall_max is not None and score_percentage > profile.overall_max:
            warnings.append(f"Score {score_percentage}% exceeds maximum {profile.overall_max}% for {profile.label}")

    if score_breakdown and profile.sections:
        for item in score_breakdown:
            label = str(item.get("label", "")).lower()
            score_val = item.get("score")
            for section in profile.sections:
                sec_lower = section.name.lower()
                is_match = (
                    sec_lower in label or label in sec_lower or SequenceMatcher(None, label, sec_lower).ratio() > 0.7
                )
                if is_match:
                    if score_val is not None:
                        s = float(str(score_val))
                        if s < section.min_score or s > section.max_score:
                            warnings.append(
                                f"Score {s} for '{item.get('label')}' outside valid range "
                                f"[{section.min_score}-{section.max_score}] for {profile.label}"
                            )
                    break

    if profile.typical_section_count and score_breakdown:
        actual = len(score_breakdown)
        expected = profile.typical_section_count
        if actual != expected:
            warnings.append(f"Expected {expected} scored sections for {profile.label}, found {actual}")

    if profile.sections:
        required_names = [s.name for s in profile.sections if s.required]
        if required_names and score_breakdown:
            found_labels = {str(item.get("label", "")).lower() for item in score_breakdown}
            for req in required_names:
                if not any(req.lower() in fl for fl in found_labels):
                    warnings.append(f"Required section '{req}' not found in {profile.label} extraction")

    return warnings
