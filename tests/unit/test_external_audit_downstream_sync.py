"""Contract tests for post-promotion downstream retry and proof honesty."""

from __future__ import annotations

from collections.abc import Sequence

import pytest

from src.domain.services.external_audit_downstream_sync import (
    DownstreamSyncRequest,
    DownstreamSyncResult,
    DownstreamTarget,
    ProofTileStatus,
    RetryPolicy,
    SyncState,
    build_downstream_proof_tile,
    sync_with_retry,
)


class SequencedAdapter:
    def __init__(self, results: Sequence[DownstreamSyncResult]) -> None:
        self.results = list(results)
        self.attempts: list[int] = []

    async def sync(self, request: DownstreamSyncRequest, *, attempt: int) -> DownstreamSyncResult:
        del request
        self.attempts.append(attempt)
        return self.results.pop(0)


def _request() -> DownstreamSyncRequest:
    return DownstreamSyncRequest(import_job_id=17, audit_run_id=9, tenant_id=3, idempotency_key="job-17:uvdb")


@pytest.mark.asyncio
async def test_retryable_failure_retries_until_uvdb_sync_succeeds() -> None:
    adapter = SequencedAdapter(
        [
            DownstreamSyncResult(
                target=DownstreamTarget.UVDB,
                state=SyncState.FAILED,
                attempt_count=1,
                detail="UVDB gateway timed out.",
                retryable=True,
                error_code="timeout",
            ),
            DownstreamSyncResult(
                target=DownstreamTarget.UVDB,
                state=SyncState.SUCCEEDED,
                attempt_count=2,
                detail="UVDB audit projection is durable.",
                records_written=1,
                records_expected=1,
            ),
        ]
    )

    result = await sync_with_retry(adapter, _request(), policy=RetryPolicy(max_attempts=3))

    assert adapter.attempts == [1, 2]
    assert result.state is SyncState.SUCCEEDED
    assert result.records_written == 1


@pytest.mark.asyncio
async def test_non_retryable_registry_failure_stops_after_first_attempt() -> None:
    adapter = SequencedAdapter(
        [
            DownstreamSyncResult(
                target=DownstreamTarget.REGISTRY,
                state=SyncState.FAILED,
                attempt_count=1,
                detail="Registry request was rejected.",
                retryable=False,
                error_code="validation_error",
            )
        ]
    )

    result = await sync_with_retry(adapter, _request(), policy=RetryPolicy(max_attempts=3))

    assert adapter.attempts == [1]
    assert result.error_code == "validation_error"


def test_partial_proof_tile_preserves_observed_counts() -> None:
    result = DownstreamSyncResult(
        target=DownstreamTarget.EVIDENCE,
        state=SyncState.PARTIAL,
        attempt_count=2,
        detail="Two evidence links were created; one still needs review.",
        retryable=True,
        records_written=2,
        records_expected=3,
    )

    tile = build_downstream_proof_tile(result, target=DownstreamTarget.EVIDENCE)

    assert tile.status is ProofTileStatus.PARTIAL
    assert tile.records_written == 2
    assert tile.records_expected == 3


def test_failed_proof_tile_never_silently_substitutes_zero_for_unknown_counts() -> None:
    result = DownstreamSyncResult(
        target=DownstreamTarget.PLANET_MARK,
        state=SyncState.FAILED,
        attempt_count=3,
        detail="Planet Mark endpoint did not return a write receipt.",
        retryable=True,
    )

    tile = build_downstream_proof_tile(result, target=DownstreamTarget.PLANET_MARK)

    assert tile.status is ProofTileStatus.FAILED
    assert tile.records_written is None
    assert tile.records_expected is None


def test_unobserved_proof_tile_is_pending_not_success_or_zero() -> None:
    tile = build_downstream_proof_tile(None, target=DownstreamTarget.UVDB)

    assert tile.status is ProofTileStatus.PENDING
    assert tile.records_written is None
    assert tile.records_expected is None
    assert tile.attempt_count == 0
