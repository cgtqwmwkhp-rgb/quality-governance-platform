"""Map search result entity types to in-app navigation paths."""

from __future__ import annotations

from typing import Optional


def build_search_path(entity_type: str, entity_id: Optional[int]) -> Optional[str]:
    """Return a frontend route for a search hit, or None if unknown/unlinked."""
    if entity_id is None:
        return None
    mapping = {
        "incident": f"/incidents/{entity_id}",
        "rta": f"/rtas/{entity_id}",
        "complaint": f"/complaints/{entity_id}",
        "near_miss": f"/near-misses/{entity_id}",
        "risk": f"/risk-register/{entity_id}",
        "audit": "/audits",
        "action": f"/actions/{entity_id}",
        "document": f"/documents/{entity_id}",
    }
    return mapping.get(entity_type)
