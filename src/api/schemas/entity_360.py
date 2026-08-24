"""Pydantic schemas for Entity360 + ImpactBundle (conveyor X-1)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

HopOrigin = Literal["graph", "cel", "case_link", "job", "lifecycle"]
HopDirection = Literal["upstream", "downstream"]
SourceStatusName = Literal["ok", "denied", "error", "skipped"]


class Entity360Hop(BaseModel):
    """Frozen shared hop contract — every Connections / Impact surface."""

    model_config = ConfigDict(extra="forbid")

    source_type: str
    source_id: int
    title: Optional[str] = None
    reference: Optional[str] = None
    href: str
    direction: HopDirection
    relation: str
    depth: int = 1
    origin: HopOrigin
    status: Optional[str] = None
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    edge_id: Optional[int] = None
    version_pin: Optional[int] = None


class Entity360EntityRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str
    source_id: int
    href: str
    title: Optional[str] = None
    reference: Optional[str] = None


class Entity360SourceStatus(BaseModel):
    """Producer source status — ``denied`` carries no hop counts."""

    model_config = ConfigDict(extra="forbid")

    origin: str
    status: SourceStatusName


class Entity360Bundle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entity: Entity360EntityRef
    upstream: List[Entity360Hop]
    downstream: List[Entity360Hop]
    sources: List[Entity360SourceStatus]
    complete: bool
    degraded_reasons: List[str] = Field(default_factory=list)
    generated_at: datetime


class ImpactBundle(Entity360Bundle):
    """Publish impact preview — blocks publish when ``complete`` is false."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["impact_bundle"] = "impact_bundle"
    can_publish: bool
    hops: List[Entity360Hop] = Field(default_factory=list)


__all__ = [
    "Entity360Bundle",
    "Entity360EntityRef",
    "Entity360Hop",
    "Entity360SourceStatus",
    "ImpactBundle",
]
