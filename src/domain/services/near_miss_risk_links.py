"""Helpers for near-miss ↔ risk register bidirectional linking."""

from __future__ import annotations

import re
from typing import Optional

NEAR_MISS_RISK_SOURCE_PREFIX = "near_miss:"


def parse_linked_risk_ids(raw: Optional[str]) -> list[int]:
    """Parse comma-separated linked_risk_ids text into unique int IDs."""
    if not raw:
        return []
    ids: list[int] = []
    seen: set[int] = set()
    for part in str(raw).split(","):
        part = part.strip()
        if not part:
            continue
        try:
            value = int(part)
        except ValueError:
            continue
        if value not in seen:
            seen.add(value)
            ids.append(value)
    return ids


def append_linked_risk_id(raw: Optional[str], risk_id: int) -> str:
    """Return updated linked_risk_ids text including risk_id (idempotent)."""
    ids = parse_linked_risk_ids(raw)
    if risk_id not in ids:
        ids.append(risk_id)
    return ",".join(str(i) for i in ids)


def near_miss_risk_source(near_miss_id: int, reference_number: str | None = None) -> str:
    """Canonical risk_source value encoding the originating near miss."""
    ref = (reference_number or "").strip()
    if ref:
        return f"{NEAR_MISS_RISK_SOURCE_PREFIX}{near_miss_id}|{ref}"
    return f"{NEAR_MISS_RISK_SOURCE_PREFIX}{near_miss_id}"


_NEAR_MISS_SOURCE_RE = re.compile(rf"^{re.escape(NEAR_MISS_RISK_SOURCE_PREFIX)}(\d+)(?:\|(.+))?$")


def parse_near_miss_id_from_risk_source(risk_source: Optional[str]) -> Optional[int]:
    """Extract near_miss id from risk_source when encoded by near_miss_risk_source()."""
    if not risk_source:
        return None
    match = _NEAR_MISS_SOURCE_RE.match(str(risk_source).strip())
    if not match:
        return None
    return int(match.group(1))


def near_miss_detail_href(near_miss_id: int) -> str:
    return f"/near-misses/{near_miss_id}"


def risk_register_href(risk_id: int | None = None) -> str:
    if risk_id is None:
        return "/risk-register"
    return f"/risk-register?riskId={risk_id}"
