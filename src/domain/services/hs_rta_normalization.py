"""Stable accident-type keys for H&S workbook imports."""

import re

RTA_COLLISION_TYPE_MAP = {
    "rear end": "rear_end",
    "rear-end": "rear_end",
    "head on": "head_on",
    "head-on": "head_on",
    "side impact": "side_impact",
    "reversing": "reversing",
    "single vehicle": "single_vehicle",
    "other": "other",
}


def normalize_rta_collision_type(value: str | None) -> str | None:
    if not value:
        return None
    normal = re.sub(r"\s+", " ", value.strip().lower())
    return RTA_COLLISION_TYPE_MAP.get(normal, re.sub(r"[^a-z0-9]+", "_", normal).strip("_") or None)
