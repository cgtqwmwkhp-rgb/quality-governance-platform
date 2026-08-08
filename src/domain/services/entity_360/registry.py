"""Producer registration for Entity360 (bidirectional day-one contract)."""

from __future__ import annotations

from typing import Iterable, List

from src.domain.services.entity_360.types import Entity360Producer

_PRODUCERS: list[Entity360Producer] = []
_DEFAULTS_LOADED = False


def register_producer(producer: Entity360Producer) -> Entity360Producer:
    """Register a producer. Replaces any prior registration with the same origin."""
    global _PRODUCERS
    _PRODUCERS = [p for p in _PRODUCERS if getattr(p, "origin", None) != producer.origin]
    _PRODUCERS.append(producer)
    return producer


def clear_producers() -> None:
    """Test helper — wipe registry (does not reset defaults-loaded flag)."""
    global _PRODUCERS
    _PRODUCERS = []


def reset_producers() -> None:
    """Test helper — clear and reload default producers."""
    global _DEFAULTS_LOADED, _PRODUCERS
    _PRODUCERS = []
    _DEFAULTS_LOADED = False
    ensure_default_producers()


def ensure_default_producers() -> None:
    """Idempotently register built-in producers (document graph + case_link)."""
    global _DEFAULTS_LOADED
    if _DEFAULTS_LOADED:
        return
    from src.domain.services.entity_360.producers.case_link import CaseLinkProducer
    from src.domain.services.entity_360.producers.document_graph import DocumentGraphProducer
    from src.domain.services.entity_360.producers.lifecycle_impact import LifecycleImpactProducer

    register_producer(DocumentGraphProducer())
    register_producer(CaseLinkProducer())
    register_producer(LifecycleImpactProducer())
    _DEFAULTS_LOADED = True


def iter_producers(*, entity_type: str) -> List[Entity360Producer]:
    ensure_default_producers()
    key = entity_type.strip().lower()
    return [p for p in _PRODUCERS if p.supports(key)]


def all_producers() -> Iterable[Entity360Producer]:
    ensure_default_producers()
    return list(_PRODUCERS)


__all__ = [
    "all_producers",
    "clear_producers",
    "ensure_default_producers",
    "iter_producers",
    "register_producer",
    "reset_producers",
]
