"""Upstream circuit breaker foundation (Path-to-10 Preferred S10).

Canonical named breakers for OCR / AI / blob upstreams. Wraps the shared
infrastructure :class:`~src.infrastructure.resilience.circuit_breaker.CircuitBreaker`
with stable names, Preferred defaults, and a degraded-mode summary surface.

This module does **not** invent API keys, dial providers, or mutate ``/readyz``.
Call sites may adopt ``get_upstream_breaker`` / ``call_via_upstream_breaker``
incrementally; existing per-service breakers that already use the same names
remain compatible via the shared registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

from src.infrastructure.resilience.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerOpenError,
    CircuitState,
    get_all_circuits,
)

# Re-export for call-site convenience without importing infrastructure directly.
__all__ = [
    "UPSTREAM_BREAKER_NAMES",
    "UpstreamBreakerSpec",
    "UpstreamDegradedSummary",
    "CircuitBreakerOpenError",
    "call_via_upstream_breaker",
    "ensure_upstream_breakers_registered",
    "get_upstream_breaker",
    "get_upstream_breaker_health",
    "is_upstream_degraded",
    "list_upstream_breaker_health",
    "upstream_degraded_summary",
]


@dataclass(frozen=True)
class UpstreamBreakerSpec:
    """Preferred defaults for a named upstream breaker."""

    name: str
    role: str
    failure_threshold: int = 5
    recovery_timeout: float = 60.0
    half_open_max_calls: int = 1


# Canonical S10 upstream names (aligned with ai_status circuit metadata).
UPSTREAM_BREAKER_SPECS: Mapping[str, UpstreamBreakerSpec] = {
    "mistral_analysis": UpstreamBreakerSpec(
        name="mistral_analysis",
        role="ocr",
        failure_threshold=5,
        recovery_timeout=300.0,
    ),
    "gemini_ai": UpstreamBreakerSpec(
        name="gemini_ai",
        role="ai",
        failure_threshold=5,
        recovery_timeout=60.0,
    ),
    "gemini_review": UpstreamBreakerSpec(
        name="gemini_review",
        role="ai_review",
        failure_threshold=5,
        recovery_timeout=300.0,
    ),
    "blob_storage": UpstreamBreakerSpec(
        name="blob_storage",
        role="blob",
        failure_threshold=5,
        recovery_timeout=60.0,
    ),
}

UPSTREAM_BREAKER_NAMES: tuple[str, ...] = tuple(UPSTREAM_BREAKER_SPECS.keys())


@dataclass(frozen=True)
class UpstreamDegradedSummary:
    """Aggregate degraded view for ops / FE banners."""

    degraded: bool
    open_circuits: tuple[str, ...]
    half_open_circuits: tuple[str, ...]
    circuits: tuple[dict[str, Any], ...]
    message: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "degraded": self.degraded,
            "open_circuits": list(self.open_circuits),
            "half_open_circuits": list(self.half_open_circuits),
            "circuits": list(self.circuits),
            "message": self.message,
        }


def _registry_by_name() -> dict[str, CircuitBreaker]:
    return {cb.name: cb for cb in get_all_circuits()}


def get_upstream_breaker(name: str) -> CircuitBreaker:
    """Return the shared breaker for ``name``, creating it from Preferred specs.

    Unknown names are rejected so callers cannot silently invent ad-hoc
    upstream identities outside the S10 catalog.
    """
    spec = UPSTREAM_BREAKER_SPECS.get(name)
    if spec is None:
        known = ", ".join(UPSTREAM_BREAKER_NAMES)
        raise KeyError(f"Unknown upstream breaker '{name}'. Known: {known}")

    existing = _registry_by_name().get(name)
    if existing is not None:
        return existing

    return CircuitBreaker(
        name=spec.name,
        failure_threshold=spec.failure_threshold,
        recovery_timeout=spec.recovery_timeout,
        half_open_max_calls=spec.half_open_max_calls,
    )


def ensure_upstream_breakers_registered(
    names: tuple[str, ...] | None = None,
) -> list[CircuitBreaker]:
    """Ensure Preferred upstream breakers exist in the process registry.

    Safe to call at startup or from readiness helpers. Does not probe providers.
    """
    target = names if names is not None else UPSTREAM_BREAKER_NAMES
    return [get_upstream_breaker(name) for name in target]


def get_upstream_breaker_health(name: str) -> dict[str, Any]:
    """Health dict for one catalog breaker (registers on demand)."""
    breaker = get_upstream_breaker(name)
    health = breaker.get_health()
    spec = UPSTREAM_BREAKER_SPECS[name]
    health["role"] = spec.role
    return health


def list_upstream_breaker_health(
    *,
    register_missing: bool = True,
) -> list[dict[str, Any]]:
    """Health for every Preferred upstream breaker.

    When ``register_missing`` is False, unregistered names are reported as
    ``state: unregistered`` without creating breaker instances (honest for
    cold processes that have not yet imported OCR/AI clients).
    """
    registered = _registry_by_name()
    rows: list[dict[str, Any]] = []
    for name, spec in UPSTREAM_BREAKER_SPECS.items():
        if name in registered:
            health = registered[name].get_health()
            health["role"] = spec.role
            rows.append(health)
        elif register_missing:
            rows.append(get_upstream_breaker_health(name))
        else:
            rows.append(
                {
                    "name": name,
                    "role": spec.role,
                    "state": "unregistered",
                    "note": (
                        "Circuit registers on first provider import/use "
                        "or via ensure_upstream_breakers_registered()."
                    ),
                }
            )
    return rows


def is_upstream_degraded(*, register_missing: bool = False) -> bool:
    """True when any Preferred upstream breaker is OPEN or HALF_OPEN."""
    return upstream_degraded_summary(register_missing=register_missing).degraded


def upstream_degraded_summary(
    *,
    register_missing: bool = False,
) -> UpstreamDegradedSummary:
    """Build a banner-friendly degraded summary for Preferred upstreams.

    Default ``register_missing=False`` keeps cold processes honest: missing
    breakers stay ``unregistered`` rather than appearing healthy CLOSED.
    """
    circuits = list_upstream_breaker_health(register_missing=register_missing)
    open_names: list[str] = []
    half_open_names: list[str] = []
    for row in circuits:
        state = row.get("state")
        name = str(row.get("name", ""))
        if state == CircuitState.OPEN.value:
            open_names.append(name)
        elif state == CircuitState.HALF_OPEN.value:
            half_open_names.append(name)

    degraded = bool(open_names or half_open_names)
    if not degraded:
        message = "All registered Preferred upstream breakers are closed."
    elif open_names and half_open_names:
        message = (
            "Upstream OCR/AI/blob services are degraded: "
            f"open={', '.join(open_names)}; probing={', '.join(half_open_names)}."
        )
    elif open_names:
        message = (
            "Upstream OCR/AI/blob services are temporarily unavailable "
            f"(circuit open: {', '.join(open_names)}). Retry shortly."
        )
    else:
        message = "Upstream OCR/AI/blob services are recovering " f"(half-open probe: {', '.join(half_open_names)})."

    return UpstreamDegradedSummary(
        degraded=degraded,
        open_circuits=tuple(open_names),
        half_open_circuits=tuple(half_open_names),
        circuits=tuple(circuits),
        message=message,
    )


async def call_via_upstream_breaker(
    name: str,
    func: Callable[..., Any],
    *args: Any,
    **kwargs: Any,
) -> Any:
    """Execute ``func`` through the Preferred breaker for ``name``.

    Raises :class:`CircuitBreakerOpenError` when the circuit is open.
    """
    breaker = get_upstream_breaker(name)
    return await breaker.call(func, *args, **kwargs)
