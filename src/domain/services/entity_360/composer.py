"""Entity360 composer — aggregates bidirectional producers into one bundle."""

from __future__ import annotations

import logging
from typing import Any, Optional

from src.domain.services.entity_360.permissions import can_view_hop, filter_hops
from src.domain.services.entity_360.registry import iter_producers
from src.domain.services.entity_360.types import HOP_REQUIRED_FIELDS, ProducerResult, SourceStatus, make_hop, utc_now
from src.domain.services.href_registry import href_for

logger = logging.getLogger(__name__)

# Internal-only keys stripped before API serialization
_INTERNAL_HOP_KEYS = frozenset({"_audit_run_id"})


def public_hop(hop: dict[str, Any]) -> dict[str, Any]:
    """Return hop with only the frozen contract fields (plus no internal keys)."""
    return {k: hop.get(k) for k in HOP_REQUIRED_FIELDS}


def narrow_risk_upstream_item(hop: dict[str, Any]) -> dict[str, Any]:
    """Project an Entity360 hop onto the frozen ``RiskUpstreamItem`` wire shape."""
    item: dict[str, Any] = {
        "source_type": hop["source_type"],
        "source_id": hop["source_id"],
        "title": hop.get("title"),
        "reference": hop.get("reference"),
        "href": hop["href"],
    }
    audit_run_id = hop.get("_audit_run_id")
    if audit_run_id is not None:
        item["audit_run_id"] = audit_run_id
    return item


class Entity360Service:
    """Compose Entity360 bundles from registered producers."""

    def __init__(self, db: Any):
        self.db = db

    async def compose(
        self,
        *,
        tenant_id: int,
        entity_type: str,
        entity_id: int,
        user: Any,
        include_lifecycle: bool = True,
    ) -> dict[str, Any]:
        key = entity_type.strip().lower()
        producers = iter_producers(entity_type=key)
        if not include_lifecycle:
            producers = [p for p in producers if getattr(p, "origin", None) != "lifecycle"]

        upstream: list[dict[str, Any]] = []
        downstream: list[dict[str, Any]] = []
        sources: list[dict[str, str]] = []
        degraded_reasons: list[str] = []

        if not producers:
            sources.append({"origin": "none", "status": "skipped"})
        for producer in producers:
            # Origin-level deny: if the subject type itself is unreadable, mark denied
            if not can_view_hop(user, key) and key not in ("document", "risk"):
                # Subject access is enforced at the route; producers still run.
                pass

            try:
                result: ProducerResult = await producer.produce(
                    db=self.db,
                    tenant_id=tenant_id,
                    entity_type=key,
                    entity_id=entity_id,
                    user=user,
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Entity360 producer %s failed", getattr(producer, "origin", "?"))
                result = ProducerResult(
                    origin=getattr(producer, "origin", "unknown"),
                    status="error",
                    reason=str(exc),
                )

            if result.status == "error":
                sources.append({"origin": result.origin, "status": "error"})
                if result.reason:
                    degraded_reasons.append(result.reason)
                continue

            if result.status == "skipped":
                sources.append({"origin": result.origin, "status": "skipped"})
                continue

            if result.status == "denied":
                sources.append({"origin": result.origin, "status": "denied"})
                continue

            # ok — filter per-hop; if producer returned hops but all denied → denied (no count)
            raw_up = list(result.upstream or [])
            raw_down = list(result.downstream or [])
            had_any = bool(raw_up or raw_down)
            filtered_up = filter_hops(user, raw_up)
            filtered_down = filter_hops(user, raw_down)
            if had_any and not filtered_up and not filtered_down:
                sources.append({"origin": result.origin, "status": "denied"})
                continue

            sources.append({"origin": result.origin, "status": "ok"})
            upstream.extend(filtered_up)
            downstream.extend(filtered_down)

        complete = not any(s["status"] == "error" for s in sources)
        entity_href = href_for(key, entity_id)
        return {
            "entity": {
                "source_type": key,
                "source_id": entity_id,
                "href": entity_href,
            },
            "upstream": [public_hop(h) for h in upstream],
            "downstream": [public_hop(h) for h in downstream],
            "sources": sources,
            "complete": complete,
            "degraded_reasons": degraded_reasons,
            "generated_at": utc_now(),
        }

    async def list_risk_upstream_items(
        self,
        *,
        tenant_id: int,
        risk_id: int,
        user: Optional[Any] = None,
    ) -> list[dict[str, Any]]:
        """Fold risk upstream onto Entity360 internals; return RiskUpstreamItem dicts.

        Does not require the ``entity_360`` feature flag — preserves the existing
        risk-register wire path while sharing composer producers.
        """
        from src.domain.services.entity_360.producers.case_link import CaseLinkProducer

        actor = user if user is not None else _AllowAllUser()
        producer = CaseLinkProducer()
        result = await producer.produce(
            db=self.db,
            tenant_id=tenant_id,
            entity_type="risk",
            entity_id=risk_id,
            user=actor,
        )
        if result.status != "ok":
            return []
        items = [narrow_risk_upstream_item(h) for h in result.upstream]
        if user is not None:
            items = [
                item
                for item, hop in zip(items, result.upstream)
                if can_view_hop(user, str(hop.get("source_type") or ""))
            ]
        return items


class _AllowAllUser:
    is_superuser = True

    def has_permission(self, _permission: str) -> bool:
        return True


# Re-export make_hop for tests
__all__ = [
    "Entity360Service",
    "make_hop",
    "narrow_risk_upstream_item",
    "public_hop",
]
