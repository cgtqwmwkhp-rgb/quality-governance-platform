"""Promote portal injury snapshot fields onto first-class Incident columns."""

from __future__ import annotations

from typing import Any, Optional


def extract_body_parts_from_injuries(injuries: Any) -> list[str]:
    """Normalise portal body-map / injury payload into body_parts labels."""
    if not injuries:
        return []
    parts: list[str] = []
    if isinstance(injuries, list):
        for item in injuries:
            if isinstance(item, str) and item.strip():
                parts.append(item.strip())
                continue
            if not isinstance(item, dict):
                continue
            for key in (
                "regionLabel",
                "region_label",
                "body_part",
                "bodyPart",
                "region",
                "regionId",
                "region_id",
                "id",
                "label",
            ):
                value = item.get(key)
                if isinstance(value, str) and value.strip():
                    parts.append(value.strip())
                    break
            regions = item.get("regions") or item.get("body_parts")
            if isinstance(regions, list):
                for region in regions:
                    if isinstance(region, str) and region.strip():
                        parts.append(region.strip())
                    elif isinstance(region, dict):
                        rid = (
                            region.get("regionLabel")
                            or region.get("label")
                            or region.get("regionId")
                            or region.get("id")
                        )
                        if isinstance(rid, str) and rid.strip():
                            parts.append(rid.strip())
    elif isinstance(injuries, dict):
        for key, value in injuries.items():
            if value and isinstance(key, str):
                parts.append(key.strip())
    # Preserve order, drop empties/dupes
    seen: set[str] = set()
    unique: list[str] = []
    for part in parts:
        normalized = part.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)
    return unique


_TRUTHY_ANSWERS = frozenset({"yes", "y", "true", "t", "1"})
_FALSY_ANSWERS = frozenset({"no", "n", "false", "f", "0"})


def interpret_has_injuries_answer(value: Any) -> bool:
    """Read the portal's answer to "Any injuries sustained?".

    The portal posts this as the string ``"yes"`` or ``"no"``, so ``bool(value)``
    reports True for both -- an unanswered question was the only way to record
    "no injury". Anything unrecognised is treated as True so an answer nobody
    anticipated cannot silently downgrade an injury.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, str):
        answer = value.strip().lower()
        if not answer:
            return False
        if answer in _FALSY_ANSWERS:
            return False
        if answer in _TRUTHY_ANSWERS:
            return True
        return True
    return bool(value)


def promote_injury_fields_from_submission(reporter_submission: Optional[dict[str, Any]]) -> dict[str, Any]:
    """Derive is_injury / body_parts from portal reporter_submission."""
    submission = reporter_submission or {}
    injuries = submission.get("injuries")
    has_injuries_flag = submission.get("has_injuries")
    body_parts = extract_body_parts_from_injuries(injuries)
    # A tapped body part outranks a "no": recorded evidence of an injury wins.
    is_injury = interpret_has_injuries_answer(has_injuries_flag) or bool(body_parts) or bool(injuries)
    return {
        "is_injury": is_injury,
        "body_parts": body_parts or None,
    }
