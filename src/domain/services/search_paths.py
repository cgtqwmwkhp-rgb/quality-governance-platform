"""Map search result entity types to in-app navigation paths."""

from __future__ import annotations

from typing import Optional
from urllib.parse import quote


def build_action_search_path(storage_kind: str, entity_id: int) -> str:
    """Build `/actions/{action_key}` using unified keys (e.g. capa:12, incident_action:3)."""
    key = f"{storage_kind}:{entity_id}"
    return f"/actions/{quote(key, safe='')}"


def build_search_path(
    entity_type: str,
    entity_id: Optional[int],
    *,
    action_key_kind: Optional[str] = None,
    audit_run_id: Optional[int] = None,
    chunk_id: Optional[int] = None,
    page_number: Optional[int] = None,
) -> Optional[str]:
    """Return a frontend route for a search hit, or None if unknown/unlinked."""
    if entity_type == "action" and action_key_kind and entity_id is not None:
        return build_action_search_path(action_key_kind, entity_id)
    if entity_type == "audit" and audit_run_id is not None:
        return f"/audits/{audit_run_id}/execute"
    if entity_id is None:
        return None
    if entity_type in ("document", "document_content"):
        path = f"/documents/{entity_id}"
        params: list[str] = []
        if chunk_id is not None:
            params.append(f"chunk={int(chunk_id)}")
        if page_number is not None:
            params.append(f"page={int(page_number)}")
        if params:
            path = f"{path}?{'&'.join(params)}"
        return path
    mapping = {
        "incident": f"/incidents/{entity_id}",
        "rta": f"/rtas/{entity_id}",
        "complaint": f"/complaints/{entity_id}",
        "near_miss": f"/near-misses/{entity_id}",
        "risk": f"/risk-register/{entity_id}",
        # Finding id alone cannot deep-link; prefer audit_run_id above.
        "audit": "/audits",
        "action": f"/actions/{entity_id}",  # bare id → capa:{id} on FE; prefer action_key_kind
    }
    return mapping.get(entity_type)
