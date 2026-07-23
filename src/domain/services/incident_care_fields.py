"""Normalize medical assistance + emergency services and derive legacy booleans."""

from __future__ import annotations

from typing import Any, Optional

MEDICAL_CODES = frozenset({"none", "self", "first-aider", "gp", "ambulance"})
EMERGENCY_CODES = frozenset({"police", "ambulance", "fire", "recovery"})


def normalize_medical_assistance(value: Any) -> Optional[str]:
    if value is None:
        return None
    code = str(value).strip().lower()
    if not code:
        return None
    # Excel Y/N import compatibility
    if code in {"y", "yes", "true", "1"}:
        return "first-aider"
    if code in {"n", "no", "false", "0"}:
        return "none"
    if code in MEDICAL_CODES:
        return code
    return code[:50]


def normalize_emergency_services(value: Any) -> list[str]:
    if value is None:
        return []
    raw: list[Any]
    if isinstance(value, str):
        raw = [part.strip() for part in value.split(",") if part.strip()]
    elif isinstance(value, (list, tuple, set)):
        raw = list(value)
    else:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        code = str(item).strip().lower()
        if not code or code in seen:
            continue
        if code in {"y", "yes", "true", "1"}:
            # Excel Y without type — attendance unknown; do not invent police.
            continue
        if code not in EMERGENCY_CODES:
            continue
        seen.add(code)
        out.append(code)
    return out


def derive_first_aid_given(medical_assistance: Optional[str]) -> bool:
    code = (medical_assistance or "").strip().lower()
    return bool(code) and code != "none"


def derive_emergency_services_called(emergency_services: Optional[list[str]]) -> bool:
    return bool(emergency_services)


def care_fields_from_submission(reporter_submission: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Promote portal snapshot medical + emergency onto first-class columns."""
    submission = reporter_submission or {}
    medical = normalize_medical_assistance(submission.get("medical_assistance"))
    services = normalize_emergency_services(submission.get("emergency_services"))
    # Legacy portal: medical==ambulance was used as emergency proxy — do not auto-copy.
    return {
        "medical_assistance": medical,
        "emergency_services": services or None,
        "first_aid_given": derive_first_aid_given(medical),
        "emergency_services_called": derive_emergency_services_called(services),
    }
