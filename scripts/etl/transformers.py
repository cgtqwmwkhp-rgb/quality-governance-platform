"""
Data Transformers - Quality Governance Platform
Stage 10: Data Foundation

Type-safe transformation functions for ETL data conversion.
No external dependencies - uses Python standard library only.
"""

import re
from datetime import datetime
from typing import Any, Callable, Dict, Optional


class TransformError(Exception):
    """Raised when a transformation fails."""

    def __init__(self, field: str, value: Any, reason: str):
        self.field = field
        self.value = value
        self.reason = reason
        super().__init__(f"Transform error for '{field}': {reason}")


# Enum mappings aligned with OpenAPI contract
INCIDENT_TYPE_MAP = {
    "quality": "quality",
    "safety": "safety",
    "security": "security",
    "environmental": "environmental",
    "near miss": "near_miss",
    "nearmiss": "near_miss",
    "near-miss": "near_miss",
    "other": "other",
    "": "other",
}

SEVERITY_MAP = {
    "critical": "critical",
    "high": "high",
    "medium": "medium",
    "low": "low",
    "1": "critical",
    "2": "high",
    "3": "medium",
    "4": "low",
    "": "medium",
}

INCIDENT_STATUS_MAP = {
    "reported": "reported",
    "open": "reported",
    "new": "reported",
    "in progress": "in_progress",
    "in_progress": "in_progress",
    "investigating": "in_progress",
    "closed": "closed",
    "resolved": "closed",
    "": "reported",
}

COMPLAINT_STATUS_MAP = {
    "received": "received",
    "new": "received",
    "acknowledged": "acknowledged",
    "in progress": "investigating",
    "investigating": "investigating",
    "resolved": "resolved",
    "closed": "closed",
    "": "received",
}

RTA_STATUS_MAP = {
    "draft": "draft",
    "new": "draft",
    "in review": "in_review",
    "in_review": "in_review",
    "approved": "approved",
    "closed": "closed",
    "": "draft",
}

DATE_FORMATS = [
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%m/%d/%Y",
]


def parse_date(value: Any, field: str = "date") -> Optional[str]:
    """Parse date to ISO format."""
    if value is None or str(value).strip() == "":
        return None

    if isinstance(value, datetime):
        return value.date().isoformat()

    value_str = str(value).strip()

    for fmt in DATE_FORMATS:
        try:
            parsed = datetime.strptime(value_str[:19], fmt)
            return parsed.date().isoformat()
        except ValueError:
            continue

    raise TransformError(field, value, "Could not parse date")


def _map_enum(
    value: Any,
    mapping: Dict[str, str],
    field: str,
    default: Optional[str] = None,
) -> str:
    """Generic enum mapper."""
    if value is None:
        value = ""

    normalized = str(value).strip().lower()

    if normalized in mapping:
        return mapping[normalized]

    if default is not None:
        return default

    raise TransformError(field, value, f"Unknown value for {field}")


def map_incident_type(value: Any, field: str = "incident_type") -> str:
    """Map to incident type enum."""
    return _map_enum(value, INCIDENT_TYPE_MAP, field, default="other")


def map_severity(value: Any, field: str = "severity") -> str:
    """Map to severity enum."""
    return _map_enum(value, SEVERITY_MAP, field, default="medium")


def map_status(value: Any, field: str = "status") -> str:
    """Map to incident status enum."""
    return _map_enum(value, INCIDENT_STATUS_MAP, field, default="reported")


def map_complaint_status(value: Any, field: str = "status") -> str:
    """Map to complaint status enum."""
    return _map_enum(value, COMPLAINT_STATUS_MAP, field, default="received")


def map_rta_status(value: Any, field: str = "status") -> str:
    """Map to RTA status enum."""
    return _map_enum(value, RTA_STATUS_MAP, field, default="draft")


def sanitize_text(value: Any, max_length: Optional[int] = None) -> Optional[str]:
    """Clean and normalize text."""
    if value is None:
        return None

    text = str(value).strip()
    if not text:
        return None

    # Normalize whitespace
    text = re.sub(r"\s+", " ", text)

    if max_length and len(text) > max_length:
        text = text[: max_length - 3] + "..."

    return text


# Transformer registry
TRANSFORMER_REGISTRY: Dict[str, Callable] = {
    "parse_date": parse_date,
    "map_incident_type": map_incident_type,
    "map_severity": map_severity,
    "map_status": map_status,
    "map_complaint_status": map_complaint_status,
    "map_rta_status": map_rta_status,
    "sanitize_text": sanitize_text,
}


def get_transformer(name: str) -> Callable:
    """Get transformer function by name."""
    if name not in TRANSFORMER_REGISTRY:
        raise ValueError(f"Unknown transformer: {name}")
    return TRANSFORMER_REGISTRY[name]
