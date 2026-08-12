"""Unit tests for Standards cell aggregate cover gate + matching (PR-B)."""

from datetime import datetime, timedelta, timezone

from src.domain.services.standards_cell_aggregate_service import (
    classify_audit_kind,
    clause_match_keys,
    compute_cell_verdict,
    detect_recurrence,
    normalize_clause_token,
    token_matches_clause,
)


def test_normalize_and_match_keys():
    keys = clause_match_keys("9001", "7.5")
    assert normalize_clause_token("7.5") in keys
    assert normalize_clause_token("9001-7.5") in keys
    assert token_matches_clause("9001-7.5", keys, "7.5")
    assert token_matches_clause("7.5", keys, "7.5")
    assert token_matches_clause("7.5.1", keys, "7.5")
    assert not token_matches_clause("8.1", keys, "7.5")


def test_classify_audit_kind_mock_imported_internal():
    assert classify_audit_kind(assessment_mode="mock", source_origin=None, template_tags=None) == "mock"
    assert classify_audit_kind(assessment_mode=None, source_origin=None, template_tags=["mock"]) == "mock"
    assert (
        classify_audit_kind(
            assessment_mode=None,
            source_origin="external_import",
            template_tags=None,
        )
        == "imported"
    )
    assert (
        classify_audit_kind(
            assessment_mode="field",
            source_origin=None,
            template_tags=["internal"],
            is_external_import=True,
        )
        == "imported"
    )
    assert classify_audit_kind(assessment_mode="field", source_origin=None, template_tags=None) == "internal"


def test_open_nc_or_action_never_covered():
    blocked = compute_cell_verdict(
        open_nc_count=1,
        open_action_count=0,
        recurrence=False,
        conformance_evidence_count=5,
        mock_gap_count=0,
        closed_nc_count=0,
    )
    assert blocked["verdict"] == "gap"
    assert blocked["cover_blocked"] is True

    action_only = compute_cell_verdict(
        open_nc_count=0,
        open_action_count=2,
        recurrence=False,
        conformance_evidence_count=5,
        mock_gap_count=0,
        closed_nc_count=0,
    )
    assert action_only["verdict"] == "partial"
    assert action_only["cover_blocked"] is True
    assert action_only["verdict"] != "covered"


def test_covered_when_evidence_and_no_open_issues():
    ok = compute_cell_verdict(
        open_nc_count=0,
        open_action_count=0,
        recurrence=False,
        conformance_evidence_count=2,
        mock_gap_count=0,
        closed_nc_count=0,
    )
    assert ok["verdict"] == "covered"
    assert ok["cover_blocked"] is False


def test_mock_gaps_paint_honestly():
    mock = compute_cell_verdict(
        open_nc_count=0,
        open_action_count=0,
        recurrence=False,
        conformance_evidence_count=0,
        mock_gap_count=1,
        closed_nc_count=0,
    )
    assert mock["verdict"] == "gap"
    assert "mock_gap" in mock["reasons"]


def test_recurrence_red_flag_after_close():
    now = datetime.now(timezone.utc)
    events = [
        {"status": "closed", "created_at": now - timedelta(days=30), "closed_at": now - timedelta(days=20)},
        {"status": "open", "created_at": now - timedelta(days=2), "closed_at": None},
    ]
    assert detect_recurrence(events) is True
    assert detect_recurrence([{"status": "open", "created_at": now}]) is False

    with_recurrence = compute_cell_verdict(
        open_nc_count=1,
        open_action_count=0,
        recurrence=True,
        conformance_evidence_count=1,
        mock_gap_count=0,
        closed_nc_count=1,
    )
    assert with_recurrence["recurrence_red_flag"] is True
    assert with_recurrence["verdict"] == "gap"
