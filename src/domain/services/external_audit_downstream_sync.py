"""Retry-safe contracts and honest proof tiles for post-promotion downstream sync.

This module deliberately has no database or promotion-service dependency.  A
future dispatcher can provide adapters for UVDB, Planet Mark, the external
audit registry, and evidence links without changing how retry outcomes or
operator-facing proof are represented.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class DownstreamTarget(StrEnum):
    """Named projections produced after an external audit is promoted."""

    UVDB = "uvdb"
    PLANET_MARK = "planet_mark"
    REGISTRY = "registry"
    EVIDENCE = "evidence"


class SyncState(StrEnum):
    """Terminal state of a single downstream projection."""

    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True)
class DownstreamSyncRequest:
    """The stable context supplied to a target-specific downstream adapter."""

    import_job_id: int
    audit_run_id: int
    tenant_id: int
    idempotency_key: str


@dataclass(frozen=True)
class DownstreamSyncResult:
    """A durable, inspectable result; counts stay unknown when not observed."""

    target: DownstreamTarget
    state: SyncState
    attempt_count: int
    detail: str
    retryable: bool = False
    records_written: int | None = None
    records_expected: int | None = None
    error_code: str | None = None

    @property
    def should_retry(self) -> bool:
        return self.state in {SyncState.FAILED, SyncState.PARTIAL} and self.retryable


class DownstreamSyncAdapter(Protocol):
    """Port implemented by the UVDB, Planet Mark, registry, or evidence adapter."""

    async def sync(self, request: DownstreamSyncRequest, *, attempt: int) -> DownstreamSyncResult:
        """Synchronise one target and return its actual outcome."""


@dataclass(frozen=True)
class RetryPolicy:
    """Bounded retry policy; attempts include the first invocation."""

    max_attempts: int = 3

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be at least one")


async def sync_with_retry(
    adapter: DownstreamSyncAdapter,
    request: DownstreamSyncRequest,
    *,
    policy: RetryPolicy = RetryPolicy(),
) -> DownstreamSyncResult:
    """Run a target adapter until it succeeds or returns a non-retryable result."""

    result: DownstreamSyncResult | None = None
    for attempt in range(1, policy.max_attempts + 1):
        result = await adapter.sync(request, attempt=attempt)
        if result.target not in DownstreamTarget:
            raise ValueError("adapter returned an unknown downstream target")
        if not result.should_retry:
            return result
    assert result is not None
    return result


class ProofTileStatus(StrEnum):
    """Operator-facing proof state; never infer success from absent data."""

    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"
    PENDING = "pending"


@dataclass(frozen=True)
class DownstreamProofTile:
    """Truthful proof summary for one downstream target."""

    target: DownstreamTarget
    status: ProofTileStatus
    label: str
    detail: str
    records_written: int | None
    records_expected: int | None
    attempt_count: int


def build_downstream_proof_tile(
    result: DownstreamSyncResult | None, *, target: DownstreamTarget
) -> DownstreamProofTile:
    """Map an observed result to proof without converting unavailable data to zero."""

    if result is None:
        return DownstreamProofTile(
            target=target,
            status=ProofTileStatus.PENDING,
            label=target.value.replace("_", " ").title(),
            detail="Sync outcome has not been observed yet.",
            records_written=None,
            records_expected=None,
            attempt_count=0,
        )
    if result.target != target:
        raise ValueError(f"result target {result.target} does not match requested target {target}")

    status_by_state = {
        SyncState.SUCCEEDED: ProofTileStatus.SUCCESS,
        SyncState.PARTIAL: ProofTileStatus.PARTIAL,
        SyncState.FAILED: ProofTileStatus.FAILED,
        SyncState.NOT_APPLICABLE: ProofTileStatus.NOT_APPLICABLE,
    }
    return DownstreamProofTile(
        target=target,
        status=status_by_state[result.state],
        label=target.value.replace("_", " ").title(),
        detail=result.detail,
        records_written=result.records_written,
        records_expected=result.records_expected,
        attempt_count=result.attempt_count,
    )


__all__ = [
    "DownstreamProofTile",
    "DownstreamSyncAdapter",
    "DownstreamSyncRequest",
    "DownstreamSyncResult",
    "DownstreamTarget",
    "ProofTileStatus",
    "RetryPolicy",
    "SyncState",
    "build_downstream_proof_tile",
    "sync_with_retry",
]
