"""Unit tests for WorkflowCalculationService (D15 coverage uplift)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from src.domain.services.workflow_calculation_service import WorkflowCalculationService


class TestCalculateProgress:
    """Tests for WorkflowCalculationService.calculate_progress."""

    def _step(self, status: str) -> SimpleNamespace:
        return SimpleNamespace(status=status)

    def test_empty_steps_returns_zero(self) -> None:
        assert WorkflowCalculationService.calculate_progress([]) == 0

    def test_all_completed_returns_100(self) -> None:
        steps = [self._step("completed")] * 4
        assert WorkflowCalculationService.calculate_progress(steps) == 100

    def test_no_completed_returns_zero(self) -> None:
        steps = [self._step("pending")] * 3
        assert WorkflowCalculationService.calculate_progress(steps) == 0

    def test_half_completed_returns_50(self) -> None:
        steps = [self._step("completed"), self._step("pending")]
        assert WorkflowCalculationService.calculate_progress(steps) == 50

    def test_one_of_four_completed_returns_25(self) -> None:
        steps = [self._step("completed")] + [self._step("in_progress")] * 3
        assert WorkflowCalculationService.calculate_progress(steps) == 25

    def test_three_of_four_completed_returns_75(self) -> None:
        steps = [self._step("completed")] * 3 + [self._step("pending")]
        assert WorkflowCalculationService.calculate_progress(steps) == 75

    def test_returns_integer(self) -> None:
        steps = [self._step("completed")] * 2 + [self._step("pending")]
        result = WorkflowCalculationService.calculate_progress(steps)
        assert isinstance(result, int)


class TestCalculateSlaStatus:
    """Tests for WorkflowCalculationService.calculate_sla_status."""

    def _instance(self, sla_due_at=None, sla_warning_at=None) -> SimpleNamespace:
        return SimpleNamespace(sla_due_at=sla_due_at, sla_warning_at=sla_warning_at)

    def test_no_sla_returns_ok(self) -> None:
        instance = self._instance()
        assert WorkflowCalculationService.calculate_sla_status(instance) == "ok"

    def test_future_due_date_no_warning_returns_ok(self) -> None:
        future = datetime.now(timezone.utc) + timedelta(hours=24)
        instance = self._instance(sla_due_at=future)
        assert WorkflowCalculationService.calculate_sla_status(instance) == "ok"

    def test_past_due_date_returns_breached(self) -> None:
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        instance = self._instance(sla_due_at=past)
        assert WorkflowCalculationService.calculate_sla_status(instance) == "breached"

    def test_past_warning_but_not_due_returns_warning(self) -> None:
        now = datetime.now(timezone.utc)
        instance = self._instance(
            sla_due_at=now + timedelta(hours=2),
            sla_warning_at=now - timedelta(hours=1),
        )
        assert WorkflowCalculationService.calculate_sla_status(instance) == "warning"

    def test_explicit_now_parameter(self) -> None:
        fixed_now = datetime(2026, 4, 7, 12, 0, tzinfo=timezone.utc)
        instance = self._instance(
            sla_due_at=datetime(2026, 4, 7, 11, 0, tzinfo=timezone.utc),
        )
        assert WorkflowCalculationService.calculate_sla_status(instance, now=fixed_now) == "breached"

    def test_future_warning_not_triggered_yet(self) -> None:
        now = datetime.now(timezone.utc)
        instance = self._instance(
            sla_due_at=now + timedelta(hours=4),
            sla_warning_at=now + timedelta(hours=2),
        )
        assert WorkflowCalculationService.calculate_sla_status(instance) == "ok"
