"""Stable accident-type keys for H&S workbook imports."""

from __future__ import annotations

import re

RTA_COLLISION_TYPE_MAP = {
    "rear end": "rear_end",
    "rear-end": "rear_end",
    "rear-end collision": "rear_end",
    "rear-end collisions": "rear_end",
    "head on": "head_on",
    "head-on": "head_on",
    "head-on collision": "head_on",
    "head-on collisions": "head_on",
    "side impact": "side_impact",
    "side-impact": "side_impact",
    "side-impact crash": "side_impact",
    "side-impact crashes": "side_impact",
    "animal-related": "animal",
    "animal-related collision": "animal",
    "animal-related collisions": "animal",
    "hit and run": "hit_and_run",
    "reversing": "reversing",
    "reversing / manoeuvring": "reversing",
    "object strike": "object_strike",
    "stationary object": "object_strike",
    "single vehicle": "single_vehicle",
    "single-vehicle accidents": "single_vehicle",
    "other": "other",
}


def normalize_rta_collision_type(value: str | None) -> str | None:
    if not value:
        return None
    # Prefer the first segment when Excel concatenates types with " / "
    primary = value.split("/")[0].strip()
    normal = re.sub(r"\s+", " ", primary.strip().lower())
    if normal in RTA_COLLISION_TYPE_MAP:
        return RTA_COLLISION_TYPE_MAP[normal]
    for key, mapped in RTA_COLLISION_TYPE_MAP.items():
        if key in normal or normal in key:
            return mapped
    return re.sub(r"[^a-z0-9]+", "_", normal).strip("_") or None
