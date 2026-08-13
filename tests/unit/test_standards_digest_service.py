"""Unit tests for Standards Monitoring digests (Wave 3 PR-F3) — pure roll-ups."""

from datetime import datetime, timedelta, timezone

from src.domain.services.standards_digest_service import (
    roll_up_cert_expiry,
    roll_up_freshness,
    roll_up_ingest_backlog,
    roll_up_nonconformities,
    safe_rate,
)


def test_safe_rate_null_when_denominator_zero():
    assert safe_rate(1, 0) is None
    assert safe_rate(0, 0) is None
    assert safe_rate(1, 4) == 0.25


def test_bare_clause_token_is_unattributed_not_9001():
    findings = [
        {
            "id": 1,
            "finding_type": "nonconformity",
            "status": "open",
            "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "clause_tokens": ["7.5"],
        }
    ]
    result = roll_up_nonconformities(findings, row_limit=10)
    assert result["open_nc_total"] == 1
    assert result["clauses_with_open_nc"] == 1
    assert result["by_clause"][0]["framework"] is None
    assert result["by_clause"][0]["clause_number"] == "7.5"
    assert result["unattributed_open_nc"] == 1
    assert all(row["framework"] != "9001" for row in result["by_clause"])


def test_framework_token_lands_only_in_declared_framework():
    findings = [
        {
            "id": 2,
            "finding_type": "nonconformity",
            "status": "open",
            "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "clause_tokens": ["14001-9.1.2"],
        }
    ]
    result = roll_up_nonconformities(findings, row_limit=10)
    assert result["by_clause"][0]["framework"] == "14001"
    assert result["by_clause"][0]["clause_number"] == "9.1.2"
    assert result["by_clause"][0]["open_nc_count"] == 1


def test_one_finding_two_frameworks_counts_once_in_total():
    findings = [
        {
            "id": 3,
            "finding_type": "nonconformity",
            "status": "open",
            "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "clause_tokens": ["9001-8.7", "14001-8.7"],
        }
    ]
    result = roll_up_nonconformities(findings, row_limit=10)
    assert result["open_nc_total"] == 1
    assert result["clauses_with_open_nc"] == 2
    assert sum(row["open_nc_count"] for row in result["by_clause"]) == 2


def test_duplicate_tokens_same_cell_do_not_double_count():
    findings = [
        {
            "id": 4,
            "finding_type": "nonconformity",
            "status": "open",
            "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "clause_tokens": ["9001-7.5", "iso9001:7.5", "9001-7.5"],
        }
    ]
    result = roll_up_nonconformities(findings, row_limit=10)
    assert len(result["by_clause"]) == 1
    assert result["by_clause"][0]["open_nc_count"] == 1


def test_recurrence_after_close_reopen():
    findings = [
        {
            "id": 10,
            "finding_type": "nonconformity",
            "status": "closed",
            "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 2, 1, tzinfo=timezone.utc),
            "clause_tokens": ["9001-8.7"],
        },
        {
            "id": 11,
            "finding_type": "nonconformity",
            "status": "open",
            "created_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 3, 1, tzinfo=timezone.utc),
            "clause_tokens": ["9001-8.7"],
        },
    ]
    result = roll_up_nonconformities(findings, row_limit=10)
    assert result["recurring_clauses"] == 1
    assert result["clauses_with_nc_history"] == 1
    assert result["recurrence_rate"] == 1.0
    assert result["by_clause"][0]["recurrence"] is True


def test_recurrence_rate_null_without_history():
    result = roll_up_nonconformities([], row_limit=10)
    assert result["recurrence_rate"] is None
    assert result["open_nc_total"] == 0


def test_observation_excluded_unknown_type_included():
    findings = [
        {
            "id": 20,
            "finding_type": "observation",
            "status": "open",
            "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "clause_tokens": ["9001-4.1"],
        },
        {
            "id": 21,
            "finding_type": None,
            "status": "open",
            "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "clause_tokens": ["9001-4.2"],
        },
    ]
    result = roll_up_nonconformities(findings, row_limit=10)
    assert result["open_nc_total"] == 1
    assert result["by_clause"][0]["clause_number"] == "4.2"


def test_open_without_clause_token():
    findings = [
        {
            "id": 30,
            "finding_type": "nonconformity",
            "status": "open",
            "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "updated_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
            "clause_tokens": [],
        }
    ]
    result = roll_up_nonconformities(findings, row_limit=10)
    assert result["open_nc_without_clause_token"] == 1
    assert result["by_clause"] == []


def test_freshness_buckets_and_stale_rate():
    links = [
        {"id": 1, "clause_id": "9001-7.5", "pinned_document_version_id": 10, "document_id": 1},
        {"id": 2, "clause_id": "9001-8.1", "pinned_document_version_id": 11, "document_id": 2},
        {"id": 3, "clause_id": "9001-9.1", "pinned_document_version_id": None, "document_id": 3},
        {"id": 4, "clause_id": "9001-10.1", "pinned_document_version_id": 12, "document_id": 4},
    ]
    tips = {
        1: (10, "1.0"),
        2: (99, "2.0"),
        3: (5, "1.0"),
        # 4 missing tip → unknown
    }
    result = roll_up_freshness(links, tips, row_limit=10, titles={2: "Control of docs"})
    assert result["current"] == 1
    assert result["stale"] == 1
    assert result["unpinned"] == 1
    assert result["unknown"] == 1
    assert result["stale_rate"] == 0.5
    assert result["stale_items"][0]["document_id"] == 2
    assert result["stale_items"][0]["title"] == "Control of docs"


