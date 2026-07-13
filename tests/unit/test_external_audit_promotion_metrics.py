"""Unit tests for promote / uvdb_sync outcome metrics (Wave C observability)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from src.domain.services import external_audit_promotion_service as promo_mod
from src.domain.services.external_audit_promotion_service import (
    ExternalAuditPromotionService,
    _record_promote_outcome,
    _record_uvdb_sync_outcome,
    get_promotion_outcome_counters,
    reset_promotion_outcome_counters,
)


@pytest.fixture(autouse=True)
def _reset_counters():
    reset_promotion_outcome_counters()
    yield
    reset_promotion_outcome_counters()


def test_record_promote_outcome_increments_counter(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(promo_mod, "record_external_audit_promote_outcome", lambda outcome: seen.append(outcome))

    _record_promote_outcome("completed")
    _record_promote_outcome("partial")

    counters = get_promotion_outcome_counters()
    assert counters["promote:completed"] == 1
    assert counters["promote:partial"] == 1
    assert seen == ["completed", "partial"]


def test_record_uvdb_sync_outcome_is_not_log_only(monkeypatch):
    seen: list[str] = []
    monkeypatch.setattr(promo_mod, "record_external_audit_promote_outcome", lambda outcome: seen.append(outcome))

    _record_uvdb_sync_outcome("synced")
    _record_uvdb_sync_outcome("missing")

    counters = get_promotion_outcome_counters()
    assert counters["uvdb_sync:synced"] == 1
    assert counters["uvdb_sync:missing"] == 1
    assert seen == ["uvdb_sync:synced", "uvdb_sync:missing"]


def test_emit_uvdb_sync_metric_for_scheme_alignment():
    host = MagicMock()
    service = ExternalAuditPromotionService(host)

    job = SimpleNamespace(detected_scheme="achilles_uvdb", provenance_json={}, source_filename=None)
    run = SimpleNamespace(assurance_scheme="Achilles UVDB Verify B2")

    service._emit_uvdb_sync_metric(
        job=job,
        run=run,
        scheme_alignment={"status": "synced", "uvdb_audit_id": 99},
    )
    assert get_promotion_outcome_counters()["uvdb_sync:synced"] == 1

    reset_promotion_outcome_counters()
    service._emit_uvdb_sync_metric(
        job=job,
        run=run,
        scheme_alignment={"status": "already_synced", "uvdb_audit_id": None},
    )
    assert get_promotion_outcome_counters()["uvdb_sync:missing"] == 1

    reset_promotion_outcome_counters()
    non_uvdb_job = SimpleNamespace(detected_scheme="planet_mark", provenance_json={}, source_filename=None)
    non_uvdb_run = SimpleNamespace(assurance_scheme="Planet Mark")
    service._emit_uvdb_sync_metric(job=non_uvdb_job, run=non_uvdb_run, scheme_alignment={"status": "synced"})
    assert get_promotion_outcome_counters()["uvdb_sync:n_a"] == 1
