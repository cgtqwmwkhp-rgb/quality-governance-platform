"""Re-export from canonical domain service.

The single source of truth for workflow engine services lives in
``src.domain.services.workflow_engine``.  This module re-exports them so
that callers using the ``src.services`` path continue to work.

The PX-286 pending-approval reconciliation this note used to point at is gone:
``WorkflowTemplateEngine.get_workflow_stats`` and ``get_pending_approvals`` were
deleted in FR-APPROVALS-01 because the class holds no state, so the queue they
reconciled was empty for every user. Outstanding decisions are read from the
domains that hold them by ``src.domain.services.approvals_read_model``. This
module remains a thin re-export only.
"""

from src.domain.services.workflow_engine import ActionExecutor, ConditionEvaluator, SLAService, WorkflowEngine

__all__ = [
    "ActionExecutor",
    "ConditionEvaluator",
    "SLAService",
    "WorkflowEngine",
]