def test_freshness_stale_rate_null_without_resolvable_tips():
    links = [
        {"id": 1, "clause_id": "9001-7.5", "pinned_document_version_id": None, "document_id": 1},
    ]
    result = roll_up_freshness(links, {}, row_limit=10)
    assert result["stale_rate"] is None


def test_ingest_backlog_effective_status_and_age():
    now = datetime(2026, 8, 12, tzinfo=timezone.utc)
    links = [
        {
            "id": 1,
            "clause_id": "9001-7.5",
            "effective_status": "proposed",
            "linked_by": "ai",
            "signal_type": "conformance",
            "created_at": now - timedelta(days=10),
        },
        {
            "id": 2,
            "clause_id": "9001-7.5",
            "effective_status": "needs_review",
            "linked_by": "auto",
            "signal_type": "nonconformity",
            "created_at": now - timedelta(days=41),
        },
        {
            "id": 3,
            "clause_id": "14001-6.1",
            "effective_status": "proposed",
            "linked_by": "manual",
            "signal_type": "gap",
            "created_at": now - timedelta(days=2),
        },
    ]
    result = roll_up_ingest_backlog(links, now=now, row_limit=10)
    assert result["total"] == 3
    assert result["by_status"]["proposed"] == 2
    assert result["by_status"]["needs_review"] == 1
    assert result["by_link_method"]["ai"] == 1
    assert result["operational_signals"] == 2
    assert result["conformance_candidates"] == 1
    assert result["oldest_age_days"] == 41
    assert result["by_clause"][0]["clause_id"] == "9001-7.5"
    assert result["by_clause"][0]["count"] == 2
    assert result["auto_confirm_threshold"] == 0.98


def test_cert_expiry_board_orders_soonest():
    now = datetime(2026, 8, 12, tzinfo=timezone.utc)
    shelf = {
        "summary": {"valid": 1, "due_soon": 1, "expired": 1, "unknown": 0},
        "items": [
            {
                "shelf_key": "register:1",
                "name": "ISO 9001",
                "scheme": "register",
                "expiry_date": "2026-09-01",
                "readiness_status": "due_soon",
                "is_critical": True,
            },
            {
                "shelf_key": "register:2",
                "name": "Expired cert",
                "scheme": "register",
                "expiry_date": "2026-07-01",
                "readiness_status": "expired",
                "is_critical": False,
            },
            {
                "shelf_key": "uvdb:1",
                "name": "UVDB",
                "scheme": "uvdb",
                "expiry_date": "2027-01-01",
                "readiness_status": "valid",
                "is_critical": False,
            },
        ],
    }
    result = roll_up_cert_expiry(shelf, now=now, row_limit=10)
    assert result["tracked"] == 3
    assert result["due_soon"] == 1
    assert result["expired"] == 1
    assert result["soonest"][0]["name"] == "Expired cert"
    assert result["soonest"][0]["days_remaining"] < 0
    assert result["soonest"][0]["scheme"] == "operational"
    assert result["soonest"][1]["name"] == "ISO 9001"
    assert result["soonest"][1]["scheme"] == "9001"
    assert any(row["scheme"] == "uvdb" and row["tracked"] == 1 for row in result["by_scheme"])
    assert any(row["scheme"] == "9001" and row["tracked"] == 1 for row in result["by_scheme"])
    assert all(row["scheme"] != "register" for row in result["by_scheme"])


def test_cert_digest_does_not_feed_pat_into_iso_or_chas():
    """Int-W7: typed feeds. PAT/insurance stay operational; ISO 9001 is its own scheme."""
    now = datetime(2026, 8, 12, tzinfo=timezone.utc)
    shelf = {
        "summary": {"valid": 2, "due_soon": 1, "expired": 0, "unknown": 0},
        "items": [
            {
                "shelf_key": "register:pat",
                "name": "Portable Appliance Test",
                "scheme": "register",
                "expiry_date": "2026-09-01",
                "readiness_status": "due_soon",
                "metadata": {"certificate_type": "PAT"},
            },
            {
                "shelf_key": "register:ins",
                "name": "Employers Liability",
                "scheme": "register",
                "expiry_date": "2027-01-01",
                "readiness_status": "valid",
                "metadata": {"certificate_type": "insurance"},
            },
            {
                "shelf_key": "register:iso",
                "name": "Quality management",
                "scheme": "register",
                "expiry_date": "2027-06-01",
                "readiness_status": "valid",
                "metadata": {"certificate_type": "ISO 9001:2015"},
            },
        ],
    }
    result = roll_up_cert_expiry(shelf, now=now, row_limit=10)
    by_scheme = {row["scheme"]: row for row in result["by_scheme"]}
    assert "9001" in by_scheme
    assert by_scheme["9001"]["tracked"] == 1
    assert by_scheme["9001"]["kind"] == "framework_certificate"
    assert "operational" in by_scheme
    assert by_scheme["operational"]["tracked"] == 2
    assert by_scheme["operational"]["kind"] == "operational"
    assert "chas" not in by_scheme
    assert "register" not in by_scheme
    assert result["soonest"][0]["scheme"] == "operational"
    assert result["soonest"][0]["name"] == "Portable Appliance Test"


def test_row_cap_preserves_total_clause_count():
    findings = []
    for i in range(23):
        findings.append(
            {
                "id": 100 + i,
                "finding_type": "nonconformity",
                "status": "open",
                "created_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
                "updated_at": datetime(2026, 8, 1, tzinfo=timezone.utc),
                "clause_tokens": [f"9001-8.{i}"],
            }
        )
    result = roll_up_nonconformities(findings, row_limit=10)
    assert result["clauses_with_open_nc"] == 23
    assert len(result["by_clause"]) == 10
