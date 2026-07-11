"""Dual-service re-export contract for investigation_service."""

from src.domain.services.investigation_service import (
    InvestigationService as DomainInvestigationService,
    MappingReasonCode as DomainMappingReasonCode,
)
from src.services.investigation_service import InvestigationService, MappingReasonCode


def test_investigation_service_reexport_is_domain_canonical():
    assert InvestigationService is DomainInvestigationService
    assert MappingReasonCode is DomainMappingReasonCode
