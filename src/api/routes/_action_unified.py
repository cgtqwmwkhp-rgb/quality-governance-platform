"""Shared helpers for unified Actions API (keys, display status, CAPA source mapping)."""

from __future__ import annotations

from src.domain.models.capa import CAPASource

# Stable storage kinds for action_key (globally unique with row id).
STORAGE_INCIDENT_ACTION = "incident_action"
STORAGE_RTA_ACTION = "rta_action"
STORAGE_COMPLAINT_ACTION = "complaint_action"
STORAGE_INVESTIGATION_ACTION = "investigation_action"
STORAGE_CAPA = "capa"
STORAGE_CAPA_ITEM = "capa_item"

# API source_type values that map only to capa_actions (not incident_actions / complaint_actions).
# "investigation" is also CAPA-backed (formal CAPAAction) while InvestigationAction /
# CAPAItem rows are still queried separately when filtering by investigation.
CAPA_ONLY_API_SOURCE_TYPES: frozenset[str] = frozenset(
    {
        "assessment",
        "induction",
        "audit_finding",
        "ncr",
        "risk",
        "management_review",
        "loler_examination",
        "vehicle_defect",
        "regulatory_watch",
        "competence_gap",
        "capa_incident",
        "capa_complaint",
        "near_miss",
        "rta",
        "investigation",
    }
)


def action_key_for(storage_kind: str, row_id: int) -> str:
    return f"{storage_kind}:{row_id}"


def normalize_action_key(key: str) -> str:
    """Accept bare numeric ids as capa:{id} (legacy / UAT deep links like /actions/2)."""
    k = (key or "").strip()
    if k.isdigit():
        return action_key_for(STORAGE_CAPA, int(k))
    return k


def parse_action_key(key: str) -> tuple[str, int]:
    key = normalize_action_key(key)
    if ":" not in key:
        raise ValueError("action_key must be '<kind>:<id>'")
    kind, _, rest = key.partition(":")
    kind = kind.strip()
    if not kind or not rest.strip():
        raise ValueError("invalid action_key")
    try:
        return kind, int(rest.strip())
    except ValueError as exc:
        raise ValueError("action_key id must be an integer") from exc


def capa_api_source_type(capa_source: CAPASource | None) -> str:
    """Map CAPASource enum to unified API source_type string."""
    if capa_source is None:
        return "capa"
    if capa_source == CAPASource.JOB_ASSESSMENT:
        return "assessment"
    if capa_source == CAPASource.INDUCTION:
        return "induction"
    if capa_source == CAPASource.INCIDENT:
        return "capa_incident"
    if capa_source == CAPASource.COMPLAINT:
        return "capa_complaint"
    return capa_source.value


def capa_enum_from_api_filter(api_source_type: str) -> CAPASource | None:
    """Resolve API filter string to CAPASource, or None if not a CAPA-backed filter."""
    s = api_source_type.lower().strip()
    if s == "assessment":
        return CAPASource.JOB_ASSESSMENT
    if s == "induction":
        return CAPASource.INDUCTION
    if s == "capa_incident":
        return CAPASource.INCIDENT
    if s == "capa_complaint":
        return CAPASource.COMPLAINT
    try:
        return CAPASource(s)
    except ValueError:
        return None


def display_status_for(raw_status: str, *, from_capa: bool) -> str:
    """Normalize raw DB status for dashboards and filters (completed / pending verification)."""
    s = (raw_status or "").strip().lower()
    if from_capa:
        if s == "closed":
            return "completed"
        if s == "verification":
            return "pending_verification"
        return s
    if s == "verified":
        return "completed"
    return s
