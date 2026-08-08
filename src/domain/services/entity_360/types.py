"""Shared Entity360 hop / source contracts (conveyor Rev 2)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Literal, Optional, Protocol

HopOrigin = Literal["graph", "cel", "case_link", "job", "lifecycle"]
HopDirection = Literal["upstream", "downstream"]
SourceStatusName = Literal["ok", "denied", "error", "skipped"]

HOP_REQUIRED_FIELDS = (
    "source_type",
    "source_id",
    "title",
    "reference",
    "href",
    "direction",
    "relation",
    "depth",
    "origin",
    "status",
    "confidence",
    "edge_id",
    "version_pin",
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def make_hop(
    *,
    source_type: str,
    source_id: int,
    href: str,
    direction: HopDirection,
    relation: str,
    origin: HopOrigin,
    depth: int = 1,
    title: Optional[str] = None,
    reference: Optional[str] = None,
    status: Optional[str] = None,
    confidence: Optional[float] = None,
    edge_id: Optional[int] = None,
    version_pin: Optional[int] = None,
) -> dict[str, Any]:
    """Build one hop dict matching the frozen Entity360 hop contract."""
    return {
        "source_type": source_type,
        "source_id": int(source_id),
        "title": title,
        "reference": reference,
        "href": href,
        "direction": direction,
        "relation": relation,
        "depth": int(depth),
        "origin": origin,
        "status": status,
        "confidence": confidence,
        "edge_id": edge_id,
        "version_pin": version_pin,
    }


@dataclass
class ProducerResult:
    """Outcome of one Entity360 producer for a subject entity."""

    origin: str
    status: SourceStatusName
    upstream: list[dict[str, Any]] = field(default_factory=list)
    downstream: list[dict[str, Any]] = field(default_factory=list)
    reason: Optional[str] = None


@dataclass
class SourceStatus:
    origin: str
    status: SourceStatusName
    # denied / skipped / error carry no hop counts — honesty without oracle leakage


class Entity360Producer(Protocol):
    """Bidirectional producer registration contract.

    Producers that claim an entity type MUST emit both upstream and downstream
    lists on day one (empty list allowed). One-way silos are rejected by tests.
    """

    origin: str

    def supports(self, entity_type: str) -> bool: ...

    async def produce(
        self,
        *,
        db: Any,
        tenant_id: int,
        entity_type: str,
        entity_id: int,
        user: Any,
    ) -> ProducerResult: ...


__all__ = [
    "HOP_REQUIRED_FIELDS",
    "Entity360Producer",
    "HopDirection",
    "HopOrigin",
    "ProducerResult",
    "SourceStatus",
    "SourceStatusName",
    "make_hop",
    "utc_now",
]
