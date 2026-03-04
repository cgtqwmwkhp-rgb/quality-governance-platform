"""
Factory-boy ORM factories for all core domain models.

These factories support both in-memory (.build()) and DB-persisted (.create())
usage. For async DB sessions, use the helpers in tests/factories/async_helpers.py.
"""

import uuid
from datetime import datetime, timezone

import factory

from src.domain.models.audit import AuditTemplate
from src.domain.models.capa import CAPAAction
from src.domain.models.complaint import Complaint
from src.domain.models.incident import Incident
from src.domain.models.near_miss import NearMiss
from src.domain.models.policy import Policy
from src.domain.models.risk import Risk
from src.domain.models.tenant import Tenant
from src.domain.models.user import User


def _utcnow():
    return datetime.now(timezone.utc)


def _ref(prefix: str):
    """Generate a unique reference number like INC-00001."""
    return factory.Sequence(lambda n: f"{prefix}-{n + 1:05d}")


# ---------------------------------------------------------------------------
# Tenant
# ---------------------------------------------------------------------------


class TenantFactory(factory.Factory):
    class Meta:
        model = Tenant

    name = factory.Sequence(lambda n: f"Tenant {n}")
    slug = factory.Sequence(lambda n: f"tenant-{n}")
    is_active = True
    subscription_tier = "standard"


# ---------------------------------------------------------------------------
# User
# ---------------------------------------------------------------------------


class UserFactory(factory.Factory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@example.com")
    hashed_password = "hashed_placeholder"
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")
    is_active = True
    is_superuser = False
    created_at = factory.LazyFunction(_utcnow)
    updated_at = factory.LazyFunction(_utcnow)


# ---------------------------------------------------------------------------
# Incident
# ---------------------------------------------------------------------------


class IncidentFactory(factory.Factory):
    class Meta:
        model = Incident

    title = factory.Faker("sentence", nb_words=6)
    description = factory.Faker("paragraph")
    reference_number = _ref("INC")
    incident_date = factory.LazyFunction(_utcnow)
    reported_date = factory.LazyFunction(_utcnow)
    severity = "MEDIUM"
    status = "REPORTED"
    incident_type = "OTHER"
    first_aid_given = False
    emergency_services_called = False
    is_sif = False
    is_psif = False
    life_altering_potential = False
    created_at = factory.LazyFunction(_utcnow)
    updated_at = factory.LazyFunction(_utcnow)


# ---------------------------------------------------------------------------
# Complaint
# ---------------------------------------------------------------------------


class ComplaintFactory(factory.Factory):
    class Meta:
        model = Complaint

    title = factory.Faker("sentence", nb_words=5)
    description = factory.Faker("paragraph")
    reference_number = _ref("CMP")
    complainant_name = factory.Faker("name")
    received_date = factory.LazyFunction(_utcnow)
    complaint_type = "OTHER"
    priority = "MEDIUM"
    status = "RECEIVED"
    created_at = factory.LazyFunction(_utcnow)
    updated_at = factory.LazyFunction(_utcnow)


# ---------------------------------------------------------------------------
# Near Miss
# ---------------------------------------------------------------------------


class NearMissFactory(factory.Factory):
    class Meta:
        model = NearMiss

    reference_number = _ref("NM")
    reporter_name = factory.Faker("name")
    contract = "Default Contract"
    location = factory.Faker("address")
    event_date = factory.LazyFunction(_utcnow)
    description = factory.Faker("paragraph")
    status = "REPORTED"
    priority = "MEDIUM"
    created_at = factory.LazyFunction(_utcnow)
    updated_at = factory.LazyFunction(_utcnow)


# ---------------------------------------------------------------------------
# Audit Template
# ---------------------------------------------------------------------------


class AuditTemplateFactory(factory.Factory):
    class Meta:
        model = AuditTemplate

    name = factory.Faker("catch_phrase")
    reference_number = _ref("TMPL")
    external_id = factory.LazyFunction(lambda: str(uuid.uuid4()))
    audit_type = "inspection"
    is_active = True
    is_published = False
    version = 1
    scoring_method = "percentage"
    allow_offline = False
    require_gps = False
    require_signature = False
    require_approval = False
    auto_create_findings = True
    created_at = factory.LazyFunction(_utcnow)
    updated_at = factory.LazyFunction(_utcnow)


# ---------------------------------------------------------------------------
# CAPA Action
# ---------------------------------------------------------------------------


class CAPAActionFactory(factory.Factory):
    class Meta:
        model = CAPAAction

    reference_number = _ref("CAPA")
    title = factory.Faker("sentence", nb_words=5)
    description = factory.Faker("paragraph")
    capa_type = "CORRECTIVE"
    status = "OPEN"
    priority = "MEDIUM"
    created_at = factory.LazyFunction(_utcnow)


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------


class RiskFactory(factory.Factory):
    class Meta:
        model = Risk

    title = factory.Faker("sentence", nb_words=5)
    description = factory.Faker("paragraph")
    reference_number = _ref("RSK")
    category = "operational"
    likelihood = 3
    impact = 3
    risk_score = 9
    risk_level = "medium"
    treatment_strategy = "mitigate"
    status = "IDENTIFIED"
    is_active = True
    created_at = factory.LazyFunction(_utcnow)
    updated_at = factory.LazyFunction(_utcnow)


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class PolicyFactory(factory.Factory):
    class Meta:
        model = Policy

    title = factory.Faker("catch_phrase")
    reference_number = _ref("POL")
    document_type = "POLICY"
    status = "DRAFT"
    is_public = False
    review_frequency_months = 12
    created_at = factory.LazyFunction(_utcnow)
    updated_at = factory.LazyFunction(_utcnow)
