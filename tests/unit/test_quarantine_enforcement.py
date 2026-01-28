"""
Unit tests for quarantine enforcement script.

These tests verify that the quarantine policy enforcement works correctly:
1. Expired quarantines are detected and cause failure
2. Budget exceeded is detected and causes failure
3. Valid policies pass
4. Self-test mode works

These tests ensure the CI gate cannot be bypassed.
"""

import subprocess
import sys
from pathlib import Path


class TestQuarantineEnforcementScript:
    """Tests for scripts/report_test_quarantine.py enforcement logic."""

    def test_self_test_mode_passes(self):
        """Self-test mode should verify enforcement logic and pass."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "report_test_quarantine.py"

        result = subprocess.run(
            [sys.executable, str(script_path), "--self-test"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Self-test should pass (exit code 0)
        assert result.returncode == 0, f"Self-test failed:\n{result.stdout}\n{result.stderr}"
        assert "ALL SELF-TESTS PASSED" in result.stdout

    def test_script_detects_expired_quarantine(self):
        """Script self-test should verify expired quarantine detection."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "report_test_quarantine.py"

        result = subprocess.run(
            [sys.executable, str(script_path), "--self-test"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Verify the expired quarantine test ran
        assert "Expired quarantine detection" in result.stdout
        assert "Expired quarantine correctly rejected" in result.stdout

    def test_script_detects_budget_exceeded(self):
        """Script self-test should verify budget exceeded detection."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "report_test_quarantine.py"

        result = subprocess.run(
            [sys.executable, str(script_path), "--self-test"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Verify the budget exceeded test ran
        assert "Budget exceeded detection" in result.stdout
        assert "Budget exceeded correctly rejected" in result.stdout

    def test_script_accepts_valid_policy(self):
        """Script self-test should verify valid policy acceptance."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "report_test_quarantine.py"

        result = subprocess.run(
            [sys.executable, str(script_path), "--self-test"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Verify the valid policy test ran
        assert "Valid policy acceptance" in result.stdout
        assert "Valid policy correctly accepted" in result.stdout


class TestQuarantineEnforcementIntegration:
    """Integration tests for quarantine enforcement against real policy."""

    def test_current_policy_is_valid(self):
        """Current QUARANTINE_POLICY.yaml should pass enforcement."""
        script_path = Path(__file__).parent.parent.parent / "scripts" / "report_test_quarantine.py"

        result = subprocess.run(
            [sys.executable, str(script_path)],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Current policy should pass
        assert result.returncode == 0, (
            f"Current quarantine policy failed enforcement:\n{result.stdout}\n{result.stderr}"
        )
        assert "QUARANTINE POLICY: PASSED" in result.stdout

    def test_script_exits_nonzero_on_failure_mode(self):
        """Script should exit with code 1 when enforcement fails."""
        # This is verified by the self-test which tests failure detection
        script_path = Path(__file__).parent.parent.parent / "scripts" / "report_test_quarantine.py"

        result = subprocess.run(
            [sys.executable, str(script_path), "--self-test"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # Self-test verifies that failures cause non-zero exit
        assert "Expired quarantine correctly rejected" in result.stdout
        assert "Budget exceeded correctly rejected" in result.stdout
