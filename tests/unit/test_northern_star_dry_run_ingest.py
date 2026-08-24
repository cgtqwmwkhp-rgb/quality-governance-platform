"""Tests for Northern Star W5b dry-run ingest (no DB writes)."""

from __future__ import annotations

import json
from pathlib import Path

from scripts.governance.library.northern_star_dry_run_ingest import run_dry_run

_FIXTURE = {
    "documents": [
        {
            "pel_ref": "PEL-HSEQ-3001",
            "function": "HSEQ",
            "level_num": 3,
            "access": "all_staff",
            "proposed_filename": "PEL-HSEQ-3001 Example Procedure v1.pdf",
            "parent_ref": "PEL-HSEQ-2001",
        },
        {
            "pel_ref": "PEL-IT-2005",
            "function": "IT",
            "level_num": 5,
            "access": "managers",
            "proposed_filename": "PEL-IT-2005 ISO 27001 - Statement of Applicability v1.pdf",
            "parent_ref": None,
        },
    ],
    "relationships": [
        {
            "from": "PEL-HSEQ-3001",
            "to": "PEL-HSEQ-2001",
            "type": "Child of",
            "target_kind": "document",
        },
        {
            "from": "PEL-IT-2005",
            "to": "PEL-IT-2005",
            "type": "Supersedes",
            "target_kind": "document",
        },
        {
            "from": "PEL-HSEQ-3001",
            "to": "PEL-HSEQ-1001",
            "type": "Child of",
            "target_kind": "document",
        },
    ],
}


def test_dry_run_flags_self_loop_r02_and_second_parent():
    report = run_dry_run(_FIXTURE, pack_path=Path("fixture.json"))
    codes = {f.code for f in report.findings}
    assert "SELF_LOOP" in codes
    assert "R02" in codes
    assert "SECOND_PARENT" in codes
    assert report.critical_count >= 2
    assert report.counters["supersedes_self_loops"] == 1
    assert report.counters["multi_parent_children"] == 1


def test_live_pack_has_no_self_loops_after_w5b_fix():
    pack_path = Path(__file__).resolve().parents[2] / "specs" / "governance-library" / "northern-star-v6.json"
    pack = json.loads(pack_path.read_text(encoding="utf-8"))
    report = run_dry_run(pack, pack_path=pack_path)
    assert report.document_count == 388
    assert report.counters["supersedes_self_loops"] == 0
    assert report.counters["multi_parent_children"] == 14
    # Known frozen allocation defect — steward reissue, not silent renumber (R29).
    assert any(f.code == "R02" and "PEL-IT-2005" in f.refs for f in report.findings)
