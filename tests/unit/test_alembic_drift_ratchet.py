"""The drift ratchet must fail on the things it was built to catch.

``scripts/validate_alembic_drift_ratchet.py`` exists because the migration drift
gate was green while 1060 autogenerate operations were being suppressed. A gate
whose failure path is untested is the same defect one level up: it would report the
suppressed count honestly and still never block anything.

So every failure condition is driven here from a synthetic inventory, and each test
names the regression it stands for. The committed baseline is not used — these
build their own, because a test that passes only against today's 209-table baseline
stops testing anything the moment a migration lands.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from validate_alembic_drift_ratchet import (  # noqa: E402
    _check_add_column_ops,
    _check_excluded_table_ratchet,
    _check_exclusion_register,
    _check_ratchet,
    _check_unsuppressed_drift,
    build_baseline,
    load_inventory,
    main,
)

# ---------------------------------------------------------------------------
# Fixtures: the smallest inventory shape the script reads
# ---------------------------------------------------------------------------


def summary(by_table: dict[str, dict[str, int]]) -> dict:
    """A summary block in the shape ``alembic/env.py`` writes."""
    by_operation: dict[str, int] = {}
    for ops in by_table.values():
        for op_type, count in ops.items():
            by_operation[op_type] = by_operation.get(op_type, 0) + count
    return {
        "total_operations": sum(by_operation.values()),
        "tables_with_drift": len(by_table),
        "by_operation": dict(sorted(by_operation.items())),
        "by_table": by_table,
    }


BASELINE_TABLES = {
    "risks_v2": {"AlterColumnOp": 3, "CreateIndexOp": 1},
    "users": {"AlterColumnOp": 2},
}


def write_inventory(path: Path, by_table: dict, after: dict | None = None) -> Path:
    payload = {
        "before_filter": [],
        "after_filter": [],
        "summary_before_filter": summary(by_table),
        "summary_after_filter": summary(after or {}),
        "excluded_tables": [],
        "filter_enabled": True,
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def write_baseline(path: Path, tables: dict, excluded_drift: dict | None = None) -> Path:
    payload = build_baseline(summary(tables), excluded_drift, set())
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# The query-breaking class
# ---------------------------------------------------------------------------


class TestAddColumnOpIsNeverTolerated:
    """A declared column the database lacks makes the whole table unreadable.

    SQLAlchemy emits every mapped column for a whole-entity load, so this is not
    "one query is wrong", it is ``UndefinedColumn`` on any ``select(Model)``. The
    count on main is zero, which is what makes zero tolerance affordable.
    """

    def test_an_add_column_op_fails_even_at_a_count_of_one(self):
        failures = _check_add_column_ops(summary({"capa_items": {"AddColumnOp": 1}}))

        assert failures, "a declared-but-absent column was tolerated"
        assert "capa_items" in failures[0]
        assert "AddColumnOp" in failures[0]

    def test_it_fails_regardless_of_what_the_baseline_says(self, tmp_path):
        """The ratchet is bypassed for this class on purpose.

        If baselining were allowed here, the number would grow the same way the
        209-table suppression did, one justified case at a time.
        """
        inventory = write_inventory(tmp_path / "inv.json", {"users": {"AddColumnOp": 1, "AlterColumnOp": 2}})
        baseline = write_baseline(tmp_path / "base.json", {"users": {"AddColumnOp": 1, "AlterColumnOp": 2}})

        exit_code = main(["--inventory", str(inventory), "--baseline", str(baseline)])

        assert exit_code == 1, "an AddColumnOp recorded in the baseline still passed"

    def test_no_add_column_ops_is_silent(self):
        assert _check_add_column_ops(summary({"users": {"AlterColumnOp": 9}})) == []


# ---------------------------------------------------------------------------
# The ratchet itself
# ---------------------------------------------------------------------------


class TestTheSuppressedSetCannotGrow:
    def test_a_table_acquiring_drift_fails(self):
        current = summary({**BASELINE_TABLES, "brand_new_table": {"AlterColumnOp": 1}})

        failures, _ = _check_ratchet(current, {"tables": BASELINE_TABLES})

        assert any("brand_new_table" in f for f in failures)

    def test_a_new_operation_type_on_a_known_table_fails(self):
        """The dangerous shape: a table already deferred for index noise starts
        losing columns, and a table-level "already known" would have hidden it."""
        current = summary({**BASELINE_TABLES, "users": {"AlterColumnOp": 2, "DropColumnOp": 1}})

        failures, _ = _check_ratchet(current, {"tables": BASELINE_TABLES})

        assert any("DropColumnOp" in f and "users" in f for f in failures)

    def test_a_rising_count_fails(self):
        current = summary({**BASELINE_TABLES, "users": {"AlterColumnOp": 3}})

        failures, _ = _check_ratchet(current, {"tables": BASELINE_TABLES})

        assert any("rose from 2 to 3" in f for f in failures)

    def test_an_unchanged_set_passes(self):
        failures, warnings = _check_ratchet(summary(BASELINE_TABLES), {"tables": BASELINE_TABLES})

        assert failures == []
        assert warnings == []


class TestShrinkingDriftIsNotPunished:
    """Landing a migration must never turn the gate red.

    That is how mutes grow: if fixing drift costs a red build and a baseline
    refresh, the cheaper move is always to add another exclusion.
    """

    def test_a_falling_count_warns_and_does_not_fail(self):
        current = summary({**BASELINE_TABLES, "users": {"AlterColumnOp": 1}})

        failures, warnings = _check_ratchet(current, {"tables": BASELINE_TABLES})

        assert failures == []
        assert any("fell from 2 to 1" in w for w in warnings)

    def test_a_table_losing_all_drift_warns_and_does_not_fail(self, tmp_path):
        inventory = write_inventory(tmp_path / "inv.json", {"users": {"AlterColumnOp": 2}})
        baseline = write_baseline(tmp_path / "base.json", BASELINE_TABLES)

        exit_code = main(["--inventory", str(inventory), "--baseline", str(baseline)])

        assert exit_code == 0, "removing drift entirely was treated as a violation"


# ---------------------------------------------------------------------------
# Drift that got past the filter
# ---------------------------------------------------------------------------


class TestUnsuppressedDriftStillFails:
    def test_a_non_empty_after_filter_fails(self):
        """`alembic check` fails on this by itself. Restated because this file's
        premise is that a gate upstream may have stopped doing what its name says."""
        failures = _check_unsuppressed_drift(summary({"users": {"CreateTableOp": 1}}))

        assert failures and "survived the filter" in failures[0]

    def test_an_empty_after_filter_is_silent(self):
        assert _check_unsuppressed_drift(summary({})) == []


# ---------------------------------------------------------------------------
# The register cannot be widened silently
# ---------------------------------------------------------------------------


class TestTheExclusionRegisterMustMatchItsDocumentation:
    def test_an_undocumented_exclusion_fails(self):
        failures = _check_exclusion_register({"users", "sneaky_table"}, {"users"})

        assert failures and "sneaky_table" in failures[0]

    def test_a_documented_table_that_is_not_excluded_fails(self):
        """A row claiming the gate is muted where it is not misleads the next reader."""
        failures = _check_exclusion_register({"users"}, {"users", "already_fixed"})

        assert failures and "already_fixed" in failures[0]

    def test_agreement_is_silent(self):
        assert _check_exclusion_register({"users"}, {"users"}) == []

    def test_the_real_register_and_the_real_document_agree(self):
        """Pins the repository's own state, so the two cannot drift apart in a PR
        that never runs the alembic-check job."""
        from validate_alembic_drift_ratchet import documented_exclusions

        sys.path.append(str(Path(__file__).resolve().parents[2]))
        from scripts.ops.run025._models import alembic_check_excluded_tables

        assert _check_exclusion_register(set(alembic_check_excluded_tables()), documented_exclusions()) == []


class TestExcludedTablesAreRatchetedToo:
    """The exclusion list hides column drift, so it needs its own ceiling.

    ``soa_control_entries`` carries four ``AddColumnOp`` that no gate mentions
    because the table is excluded from the comparison outright. Zero tolerance is
    not applied there — it is already a recorded decision with a named owner — but
    a second table joining that class must fail.
    """

    def test_a_second_table_gaining_add_column_drift_fails(self):
        failures, _ = _check_excluded_table_ratchet(
            {"soa_control_entries": {"AddColumnOp": 4}, "ims_controls": {"AddColumnOp": 1}},
            {"soa_control_entries": {"AddColumnOp": 4}},
        )

        assert any("ims_controls" in f and "query-breaking" in f for f in failures)

    def test_the_recorded_case_passes_unchanged(self):
        failures, _ = _check_excluded_table_ratchet(
            {"soa_control_entries": {"AddColumnOp": 4}},
            {"soa_control_entries": {"AddColumnOp": 4}},
        )

        assert failures == []

    def test_an_exclusion_with_no_drift_left_is_reported_as_removable(self):
        _, warnings = _check_excluded_table_ratchet({}, {"security_incident": {"AlterColumnOp": 1}})

        assert any("stale" in w and "security_incident" in w for w in warnings)


# ---------------------------------------------------------------------------
# Refusing to report on a comparison that did not happen
# ---------------------------------------------------------------------------


class TestTheGateRefusesToGuess:
    def test_a_missing_inventory_fails_rather_than_passing_empty(self, tmp_path):
        """An absent artifact reads as "no drift" to anything that defaults to
        zero, which would make a crashed `alembic check` look like a clean one."""
        exit_code = main(["--inventory", str(tmp_path / "nope.json"), "--baseline", str(tmp_path / "b.json")])

        assert exit_code == 1

    def test_an_inventory_without_summaries_fails(self, tmp_path):
        path = tmp_path / "old.json"
        path.write_text(json.dumps({"before_filter": [], "after_filter": []}), encoding="utf-8")

        exit_code = main(["--inventory", str(path), "--baseline", str(tmp_path / "b.json")])

        assert exit_code == 1

    def test_an_inventory_missing_a_required_key_is_rejected(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text(json.dumps({"before_filter": []}), encoding="utf-8")

        with pytest.raises(Exception, match="after_filter"):
            load_inventory(path)

    def test_a_missing_baseline_fails(self, tmp_path):
        inventory = write_inventory(tmp_path / "inv.json", {"users": {"AlterColumnOp": 1}})

        exit_code = main(["--inventory", str(inventory), "--baseline", str(tmp_path / "absent.json")])

        assert exit_code == 1


class TestTheCommittedBaselineDescribesTheRepository:
    def test_the_baseline_records_no_add_column_ops(self):
        """If this ever fails, the zero-tolerance rule above has been baselined
        around rather than fixed."""
        root = Path(__file__).resolve().parents[2]
        baseline = json.loads((root / "docs/governance/alembic_drift_baseline.json").read_text(encoding="utf-8"))

        assert baseline["by_operation"].get("AddColumnOp", 0) == 0
        assert not [t for t, ops in baseline["tables"].items() if ops.get("AddColumnOp")]

    def test_the_baseline_covers_every_table_it_claims_to(self):
        root = Path(__file__).resolve().parents[2]
        baseline = json.loads((root / "docs/governance/alembic_drift_baseline.json").read_text(encoding="utf-8"))

        assert len(baseline["tables"]) == baseline["tables_with_drift"]
        assert sum(sum(ops.values()) for ops in baseline["tables"].values()) == baseline["total_operations"]
