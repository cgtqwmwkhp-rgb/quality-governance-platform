"""
Factory-boy factories for domain models.

Usage:
    from tests.factories import UserFactory, IncidentFactory
    user = UserFactory.build()           # in-memory only
    user = UserFactory.create()          # persisted via session

All factories are deterministic (fixed timestamps, sequence-based text).
"""

from tests.factories.core import (
    GOLDEN_COMPLAINT,
    GOLDEN_INCIDENT,
    GOLDEN_RISK,
    GOLDEN_RTA,
    AuditTemplateFactory,
    CAPAActionFactory,
    ComplaintFactory,
    IncidentActionFactory,
    IncidentFactory,
    NearMissFactory,
    PolicyFactory,
    RiskFactory,
    RTAActionFactory,
    RTAFactory,
    TenantFactory,
    UserFactory,
)

__all__ = [
    "TenantFactory",
    "UserFactory",
    "IncidentFactory",
    "IncidentActionFactory",
    "ComplaintFactory",
    "NearMissFactory",
    "AuditTemplateFactory",
    "CAPAActionFactory",
    "RiskFactory",
    "PolicyFactory",
    "RTAFactory",
    "RTAActionFactory",
    "GOLDEN_INCIDENT",
    "GOLDEN_RISK",
    "GOLDEN_RTA",
    "GOLDEN_COMPLAINT",
]
