#!/usr/bin/env python3
"""
Unit tests for the baseline gate validator.

These tests prove:
1. Single source of truth - baseline is ONLY read from the artifact file
2. Gate fails when expected (regression detection)
3. Gate passes when expected
4. Override handling works correctly
5. No hardcoded baseline values can bypass the gate
"""

import json
import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

# Add scripts to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

from validate_baseline_gate import (  # noqa: E402
    BaselineConfig,
    Override,
    compute_min_acceptable,
    load_baseline,
    parse_override,
    validate_gate,
)


class TestSingleSourceOfTruth(TestCase):
    """Tests proving single source of truth for baseline values."""

    def test_baseline_loaded_only_from_file(self):
        """Baseline values MUST come from the artifact file, nowhere else."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "baseline_pass_count": 127,
                    "baseline_skip_count": 20,
                    "baseline_total_count": 147,
                    "baseline_commit_sha": "test-sha",
                    "baseline_date": "2026-01-28",
                    "baseline_notes": "Test baseline",
                    "version": "1.0.0",
                    "min_acceptable_percentage": 90,
                    "override": None,
                },
                f,
            )
            f.flush()

            baseline = load_baseline(Path(f.name))

            # Verify all values match the file
            self.assertEqual(baseline.baseline_pass_count, 127)
            self.assertEqual(baseline.baseline_skip_count, 20)
            self.assertEqual(baseline.baseline_total_count, 147)
            self.assertEqual(baseline.baseline_commit_sha, "test-sha")
            self.assertEqual(baseline.baseline_date, "2026-01-28")

            os.unlink(f.name)

    def test_missing_baseline_file_exits_with_error(self):
        """Missing baseline file MUST cause exit code 2."""
        with self.assertRaises(SystemExit) as cm:
            load_baseline(Path("/nonexistent/baseline.json"))
        self.assertEqual(cm.exception.code, 2)

    def test_invalid_json_exits_with_error(self):
        """Invalid JSON in baseline file MUST cause exit code 2."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            f.flush()

            with self.assertRaises(SystemExit) as cm:
                load_baseline(Path(f.name))
            self.assertEqual(cm.exception.code, 2)

            os.unlink(f.name)

    def test_missing_required_fields_exits_with_error(self):
        """Missing required fields MUST cause exit code 2."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "baseline_pass_count": 127,
                    # Missing other required fields
                },
                f,
            )
            f.flush()

            with self.assertRaises(SystemExit) as cm:
                load_baseline(Path(f.name))
            self.assertEqual(cm.exception.code, 2)

            os.unlink(f.name)


class TestGateEnforcement(TestCase):
    """Tests proving gate enforcement is truthful and blocking."""

    def setUp(self):
        """Create a temporary baseline file for each test."""
        self.temp_file = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False)
        self.baseline_data = {
            "baseline_pass_count": 100,
            "baseline_skip_count": 10,
            "baseline_total_count": 110,
            "baseline_commit_sha": "test-sha",
            "baseline_date": "2026-01-28",
            "baseline_notes": "Test baseline",
            "version": "1.0.0",
            "min_acceptable_percentage": 90,
            "override": None,
        }
        json.dump(self.baseline_data, self.temp_file)
        self.temp_file.flush()
        self.baseline_path = Path(self.temp_file.name)

    def tearDown(self):
        """Clean up temp file."""
        os.unlink(self.temp_file.name)

    def test_gate_fails_on_regression(self):
        """Gate MUST fail when current passed < min acceptable."""
        # Min acceptable = 100 * 90% = 90
        # Current passed = 80 < 90 -> MUST FAIL
        result = validate_gate(current_passed=80, current_skipped=10, baseline_path=self.baseline_path)
        self.assertFalse(result)

    def test_gate_passes_at_threshold(self):
        """Gate MUST pass when current passed == min acceptable."""
        # Min acceptable = 100 * 90% = 90
        # Current passed = 90 == 90 -> MUST PASS
        result = validate_gate(current_passed=90, current_skipped=10, baseline_path=self.baseline_path)
        self.assertTrue(result)

    def test_gate_passes_above_threshold(self):
        """Gate MUST pass when current passed > min acceptable."""
        # Min acceptable = 100 * 90% = 90
        # Current passed = 100 > 90 -> MUST PASS
        result = validate_gate(current_passed=100, current_skipped=10, baseline_path=self.baseline_path)
        self.assertTrue(result)

    def test_gate_passes_above_baseline(self):
        """Gate MUST pass when current passed > baseline."""
        # Min acceptable = 100 * 90% = 90
        # Current passed = 120 > 100 (baseline) -> MUST PASS
        result = validate_gate(current_passed=120, current_skipped=5, baseline_path=self.baseline_path)
        self.assertTrue(result)


class TestOverrideHandling(TestCase):
    """Tests proving override handling is structured and time-boxed."""

    def test_valid_override_changes_threshold(self):
        """Valid override MUST change the min acceptable threshold."""
        future_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        override_data = {
            "issue_id": "GH-123",
            "owner": "test-owner",
            "expiry": future_date,
            "reason": "Test reason",
            "temporary_min_pass": 50,
        }

        override = parse_override(override_data)

        self.assertIsNotNone(override)
        self.assertEqual(override.issue_id, "GH-123")
        self.assertEqual(override.owner, "test-owner")
        self.assertEqual(override.temporary_min_pass, 50)

    def test_expired_override_is_ignored(self):
        """Expired override MUST be ignored."""
        past_date = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        override_data = {
            "issue_id": "GH-123",
            "owner": "test-owner",
            "expiry": past_date,
            "reason": "Test reason",
            "temporary_min_pass": 50,
        }

        override = parse_override(override_data)

        self.assertIsNone(override)

    def test_override_missing_fields_is_ignored(self):
        """Override missing required fields MUST be ignored."""
        override_data = {
            "issue_id": "GH-123",
            # Missing: owner, expiry, reason, temporary_min_pass
        }

        override = parse_override(override_data)

        self.assertIsNone(override)

    def test_override_with_invalid_date_is_ignored(self):
        """Override with invalid date format MUST be ignored."""
        override_data = {
            "issue_id": "GH-123",
            "owner": "test-owner",
            "expiry": "not-a-date",
            "reason": "Test reason",
            "temporary_min_pass": 50,
        }

        override = parse_override(override_data)

        self.assertIsNone(override)

    def test_override_lowers_threshold_for_gate(self):
        """Active override MUST lower the threshold for gate calculation."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            future_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            json.dump(
                {
                    "baseline_pass_count": 100,
                    "baseline_skip_count": 10,
                    "baseline_total_count": 110,
                    "baseline_commit_sha": "test-sha",
                    "baseline_date": "2026-01-28",
                    "baseline_notes": "Test baseline",
                    "version": "1.0.0",
                    "min_acceptable_percentage": 90,
                    "override": {
                        "issue_id": "GH-123",
                        "owner": "test-owner",
                        "expiry": future_date,
                        "reason": "Known regression being fixed",
                        "temporary_min_pass": 50,
                    },
                },
                f,
            )
            f.flush()

            # Without override: 80 < 90 -> FAIL
            # With override: 80 >= 50 -> PASS
            result = validate_gate(current_passed=80, current_skipped=10, baseline_path=Path(f.name))
            self.assertTrue(result)

            os.unlink(f.name)


