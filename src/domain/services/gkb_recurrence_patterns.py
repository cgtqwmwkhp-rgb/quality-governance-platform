"""GKB WL4 recurrence pattern planner (scaffold).

Clusters repeated clause / evidence hits across cases into a deny-safe
recurrence plan. Clustering key is ``tenant_id`` + ``clause_id``, with an
optional ``entity_type`` window so the same clause can form separate patterns
per entity kind (incident, audit finding, etc.).

This module is deliberately unwired from routes, persistence, and
GovernedKnowledgeService. Callers receive a plan with stable pattern keys,
hit counts, and sample entity ids for future adapters.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import StrEnum


class RecurrencePatternStep(StrEnum):
    """Ordered recurrence planner steps."""

    CLUSTER_HITS = "cluster_hits"
    EMIT_PATTERNS = "emit_patterns"


class RecurrencePatternDenyReason(StrEnum):
    """Stable deny reasons when recurrence planning must not run."""

    TENANT_CONTEXT_REQUIRED = "tenant_context_required"
    HITS_REQUIRED = "hits_required"


@dataclass(frozen=True)
class ClauseHitRecord:
    """Minimum clause / evidence hit input (no DB required)."""

    clause_id: str
    entity_id: str
    entity_type: str | None = None
    tenant_id: int | None = None


@dataclass(frozen=True)
class RecurrencePatternCluster:
    """One clustered recurrence pattern within a plan."""

    pattern_key: str
    clause_id: str
    entity_type: str | None
    hit_count: int
    sample_entity_ids: tuple[str, ...]


@dataclass(frozen=True)
class RecurrencePatternContext:
    """Minimum inputs for a recurrence-pattern decision (no DB required)."""

    tenant_id: int | None
    hits: tuple[ClauseHitRecord, ...] = ()
    # When True, entity_type participates in the cluster key (optional window).
    include_entity_type_window: bool = True
    # Cap distinct sample entity ids retained per pattern (deterministic order).
    sample_limit: int = 5


@dataclass(frozen=True)
class RecurrencePatternPlan:
    """Idempotent-friendly decision outcome for recurrence clustering."""

    patterns: tuple[RecurrencePatternCluster, ...]
    steps: tuple[RecurrencePatternStep, ...]
    denied: bool = False
    deny_reason: RecurrencePatternDenyReason | None = None

    @property
    def should_run(self) -> bool:
        return not self.denied and bool(self.steps)

    @property
    def pattern_count(self) -> int:
        return len(self.patterns)


def decide_recurrence_patterns(ctx: RecurrencePatternContext) -> RecurrencePatternPlan:
    """Cluster clause hits into recurrence patterns for a tenant.

    Deny-safe defaults: missing tenant or empty hits yields an empty plan with
    a stable deny reason (no side effects implied). Hits belonging to another
    tenant (when ``hit.tenant_id`` is set) are ignored.
    """
    if ctx.tenant_id is None:
        return _denied(RecurrencePatternDenyReason.TENANT_CONTEXT_REQUIRED)
    if not ctx.hits:
        return _denied(RecurrencePatternDenyReason.HITS_REQUIRED)

    sample_limit = max(0, int(ctx.sample_limit))
    buckets: dict[tuple[str, str | None], list[str]] = defaultdict(list)

    for hit in ctx.hits:
        if hit.tenant_id is not None and hit.tenant_id != ctx.tenant_id:
            continue
        clause_id = (hit.clause_id or "").strip()
        entity_id = (hit.entity_id or "").strip()
        if not clause_id or not entity_id:
            continue
        entity_type = (hit.entity_type or "").strip() or None
        window = entity_type if ctx.include_entity_type_window else None
        buckets[(clause_id, window)].append(entity_id)

    if not buckets:
        return _denied(RecurrencePatternDenyReason.HITS_REQUIRED)

    patterns: list[RecurrencePatternCluster] = []
    for (clause_id, entity_type), entity_ids in sorted(
        buckets.items(), key=lambda item: (item[0][0], item[0][1] or "")
    ):
        # Preserve first-seen order while de-duplicating sample ids.
        seen: set[str] = set()
        unique_ids: list[str] = []
        for entity_id in entity_ids:
            if entity_id in seen:
                continue
            seen.add(entity_id)
            unique_ids.append(entity_id)

        pattern_key = _pattern_key(ctx.tenant_id, clause_id, entity_type)
        patterns.append(
            RecurrencePatternCluster(
                pattern_key=pattern_key,
                clause_id=clause_id,
                entity_type=entity_type,
                hit_count=len(entity_ids),
                sample_entity_ids=tuple(unique_ids[:sample_limit]),
            )
        )

    return RecurrencePatternPlan(
        patterns=tuple(patterns),
        steps=(
            RecurrencePatternStep.CLUSTER_HITS,
            RecurrencePatternStep.EMIT_PATTERNS,
        ),
    )


def _pattern_key(tenant_id: int, clause_id: str, entity_type: str | None) -> str:
    if entity_type:
        return f"tenant:{tenant_id}|clause:{clause_id}|entity_type:{entity_type}"
    return f"tenant:{tenant_id}|clause:{clause_id}"


def _denied(reason: RecurrencePatternDenyReason) -> RecurrencePatternPlan:
    return RecurrencePatternPlan(
        patterns=(),
        steps=(),
        denied=True,
        deny_reason=reason,
    )
