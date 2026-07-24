"""Unit tests for Safety Insights training/competence correlation (no DB)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from src.domain.services.safety_insights_training import (
    build_signals_from_rows,
    empty_training_signals,
    labels_overlap,
    tokenize_label,
)


def test_tokenize_label_strips_stopwords():
    tokens = tokenize_label("Reversing near miss at Depot Alpha")
    assert "reversing" in tokens
    assert "depot" in tokens
    assert "alpha" in tokens
    assert "near" not in tokens
    assert "miss" not in tokens


def test_labels_overlap_requires_shared_token():
    shared = labels_overlap("manual handling injuries", "Manual Handling competency")
    assert "manual" in shared
    assert "handling" in shared
    assert labels_overlap("forklift tip-over", "working at height") == set()


def test_empty_training_signals_is_honest():
    payload = empty_training_signals()
    assert payload["available"] is False
    assert payload["signals"] == []
    assert "competence_gap_actions" in payload["sources_checked"]


def test_build_signals_sparse_data_returns_unavailable():
    payload = build_signals_from_rows(
        theme_labels=["reversing collisions"],
        modules=["rta"],
        gaps=[],
        tickets=[],
        competency_rows=[],
        requirements=[],
    )
    assert payload["available"] is False
    assert payload["signals"] == []


def test_open_competence_gap_emits_signal_even_without_theme_match():
    gap = SimpleNamespace(
        id=11,
        status="open",
        signal_type="competence_gap",
        ticket_scheme="CSCS",
        rationale="Operator failed practical",
        requirement_id=None,
        engineer_id=5,
    )
    payload = build_signals_from_rows(
        theme_labels=["unrelated theme xyz"],
        modules=["incident"],
        gaps=[gap],
        tickets=[],
        competency_rows=[],
        requirements=[],
    )
    assert payload["available"] is True
    assert len(payload["signals"]) == 1
    sig = payload["signals"][0]
    assert sig["kind"] == "open_competence_gap"
    assert sig["evidence"]["gap_id"] == 11
    assert sig["theme_label"] is None
    assert sig["strength"] == "weak"


def test_theme_overlap_with_requirement_and_expired_ticket():
    now = datetime(2026, 7, 1, tzinfo=timezone.utc)
    req = SimpleNamespace(id=3, name="Manual Handling refresher", is_mandatory=True)
    ticket = SimpleNamespace(
        id=9,
        scheme="Manual Handling",
        verify_state="expired",
        expires_at=now - timedelta(days=10),
        engineer_id=2,
    )
    payload = build_signals_from_rows(
        theme_labels=["manual handling strains"],
        modules=["incident", "near_miss"],
        gaps=[],
        tickets=[ticket],
        competency_rows=[],
        requirements=[req],
        now=now,
    )
    assert payload["available"] is True
    kinds = {s["kind"] for s in payload["signals"]}
    assert "expired_training_ticket" in kinds
    assert "requirement_theme_overlap" in kinds
    expired = next(s for s in payload["signals"] if s["kind"] == "expired_training_ticket")
    assert expired["theme_label"] == "manual handling strains"
    assert "manual" in expired["shared_tokens"]


def test_due_competency_record_signal():
    row = SimpleNamespace(
        id=44,
        state="due",
        outcome="conditional",
        engineer_id=7,
        requirement_name="Working at Height",
        requirement_id=None,
    )
    payload = build_signals_from_rows(
        theme_labels=["working at height falls"],
        modules=["incident"],
        gaps=[],
        tickets=[],
        competency_rows=[row],
        requirements=[],
    )
    assert payload["available"] is True
    sig = payload["signals"][0]
    assert sig["kind"] == "due_or_expired_competency"
    assert sig["theme_label"] == "working at height falls"
    assert sig["strength"] == "moderate"


def test_active_ticket_without_overlap_is_ignored():
    ticket = SimpleNamespace(
        id=1,
        scheme="First Aid",
        verify_state="verified",
        expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        engineer_id=1,
    )
    payload = build_signals_from_rows(
        theme_labels=["reversing collisions"],
        modules=["rta"],
        gaps=[],
        tickets=[ticket],
        competency_rows=[],
        requirements=[],
    )
    assert payload["available"] is False
    assert payload["signals"] == []


def test_monthly_digest_flag_defaults_on(monkeypatch):
    from src.infrastructure.tasks import safety_insights_tasks as tasks

    monkeypatch.delenv("SAFETY_INSIGHTS_MONTHLY_DIGEST_ENABLED", raising=False)
    assert tasks._monthly_digest_enabled() is True
    monkeypatch.setenv("SAFETY_INSIGHTS_MONTHLY_DIGEST_ENABLED", "0")
    assert tasks._monthly_digest_enabled() is False
    monkeypatch.setenv("SAFETY_INSIGHTS_MONTHLY_DIGEST_ENABLED", "true")
    assert tasks._monthly_digest_enabled() is True
