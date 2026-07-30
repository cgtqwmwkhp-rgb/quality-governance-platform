"""The write-schema extra=forbid ratchet must fail on the regressions it exists for.

Board B-10 / w4-extra-forbid: 284 of 296 write request bodies still accept unknown
fields. The inventory lock does not convert them; it stops the forbid set from
shrinking and the open set from growing. Every failure path is driven from a
synthetic inventory so the committed main baseline is not required for these
tests to mean anything after the next conversion lands.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from validate_write_schema_extra_forbid_ratchet import build_baseline, check_ratchet, main  # noqa: E402


def inventory(
    *,
    forbid: list[str],
    open_schemas: list[str],
    write_operation_count: int = 10,
) -> dict:
    models = sorted(set(forbid) | set(open_schemas))
    return {
        "total_write_schemas": len(models),
        "forbid_count": len(forbid),
        "open_count": len(open_schemas),
        "forbid_schemas": sorted(forbid),
        "open_schemas": sorted(open_schemas),
        "operations_by_schema": {m: [f"POST /api/v1/{m.lower()}"] for m in models},
        "write_operation_count": write_operation_count,
    }


class TestRatchetFailures:
    def test_forbid_count_decrease_fails(self):
        baseline = build_baseline(inventory(forbid=["A", "B"], open_schemas=["C", "D"]))
        current = inventory(forbid=["A"], open_schemas=["B", "C", "D"])

        failures, _warnings = check_ratchet(current, baseline)

        assert any("forbid count fell" in msg for msg in failures)
        assert any("no longer reject" in msg for msg in failures)

    def test_open_count_increase_fails(self):
        baseline = build_baseline(inventory(forbid=["A"], open_schemas=["B", "C"]))
        current = inventory(forbid=["A"], open_schemas=["B", "C", "D"])

        failures, _warnings = check_ratchet(current, baseline)

        assert any("open (non-forbid) write schema count rose" in msg for msg in failures)

    def test_forbid_membership_swap_fails_even_when_counts_flat(self):
        """Counts staying flat must not hide losing forbid on a locked schema."""
        baseline = build_baseline(inventory(forbid=["ActionCreate"], open_schemas=["ComplaintCreate"]))
        current = inventory(forbid=["ComplaintCreate"], open_schemas=["ActionCreate"])

        failures, _warnings = check_ratchet(current, baseline)

        assert any("ActionCreate" in msg and "no longer reject" in msg for msg in failures)

    def test_within_baseline_is_silent(self):
        data = inventory(forbid=["A", "B"], open_schemas=["C", "D", "E"])
        baseline = build_baseline(data)

        failures, warnings = check_ratchet(data, baseline)

        assert failures == []
        assert warnings == []


class TestRatchetWarnings:
    def test_improvement_warns_for_stale_baseline(self):
        baseline = build_baseline(inventory(forbid=["A"], open_schemas=["B", "C", "D"]))
        current = inventory(forbid=["A", "B"], open_schemas=["C", "D"])

        failures, warnings = check_ratchet(current, baseline)

        assert failures == []
        assert any("forbid count rose" in msg for msg in warnings)
        assert any("open count fell" in msg for msg in warnings)


class TestCli:
    def test_main_fails_when_open_count_grows(self, tmp_path: Path):
        baseline_inv = inventory(forbid=["A"], open_schemas=["B", "C"])
        current_inv = inventory(forbid=["A"], open_schemas=["B", "C", "D"])
        baseline_path = tmp_path / "baseline.json"
        inventory_path = tmp_path / "inventory.json"
        baseline_path.write_text(json.dumps(build_baseline(baseline_inv)), encoding="utf-8")
        inventory_path.write_text(json.dumps(current_inv), encoding="utf-8")

        exit_code = main(
            [
                "--baseline",
                str(baseline_path),
                "--from-inventory",
                str(inventory_path),
            ]
        )

        assert exit_code == 1

    def test_main_passes_on_matching_inventory(self, tmp_path: Path):
        data = inventory(forbid=["A", "B"], open_schemas=["C"])
        baseline_path = tmp_path / "baseline.json"
        inventory_path = tmp_path / "inventory.json"
        baseline_path.write_text(json.dumps(build_baseline(data)), encoding="utf-8")
        inventory_path.write_text(json.dumps(data), encoding="utf-8")

        exit_code = main(
            [
                "--baseline",
                str(baseline_path),
                "--from-inventory",
                str(inventory_path),
            ]
        )

        assert exit_code == 0

    def test_write_baseline_round_trip(self, tmp_path: Path):
        data = inventory(
            forbid=["ActionCreate", "ActionUpdate"],
            open_schemas=["ComplaintCreate"],
        )
        inventory_path = tmp_path / "inventory.json"
        baseline_path = tmp_path / "baseline.json"
        inventory_path.write_text(json.dumps(data), encoding="utf-8")

        write_code = main(
            [
                "--baseline",
                str(baseline_path),
                "--from-inventory",
                str(inventory_path),
                "--write-baseline",
            ]
        )
        assert write_code == 0
        check_code = main(
            [
                "--baseline",
                str(baseline_path),
                "--from-inventory",
                str(inventory_path),
            ]
        )
        assert check_code == 0
        payload = json.loads(baseline_path.read_text(encoding="utf-8"))
        assert payload["min_forbid_count"] == 2
        assert payload["max_open_count"] == 1
        assert payload["forbid_schemas"] == ["ActionCreate", "ActionUpdate"]


def test_committed_baseline_shape() -> None:
    root = Path(__file__).resolve().parents[2]
    baseline = root / "docs/governance/write_schema_extra_forbid_baseline.json"
    inventory_md = root / "docs/governance/write_schema_extra_forbid_inventory.md"
    assert baseline.is_file()
    assert inventory_md.is_file()
    payload = json.loads(baseline.read_text(encoding="utf-8"))
    assert payload["min_forbid_count"] == 12
    assert payload["max_open_count"] == 284
    assert payload["total_write_schemas"] == 296
    assert payload["forbid_schemas"] == [        "AcknowledgementAction",
        "AcknowledgementCreate",
        "ActionCreate",
        "ActionOwnerNoteCreate",
        "ActionUpdate",
        "AddCauseRequest",
        "AddCertificationRequest",
        "AddTrainingRequest",
        "AddWhyRequest",
        "AllocationRequest",
        "CreateExportRequest",
        "CreateFindingCapaRequest",
    ]
