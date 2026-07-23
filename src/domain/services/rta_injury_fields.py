"""Derive RTA third_party_injured rollup from structured third_parties JSON."""

from __future__ import annotations

from typing import Any, Optional


def parties_from_third_parties(third_parties: Any) -> list[dict[str, Any]]:
    if third_parties is None:
        return []
    if isinstance(third_parties, list):
        return [p for p in third_parties if isinstance(p, dict)]
    if isinstance(third_parties, dict):
        raw = third_parties.get("parties")
        if isinstance(raw, list):
            return [p for p in raw if isinstance(p, dict)]
    return []


def derive_third_party_injured(
    third_parties: Any,
    *,
    explicit: Optional[bool] = None,
) -> Optional[bool]:
    """Return rollup flag for third-party injury.

    - explicit True/False wins when provided (Excel Y/N, portal top-level answer)
    - else True if any party.injured
    - else False if parties exist and none injured
    - else None (unknown / no parties)
    """
    if explicit is not None:
        return bool(explicit)
    parties = parties_from_third_parties(third_parties)
    if not parties:
        return None
    if any(bool(p.get("injured")) for p in parties):
        return True
    return False


def seed_third_parties_for_injury(
    third_parties: Any,
    *,
    injured: bool,
) -> Optional[dict[str, Any]]:
    """Ensure JSON has at least one injured party when Excel only has Y/N."""
    parties = parties_from_third_parties(third_parties)
    if injured and not parties:
        return {"parties": [{"injured": True}]}
    if isinstance(third_parties, dict) and "parties" in third_parties:
        return third_parties
    if parties:
        return {"parties": parties}
    return None
