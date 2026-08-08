"""Entity360 producer package — default registrations load via registry."""

from __future__ import annotations

from src.domain.services.entity_360.producers.case_link import CaseLinkProducer
from src.domain.services.entity_360.producers.compliance_evidence import ComplianceEvidenceProducer
from src.domain.services.entity_360.producers.document_graph import DocumentGraphProducer
from src.domain.services.entity_360.producers.job_lifecycle import JobLifecycleProducer
from src.domain.services.entity_360.producers.lifecycle_impact import LifecycleImpactProducer

__all__ = [
    "CaseLinkProducer",
    "ComplianceEvidenceProducer",
    "DocumentGraphProducer",
    "JobLifecycleProducer",
    "LifecycleImpactProducer",
]
