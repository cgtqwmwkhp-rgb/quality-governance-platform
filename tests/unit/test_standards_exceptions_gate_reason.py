"""PR-E2 — attach ingest gate_reason onto Exceptions inbox rows without inventing."""

from types import SimpleNamespace

from src.domain.services.standards_exceptions_gate_reason import (
    INGEST_GATE_REASONS,
    evidence_map_log_key,
    gate_reason_from_payload,
    is_known_ingest_gate_reason,
    latest_gate_reasons_by_log_key,
)


def test_evidence_map_log_key_matches_persist_mapping_identity():
    assert evidence_map_log_key("document", "42", "7.5") == "document:42:7.5"
    assert evidence_map_log_key("incident", "7", "ISO9001:8.5") == "incident:7:ISO9001:8.5"


def test_gate_reason_from_payload_does_not_invent():
    assert gate_reason_from_payload(None) is None
    assert gate_reason_from_payload("below_threshold") is None
    assert gate_reason_from_payload({}) is None
    assert gate_reason_from_payload({"gate_reason": ""}) is None
    assert gate_reason_from_payload({"gate_reason": "  "}) is None
    assert gate_reason_from_payload({"gate_reason": 12}) is None
    assert gate_reason_from_payload({"gate_reason": "below_threshold"}) == "below_threshold"


def test_latest_gate_reasons_first_seen_wins_when_newest_first():
    logs = [
        SimpleNamespace(
            entity_id="document:1:7.5",
            payload={"gate_reason": "below_threshold"},
        ),
        SimpleNamespace(
            entity_id="document:1:7.5",
            payload={"gate_reason": "matrix_not_loaded"},
        ),
        SimpleNamespace(
            entity_id="document:2:8.1",
            payload={"gate_reason": "alignment_near_requires_addition"},
        ),
        SimpleNamespace(entity_id="document:3:4.1", payload={}),
    ]
    latest = latest_gate_reasons_by_log_key(logs)
    assert latest["document:1:7.5"] == "below_threshold"
    assert latest["document:2:8.1"] == "alignment_near_requires_addition"
    assert "document:3:4.1" not in latest


def test_known_ingest_gate_reasons_cover_pr_e_tokens():
    for token in (
        "below_threshold",
        "matrix_not_loaded",
        "strict_doc_type",
        "alignment_not_exact_for_framework",
        "cover_blocked_open_nc",
        "auto_confirmed",
    ):
        assert token in INGEST_GATE_REASONS
        assert is_known_ingest_gate_reason(token)
    assert not is_known_ingest_gate_reason("invented_reason")
    assert not is_known_ingest_gate_reason(None)
    assert not is_known_ingest_gate_reason("  ")


def test_filter_links_by_gate_reason_excludes_unlogged():
    from src.domain.services.standards_exceptions_gate_reason import filter_links_by_gate_reason

    a = SimpleNamespace(id=1)
    b = SimpleNamespace(id=2)
    c = SimpleNamespace(id=3)
    kept = filter_links_by_gate_reason(
        [a, b, c],
        {1: "below_threshold", 2: None, 3: "matrix_not_loaded"},
        "below_threshold",
    )
    assert [link.id for link in kept] == [1]


def test_sort_inbox_page_confidence_desc_then_created():
    from datetime import datetime, timezone

    from src.domain.services.standards_exceptions_gate_reason import sort_inbox_page_for_triage

    t0 = datetime(2026, 8, 14, 10, 0, tzinfo=timezone.utc)
    t1 = datetime(2026, 8, 14, 11, 0, tzinfo=timezone.utc)
    links = [
        SimpleNamespace(id=1, confidence=0.5, created_at=t1),
        SimpleNamespace(id=2, confidence=0.97, created_at=t0),
        SimpleNamespace(id=3, confidence=0.97, created_at=t1),
        SimpleNamespace(id=4, confidence=None, created_at=t1),
    ]
    ordered = sort_inbox_page_for_triage(links)
    assert [link.id for link in ordered] == [3, 2, 1, 4]
