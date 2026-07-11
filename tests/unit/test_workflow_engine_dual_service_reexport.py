"""Path-to-10: src.services.workflow_engine is a dual-service re-export."""

from src.domain.services import workflow_engine as domain_mod
from src.services import workflow_engine as services_mod


def test_workflow_engine_services_reexport_domain_classes():
    assert services_mod.WorkflowEngine is domain_mod.WorkflowEngine
    assert services_mod.SLAService is domain_mod.SLAService
    assert services_mod.ConditionEvaluator is domain_mod.ConditionEvaluator
    assert services_mod.ActionExecutor is domain_mod.ActionExecutor


def test_workflow_engine_service_constructs_with_session():
    class _DummySession:
        pass

    svc = services_mod.WorkflowEngine(_DummySession())
    assert svc is not None
    sla = services_mod.SLAService(_DummySession())
    assert sla is not None
