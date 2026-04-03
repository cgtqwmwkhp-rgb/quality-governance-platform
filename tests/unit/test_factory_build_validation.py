"""Verify all test factories produce valid instances without exceptions."""

import pytest

from tests.factories.core import (
    AuditFindingFactory,
    AuditRunFactory,
    AuditTemplateFactory,
    CAPAActionFactory,
    ComplaintFactory,
    EnterpriseRiskFactory,
    EvidenceAssetFactory,
    ExternalAuditImportJobFactory,
    IncidentActionFactory,
    IncidentFactory,
    InvestigationFactory,
    NearMissFactory,
    PolicyFactory,
    RiskFactory,
    RTAActionFactory,
    RTAFactory,
    TenantFactory,
    UserFactory,
)

FACTORIES = [
    UserFactory,
    TenantFactory,
    IncidentFactory,
    RiskFactory,
    RTAFactory,
    ComplaintFactory,
    AuditRunFactory,
    AuditTemplateFactory,
    AuditFindingFactory,
    CAPAActionFactory,
    IncidentActionFactory,
    NearMissFactory,
    PolicyFactory,
    RTAActionFactory,
    InvestigationFactory,
    EnterpriseRiskFactory,
    EvidenceAssetFactory,
    ExternalAuditImportJobFactory,
]


@pytest.mark.parametrize("factory_cls", FACTORIES, ids=lambda f: f.__name__)
def test_factory_builds_without_error(factory_cls):
    """Each factory should produce an instance via .build() without raising."""
    instance = factory_cls.build()
    assert instance is not None
    assert hasattr(instance, "id") or hasattr(instance, "__tablename__")
