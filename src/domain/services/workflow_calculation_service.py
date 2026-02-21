"""Workflow progress and SLA calculation service."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional


class WorkflowCalculationService:
    """Pure calculation helpers for workflow instances."""

    @staticmethod
    def calculate_progress(steps: list[Any]) -> int:
        """Compute completion percentage from a list of workflow steps.

        Each step is expected to have a ``.status`` attribute; steps with
        ``status == "completed"`` count towards the numerator.
        """
        total = len(steps)
        if not total:
            return 0
        completed = sum(1 for s in steps if s.status == "completed")
        return int((completed / total) * 100)

    @staticmethod
    def calculate_sla_status(
        instance: Any,
        now: Optional[datetime] = None,
    ) -> str:
        """Determine the SLA status for a workflow instance.

        Returns ``"breached"``, ``"warning"``, or ``"ok"``.

        *instance* must expose ``.sla_due_at`` and ``.sla_warning_at``
        attributes.
        """
        if now is None:
            now = datetime.utcnow()

        if instance.sla_due_at:
            if now > instance.sla_due_at:
                return "breached"
            if instance.sla_warning_at and now > instance.sla_warning_at:
                return "warning"
        return "ok"
