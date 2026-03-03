"""
Factory-boy factories for domain models.

Usage:
    from tests.factories import UserFactory, IncidentFactory
    user = UserFactory.build()           # in-memory only
    user = UserFactory.create()          # persisted via session
"""

from tests.factories.core import (
    TenantFactory,
    UserFactory,
    IncidentFactory,
    ComplaintFactory,
    NearMissFactory,
    AuditTemplateFactory,
    CAPAActionFactory,
    RiskFactory,
    PolicyFactory,
)

__all__ = [
    "TenantFactory",
    "UserFactory",
    "IncidentFactory",
    "ComplaintFactory",
    "NearMissFactory",
    "AuditTemplateFactory",
    "CAPAActionFactory",
    "RiskFactory",
    "PolicyFactory",
]
