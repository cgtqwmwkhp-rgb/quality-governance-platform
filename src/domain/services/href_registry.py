"""Central SPA deep-link path builders for Entity360 / Doc Graph hops.

Call sites must never string-build hop ``href`` values — use these helpers
(or thin wrappers that delegate here). Generalises the risk ``case_type_href``
pattern so every module shares one registry.
"""

from __future__ import annotations

from typing import Callable, Mapping

# ---------------------------------------------------------------------------
# Entity path builders (registry)
# ---------------------------------------------------------------------------

_ENTITY_PATHS: dict[str, Callable[[int], str]] = {
    "document": lambda entity_id: f"/documents/{entity_id}",
    "risk": lambda entity_id: f"/risk-register/{entity_id}",
    "incident": lambda entity_id: f"/incidents/{entity_id}",
    "near_miss": lambda entity_id: f"/near-misses/{entity_id}",
    "rta": lambda entity_id: f"/rtas/{entity_id}",
    "complaint": lambda entity_id: f"/complaints/{entity_id}",
    "capa": lambda entity_id: f"/actions/{entity_id}",
    "action": lambda entity_id: f"/actions/{entity_id}",
    "clause": lambda entity_id: f"/compliance/evidence?clause={entity_id}",
    "job_step": lambda entity_id: f"/job-lifecycle/steps/{entity_id}",
}


def register_href(entity_type: str, builder: Callable[[int], str]) -> None:
    """Register or replace a path builder (tests / future producers)."""
    key = entity_type.strip().lower()
    if not key:
        raise ValueError("entity_type must be non-empty")
    _ENTITY_PATHS[key] = builder


def href_for(entity_type: str, entity_id: int) -> str:
    """Return the SPA deep-link for ``(entity_type, entity_id)``.

    Unknown types fall back to ``/{type}/{id}`` so hops remain navigable without
    inventing parallel string builders at call sites.
    """
    key = entity_type.strip().lower()
    builder = _ENTITY_PATHS.get(key)
    if builder is not None:
        return builder(entity_id)
    return f"/{key}/{entity_id}"


def document_href(document_id: int) -> str:
    """SPA deep-link for a library document."""
    return href_for("document", document_id)


def risk_href(risk_id: int) -> str:
    """SPA deep-link for an enterprise risk."""
    return href_for("risk", risk_id)


def case_type_href(case_type: str, case_id: int) -> str:
    """Deep-link path for a case_risk_links case_type (compat wrapper)."""
    return href_for(case_type, case_id)


def audit_finding_href(*, run_id: int, finding_id: int | None = None) -> str:
    """Deep-link into an audit run execute surface for a finding.

    Finding id is reserved for future deep anchors; today the execute page is
    the stable navigation target used by risk upstream.
    """
    _ = finding_id
    return f"/audits/{run_id}/execute"


def registered_entity_types() -> frozenset[str]:
    """Known entity types with dedicated builders (excluding fallback)."""
    return frozenset(_ENTITY_PATHS.keys())


def registry_snapshot() -> Mapping[str, Callable[[int], str]]:
    """Read-only view of builders (tests)."""
    return dict(_ENTITY_PATHS)


__all__ = [
    "audit_finding_href",
    "case_type_href",
    "document_href",
    "href_for",
    "register_href",
    "registered_entity_types",
    "registry_snapshot",
    "risk_href",
]
