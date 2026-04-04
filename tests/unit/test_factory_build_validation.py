"""Smoke test: every factory in tests/factories/core.py can .build() without errors."""

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


@pytest.mark.parametrize(
    "factory_cls",
    [
        TenantFactory,
        UserFactory,
        IncidentFactory,
        IncidentActionFactory,
        ComplaintFactory,
        NearMissFactory,
        AuditTemplateFactory,
        CAPAActionFactory,
        RiskFactory,
        PolicyFactory,
        RTAFactory,
        RTAActionFactory,
        AuditRunFactory,
        AuditFindingFactory,
        InvestigationFactory,
        EnterpriseRiskFactory,
        EvidenceAssetFactory,
        ExternalAuditImportJobFactory,
    ],
    ids=lambda cls: cls.__name__,
)
def test_factory_builds_valid_instance(factory_cls):
    instance = factory_cls.build()
    assert instance is not None
