"""The audit-trail coverage ratchet must fail on the regressions it exists for.

Board w1-px155 / PX-155: measure wired vs silent ``record_audit_event`` sites,
``log_auth`` callers, and product-module coverage. The inventory lock does not
wire every uncovered module; it stops wired/auth/module floors from falling and
silent sites from rising.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from validate_audit_trail_coverage_ratchet import (  # noqa: E402
    build_baseline,
    check_ratchet,
    inventory_audit_coverage,
    main,
)


def inventory(
    *,
    wired: int,
    silent: int,
    log_auth: int,
    covered: list[str],
    uncovered: list[str] | None = None,
) -> dict:
    uncovered = uncovered or []
    return {
        "record_audit_event_total": wired + silent,
        "wired_record_audit_event_count": wired,
        "silent_record_audit_event_count": silent,
        "log_auth_caller_count": log_auth,
        "other_audit_log_write_count": 0,
        "product_module_count": len(covered) + len(uncovered),
        "covered_module_count": len(covered),
        "uncovered_module_count": len(uncovered),
        "covered_modules": list(covered),
        "uncovered_modules": list(uncovered),
        "wired_sites": [],
        "silent_sites": [],
        "log_auth_sites": [],
        "other_audit_log_write_sites": [],
    }


class TestRatchetFailures:
    def test_wired_count_decrease_fails(self):
        baseline = build_baseline(inventory(wired=10, silent=0, log_auth=1, covered=["Incidents", "CAPA"]))
        current = inventory(wired=9, silent=0, log_auth=1, covered=["Incidents", "CAPA"])

        failures, _warnings = check_ratchet(current, baseline)

        assert any("wired record_audit_event count fell" in msg for msg in failures)

    def test_silent_count_increase_fails(self):
        baseline = build_baseline(inventory(wired=10, silent=0, log_auth=1, covered=["Incidents"]))
        current = inventory(wired=10, silent=1, log_auth=1, covered=["Incidents"])

        failures, _warnings = check_ratchet(current, baseline)

        assert any("silent record_audit_event count rose" in msg for msg in failures)

    def test_log_auth_decrease_fails(self):
        baseline = build_baseline(inventory(wired=10, silent=0, log_auth=2, covered=["Auth"]))
        current = inventory(wired=10, silent=0, log_auth=0, covered=["Auth"])

        failures, _warnings = check_ratchet(current, baseline)

        assert any("log_auth caller count fell" in msg for msg in failures)

    def test_covered_module_loss_fails(self):
        baseline = build_baseline(inventory(wired=10, silent=0, log_auth=1, covered=["Incidents", "CAPA"]))
        current = inventory(wired=10, silent=0, log_auth=1, covered=["Incidents"])

        failures, _warnings = check_ratchet(current, baseline)

        assert any("lost audit writers" in msg for msg in failures)
        assert any("CAPA" in msg for msg in failures)

    def test_within_baseline_is_silent(self):
        data = inventory(
            wired=12,
            silent=0,
            log_auth=1,
            covered=["Incidents", "CAPA", "Auth"],
            uncovered=["KRI"],
        )
        baseline = build_baseline(data)

        failures, warnings = check_ratchet(data, baseline)

        assert failures == []
        assert warnings == []


class TestRatchetWarnings:
    def test_improvement_warns_for_stale_baseline(self):
        baseline = build_baseline(inventory(wired=10, silent=2, log_auth=1, covered=["Incidents"]))
        current = inventory(
            wired=12,
            silent=0,
            log_auth=2,
            covered=["Incidents", "Auth"],
            uncovered=[],
        )

        failures, warnings = check_ratchet(current, baseline)

        assert failures == []
        assert any("wired count rose" in msg for msg in warnings)
        assert any("silent count fell" in msg for msg in warnings)
        assert any("log_auth callers rose" in msg for msg in warnings)


class TestLiveInventory:
    def test_repo_inventory_has_sites_and_modules(self):
        current = inventory_audit_coverage()

        assert current["record_audit_event_total"] > 20
        assert current["wired_record_audit_event_count"] == current["record_audit_event_total"]
        assert current["silent_record_audit_event_count"] == 0
        assert current["log_auth_caller_count"] >= 1
        assert current["product_module_count"] >= 20
        assert current["covered_module_count"] >= 1
        assert "User Management & Authentication" in current["covered_modules"]

    def test_main_write_baseline_roundtrip(self, tmp_path: Path):
        baseline = tmp_path / "baseline.json"
        markdown = tmp_path / "inventory.md"
        rc = main(["--write-baseline", "--baseline", str(baseline), "--markdown", str(markdown)])
        assert rc == 0
        assert baseline.is_file()
        payload = json.loads(baseline.read_text(encoding="utf-8"))
        assert payload["max_silent_record_audit_event_count"] == 0
        assert payload["min_log_auth_caller_count"] >= 1
        rc2 = main(["--baseline", str(baseline)])
        assert rc2 == 0
