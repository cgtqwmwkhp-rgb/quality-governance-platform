"""Entity360 shared hop composer (conveyor X-1)."""

from __future__ import annotations

from src.domain.services.entity_360.composer import (
    Entity360Service,
    make_hop,
    narrow_risk_upstream_item,
    public_hop,
)
from src.domain.services.entity_360.impact import build_impact_bundle, publish_blocked_detail
from src.domain.services.entity_360.registry import (
    all_producers,
    ensure_default_producers,
    register_producer,
    reset_producers,
)
from src.domain.services.entity_360.types import HOP_REQUIRED_FIELDS, ProducerResult

__all__ = [
    "HOP_REQUIRED_FIELDS",
    "Entity360Service",
    "ProducerResult",
    "all_producers",
    "build_impact_bundle",
    "ensure_default_producers",
    "make_hop",
    "narrow_risk_upstream_item",
    "public_hop",
    "publish_blocked_detail",
    "register_producer",
    "reset_producers",
]
