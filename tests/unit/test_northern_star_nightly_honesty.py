"""Tests for Northern Star W9 nightly honesty reports (no DB writes)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.library.northern_star_nightly_honesty import (
    HonestyReport,
    assert_delivery_guard,
    load_baseline,
    run_honesty_report,
)

_REPO = Path(__file__).resolve().parents[2]
_PACK = _REPO / "specs" / "governance-library" / "northern-star-v6.json"


def _fixture_pack() -> dict:
    return {
        "documents": [
            {
                "pel_ref": "PEL-HSEQ-2001",
                "type": "Policy",
                "level_num": 2,
                "status": "Issued",
                "delivery": "Controlled document",
                "external_origin": False,
                "legacy_ref": None,
                "review_cycle_months": 12,
                "parent_ref": "PEL-HSEQ-1001",
            },
            {
                "pel_ref": "PEL-HSEQ-1001",
                "type": "Manual",
                "level_num": 1,
                "status": "Issued",
                "delivery": "Controlled document",
                "external_origin": False,
                "legacy_ref": "IMS 001",
                "review_date": None,
            },
            {
                "pel_ref": "PEL-DP-2001",
                "type": "Statement",
                "level_num": 2,
                "status": "Migration pending",
                "delivery": "Controlled document",
                "external_origin": False,
                "legacy_ref": None,
            },
            {
                "pel_ref": "PEL-PROC-3001",
                "type": "Procedure",
                "level_num": 3,
                "status": "Migration pending",
                "delivery": "Controlled document",
                "external_origin": False,
                "legacy_ref": "IMS 001",
                "parent_ref": "PEL-HSEQ-2001",
            },
        ],
        "relationships": [
            {
                "from": "PEL-PROC-3001",
                "to": "PEL-HSEQ-2001",
                "type": "Child of",
                "target_kind": "document",
            }
        ],
    }


def test_fixture_reports_r08_r25_r30_honesty():
    report = run_honesty_report(_fixture_pack(), pack_path=Path("fixture.json"))
    assert report.writes is False
    assert report.counters["r08_gaps"] == 0  # policy has L3 child
    assert report.counters["r25_issued"] == 2
    assert report.counters["r25_issued_missing_review_date"] == 2
    assert report.counters["r25_overdue_computed"] == 0
    # IMS 001 maps to two PELs → ambiguous; coverage gaps for docs without legacy_ref
    assert report.counters["r30_ambiguous_tokens"] == 1
    assert report.counters["r30_gap_total"] >= 2
    codes = {f.code for f in report.findings}
    assert "R25" in codes
    assert "R30" in codes


def test_fixture_r08_gap_when_policy_has_no_l3_child():
    pack = _fixture_pack()
    pack["documents"] = [d for d in pack["documents"] if d["pel_ref"] != "PEL-PROC-3001"]
    pack["relationships"] = []
    report = run_honesty_report(pack, pack_path=Path("fixture.json"))
    assert report.counters["r08_gaps"] == 1
    assert any(f.code == "R08" and "PEL-HSEQ-2001" in f.refs for f in report.findings)


def test_live_pack_honesty_pins_and_guard_passes():
    pack = json.loads(_PACK.read_text(encoding="utf-8"))
    report = run_honesty_report(pack, pack_path=_PACK)
    assert report.document_count == 388
    assert report.writes is False
    # Known estate debt — never silent green
    assert report.counters["r08_gaps"] == 30
    assert report.counters["r25_issued_missing_review_date"] == 8
    assert report.counters["r25_pack_missing_review_date"] == 388
    assert report.counters["r25_overdue_computed"] == 0
    # Master plan ~135; pack measures controlled coverage gaps honestly (higher).
    assert report.counters["r30_gap_total"] >= 135
    assert report.counters["r30_gap_total"] == 220
    failures = assert_delivery_guard(report, load_baseline())
    assert failures == []


def test_delivery_guard_rejects_fabricated_zeros():
    clean = HonestyReport(
        pack_path="x",
        document_count=0,
        counters={
            "r08_gaps": 0,
            "r25_issued_missing_review_date": 0,
            "r25_pack_missing_review_date": 10,
            "r25_overdue_computed": 0,
            "r30_gap_total": 0,
        },
    )
    failures = assert_delivery_guard(clean, load_baseline())
    assert any("r08_gaps" in f for f in failures)
    assert any("r30_gap_total" in f for f in failures)
