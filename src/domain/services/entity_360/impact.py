"""Publish ImpactBundle — server DTO that blocks publish when degraded."""

from __future__ import annotations

from typing import Any, Optional

from src.domain.services.entity_360.composer import Entity360Service, public_hop
from src.domain.services.entity_360.types import utc_now


async def build_impact_bundle(
    *,
    db: Any,
    tenant_id: int,
    document_id: int,
    user: Any,
) -> dict[str, Any]:
    """Compose an ImpactBundle for a library document publish preview.

    Uses the same hop/composer path as Entity360. ``complete=false`` (any
    producer ``error``) MUST block publish — no silent Promise.allSettled path.
    """
    service = Entity360Service(db)
    bundle = await service.compose(
        tenant_id=tenant_id,
        entity_type="document",
        entity_id=document_id,
        user=user,
        include_lifecycle=True,
    )
    complete = bool(bundle.get("complete"))
    return {
        **bundle,
        "can_publish": complete,
        "kind": "impact_bundle",
        "generated_at": bundle.get("generated_at") or utc_now(),
        # Convenience: flatten hops for FE checklist
        "hops": [
            *(public_hop(h) if "source_type" in h else h for h in bundle.get("upstream") or []),
            *(public_hop(h) if "source_type" in h else h for h in bundle.get("downstream") or []),
        ],
    }


def publish_blocked_detail(bundle: dict[str, Any]) -> dict[str, Any]:
    """HTTP error payload when publish is refused due to incomplete ImpactBundle."""
    return {
        "code": "ENTITY360_IMPACT_INCOMPLETE",
        "message": "Publish blocked: impact bundle is incomplete or degraded",
        "complete": False,
        "can_publish": False,
        "degraded_reasons": list(bundle.get("degraded_reasons") or []),
        "sources": list(bundle.get("sources") or []),
    }


__all__ = [
    "build_impact_bundle",
    "publish_blocked_detail",
]
