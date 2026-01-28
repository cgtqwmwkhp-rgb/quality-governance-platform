"""
Unit Tests for Baseline Governance

These tests verify that:
1. E2E baseline is read from the single source of truth (docs/evidence/e2e_baseline.json)
2. No hardcoded baselines exist in CI workflow
3. Gate logic works correctly
"""

import json
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).parent.parent.parent
BASELINE_FILE = REPO_ROOT / "docs" / "evidence" / "e2e_baseline.json"
CI_WORKFLOW_FILE = REPO_ROOT / ".github" / "workflows" / "ci.yml"


class TestBaselineGovernance:
    """Tests for E2E baseline single-source-of-truth."""

    def test_baseline_file_exists(self):
        """Verify the baseline artifact file exists."""
        assert BASELINE_FILE.exists(), (
            f"Baseline file missing: {BASELINE_FILE}\n" "Create this file with baseline_pass_count to enable governance"
        )

    def test_baseline_file_has_required_fields(self):
        """Verify baseline file has all required fields."""
        required_fields = [
            "baseline_pass_count",
            "baseline_commit_sha",
            "baseline_date",
            "baseline_notes",
        ]

        with open(BASELINE_FILE) as f:
            data = json.load(f)

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

    def test_baseline_pass_count_is_positive_integer(self):
        """Verify baseline_pass_count is a positive integer."""
        with open(BASELINE_FILE) as f:
            data = json.load(f)

        baseline = data["baseline_pass_count"]
        assert isinstance(baseline, int), f"baseline_pass_count must be int, got {type(baseline)}"
        assert baseline > 0, f"baseline_pass_count must be positive, got {baseline}"

    def test_ci_workflow_reads_from_baseline_file(self):
        """Verify CI workflow reads baseline from artifact file, not hardcoded."""
        with open(CI_WORKFLOW_FILE) as f:
            ci_content = f.read()

        # Check that CI reads from the baseline file
        assert "e2e_baseline.json" in ci_content, "CI workflow must read from docs/evidence/e2e_baseline.json"

        # Check for hardcoded E2E_BASELINE=<number> pattern (should NOT exist)
        hardcoded_pattern = re.compile(r"E2E_BASELINE=\d+\s*#")
        matches = hardcoded_pattern.findall(ci_content)
        assert len(matches) == 0, (
            f"CI workflow has hardcoded baseline: {matches}\n" "Remove hardcoded values and read from e2e_baseline.json"
        )

    def test_report_script_uses_baseline_file(self):
        """Verify report script reads from baseline file."""
        script_path = REPO_ROOT / "scripts" / "report_test_quarantine.py"

        with open(script_path) as f:
            script_content = f.read()

        assert "e2e_baseline.json" in script_content, "Report script must read from e2e_baseline.json"

    def test_baseline_consistency_across_sources(self):
        """Verify baseline value is consistent between file and script."""
        # Read from file
        with open(BASELINE_FILE) as f:
            file_baseline = json.load(f)["baseline_pass_count"]

        # Read from script
        from scripts.report_test_quarantine import E2E_BASELINE_COUNT

        assert file_baseline == E2E_BASELINE_COUNT, (
            f"Baseline mismatch: file={file_baseline}, script={E2E_BASELINE_COUNT}\n"
            "Script should read from file, not hardcode"
        )


class TestPathDriftPrevention:
    """Tests for API path drift prevention."""

    def test_path_drift_script_exists(self):
        """Verify path drift check script exists."""
        script_path = REPO_ROOT / "scripts" / "check_api_path_drift.py"
        assert script_path.exists(), f"Path drift script missing: {script_path}"

    def test_path_drift_script_self_test_passes(self):
        """Verify path drift script self-tests pass."""
        result = subprocess.run(
            ["python", str(REPO_ROOT / "scripts" / "check_api_path_drift.py"), "--self-test"],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Path drift self-test failed:\n{result.stdout}\n{result.stderr}"
        assert "ALL SELF-TESTS PASSED" in result.stdout

    def test_no_path_drift_in_tests(self):
        """Verify no /api vs /api/v1 drift exists in test files."""
        result = subprocess.run(
            ["python", str(REPO_ROOT / "scripts" / "check_api_path_drift.py")],
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Path drift detected:\n{result.stdout}\n{result.stderr}"


class TestGateLogic:
    """Tests for gate enforcement logic."""

    def test_minimum_gate_threshold(self):
        """Verify minimum gate threshold is 20."""
        from scripts.report_test_quarantine import E2E_MINIMUM_PASS

        assert E2E_MINIMUM_PASS == 20, f"Minimum gate should be 20, got {E2E_MINIMUM_PASS}"

    def test_baseline_regression_threshold(self):
        """Verify baseline regression threshold is 90% of baseline."""
        from scripts.report_test_quarantine import E2E_BASELINE_COUNT

        min_acceptable = int(E2E_BASELINE_COUNT * 0.9)

        with open(BASELINE_FILE) as f:
            baseline = json.load(f)["baseline_pass_count"]

        expected_min = int(baseline * 0.9)
        assert min_acceptable == expected_min, (
            f"Min acceptable should be 90% of baseline ({baseline}), " f"expected {expected_min}, got {min_acceptable}"
        )