class TestMinAcceptableComputation(TestCase):
    """Tests proving MIN_ACCEPTABLE is computed correctly."""

    def test_min_acceptable_is_90_percent_of_baseline(self):
        """MIN_ACCEPTABLE = baseline * 0.90 when no override."""
        baseline = BaselineConfig(
            baseline_pass_count=127,
            baseline_skip_count=20,
            baseline_total_count=147,
            baseline_commit_sha="test",
            baseline_date="2026-01-28",
            baseline_notes="test",
            version="1.0.0",
            min_acceptable_percentage=90,
            override=None,
        )

        result = compute_min_acceptable(baseline, None)

        # 127 * 0.90 = 114.3 -> int = 114
        self.assertEqual(result, 114)

    def test_min_acceptable_uses_override_when_active(self):
        """MIN_ACCEPTABLE = override.temporary_min_pass when override active."""
        baseline = BaselineConfig(
            baseline_pass_count=127,
            baseline_skip_count=20,
            baseline_total_count=147,
            baseline_commit_sha="test",
            baseline_date="2026-01-28",
            baseline_notes="test",
            version="1.0.0",
            min_acceptable_percentage=90,
            override=None,  # Override data is parsed separately
        )

        override = Override(
            issue_id="GH-123", owner="test-owner", expiry="2026-12-31", reason="Test", temporary_min_pass=80
        )

        result = compute_min_acceptable(baseline, override)

        self.assertEqual(result, 80)


class TestNoHardcodedBypass(TestCase):
    """Tests proving no hardcoded values can bypass the gate."""

    def test_different_baseline_values_produce_different_thresholds(self):
        """Changing baseline file MUST change the computed threshold."""
        thresholds = []

        for baseline_value in [50, 100, 150, 200]:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(
                    {
                        "baseline_pass_count": baseline_value,
                        "baseline_skip_count": 10,
                        "baseline_total_count": baseline_value + 10,
                        "baseline_commit_sha": "test-sha",
                        "baseline_date": "2026-01-28",
                        "baseline_notes": f"Baseline {baseline_value}",
                        "version": "1.0.0",
                        "min_acceptable_percentage": 90,
                        "override": None,
                    },
                    f,
                )
                f.flush()

                baseline = load_baseline(Path(f.name))
                threshold = compute_min_acceptable(baseline, None)
                thresholds.append(threshold)

                os.unlink(f.name)

        # All thresholds should be different (proportional to baseline)
        self.assertEqual(len(set(thresholds)), 4)
        # Verify they are 90% of each baseline
        self.assertEqual(thresholds, [45, 90, 135, 180])


if __name__ == "__main__":
    main()
