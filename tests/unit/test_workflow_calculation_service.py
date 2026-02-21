"""Unit tests for WorkflowCalculationService - can run standalone."""

import os
import sys
from datetime import datetime, timedelta

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.domain.services.workflow_calculation_service import WorkflowCalculationService  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class MockStep:
    def __init__(self, status: str):
        self.status = status


class MockInstance:
    def __init__(self, sla_due_at=None, sla_warning_at=None):
        self.sla_due_at = sla_due_at
        self.sla_warning_at = sla_warning_at


# ---------------------------------------------------------------------------
# calculate_progress tests
# ---------------------------------------------------------------------------


def test_progress_all_completed():
    """100% when every step is completed."""
    steps = [MockStep("completed"), MockStep("completed"), MockStep("completed")]
    assert WorkflowCalculationService.calculate_progress(steps) == 100
    print("✓ All completed = 100%")


def test_progress_none_completed():
    """0% when no steps are completed."""
    steps = [MockStep("pending"), MockStep("in_progress")]
    assert WorkflowCalculationService.calculate_progress(steps) == 0
    print("✓ None completed = 0%")


def test_progress_empty_steps():
    """0% for an empty step list (avoid division by zero)."""
    assert WorkflowCalculationService.calculate_progress([]) == 0
    print("✓ Empty steps = 0%")


def test_progress_partial():
    """Partial completion rounds down via int()."""
    steps = [MockStep("completed"), MockStep("pending"), MockStep("pending")]
    assert WorkflowCalculationService.calculate_progress(steps) == 33
    print("✓ 1/3 completed = 33%")


def test_progress_half():
    """50% for half completed."""
    steps = [MockStep("completed"), MockStep("pending")]
    assert WorkflowCalculationService.calculate_progress(steps) == 50
    print("✓ 1/2 completed = 50%")


# ---------------------------------------------------------------------------
# calculate_sla_status tests
# ---------------------------------------------------------------------------


def test_sla_breached():
    """SLA is breached when now > sla_due_at."""
    past = datetime.utcnow() - timedelta(hours=1)
    instance = MockInstance(sla_due_at=past, sla_warning_at=past - timedelta(hours=2))
    assert WorkflowCalculationService.calculate_sla_status(instance) == "breached"
    print("✓ Past due = breached")


def test_sla_warning():
    """SLA is warning when past warning but before due."""
    now = datetime.utcnow()
    instance = MockInstance(
        sla_due_at=now + timedelta(hours=2),
        sla_warning_at=now - timedelta(hours=1),
    )
    assert WorkflowCalculationService.calculate_sla_status(instance) == "warning"
    print("✓ Past warning, before due = warning")


def test_sla_ok():
    """SLA is ok when before both thresholds."""
    now = datetime.utcnow()
    instance = MockInstance(
        sla_due_at=now + timedelta(days=5),
        sla_warning_at=now + timedelta(days=3),
    )
    assert WorkflowCalculationService.calculate_sla_status(instance) == "ok"
    print("✓ Before warning = ok")


def test_sla_no_due_date():
    """SLA is ok when no due date is set."""
    instance = MockInstance(sla_due_at=None, sla_warning_at=None)
    assert WorkflowCalculationService.calculate_sla_status(instance) == "ok"
    print("✓ No SLA dates = ok")


if __name__ == "__main__":
    print("=" * 60)
    print("WORKFLOW CALCULATION SERVICE TESTS")
    print("=" * 60)
    print()

    test_progress_all_completed()
    test_progress_none_completed()
    test_progress_empty_steps()
    test_progress_partial()
    test_progress_half()
    print()
    test_sla_breached()
    test_sla_warning()
    test_sla_ok()
    test_sla_no_due_date()

    print()
    print("=" * 60)
    print("ALL TESTS PASSED ✅")
    print("=" * 60)
