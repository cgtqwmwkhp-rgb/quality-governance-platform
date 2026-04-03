"""
Factory-boy ORM factories for all core domain models.

These factories support both in-memory (.build()) and DB-persisted (.create())
usage. For async DB sessions, use the helpers in tests/factories/async_helpers.py.

Determinism: all timestamps use a fixed epoch and all text fields use
factory.Sequence (not Faker) so test output is identical across runs.
"""

import uuid
from datetime import datetime, timezone

import factory

from src.domain.models.audit import AuditFinding as AuditFindingModel
from src.domain.models.audit import AuditRun as AuditRunModel
from src.domain.models.audit import AuditTemplate
from src.domain.models.capa import CAPAAction
from src.domain.models.complaint import Complaint
from src.domain.models.evidence_asset import EvidenceAsset
from src.domain.models.external_audit_import import ExternalAuditImportJob
from src.domain.models.incident import ActionStatus, Incident, IncidentAction
from src.domain.models.investigation import InvestigationRun
from src.domain.models.near_miss import NearMiss
from src.domain.models.policy import Policy
from src.domain.models.risk import Risk
from src.domain.models.risk_register import EnterpriseRisk
from src.domain.models.rta import RoadTrafficCollision, RTAAction
from src.domain.models.tenant import Tenant
from src.domain.models.user import User

FIXED_EPOCH = datetime(2026, 1, 15, 10, 0, 0, tzinfo=timezone.utc)


def _fixed_ts():
    """Fixed timestamp for reproducible test data."""
    return FIXED_EPOCH


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
    admin_email = factory.Sequence(lambda n: f"admin-{n}@example.com")
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
    first_name = factory.Sequence(lambda n: f"First{n}")
    last_name = factory.Sequence(lambda n: f"Last{n}")
    is_active = True
    is_superuser = False
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# Incident
# ---------------------------------------------------------------------------


class IncidentFactory(factory.Factory):
    class Meta:
        model = Incident

    title = factory.Sequence(lambda n: f"Test Incident {n}")
    description = factory.Sequence(lambda n: f"Incident description for case {n}.")
    reference_number = _ref("INC")
    incident_date = factory.LazyFunction(_fixed_ts)
    reported_date = factory.LazyFunction(_fixed_ts)
    severity = "MEDIUM"
    status = "REPORTED"
    incident_type = "OTHER"
    first_aid_given = False
    emergency_services_called = False
    is_sif = False
    is_psif = False
    life_altering_potential = False
    tenant_id = 1
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# Incident Action
# ---------------------------------------------------------------------------


class IncidentActionFactory(factory.Factory):
    class Meta:
        model = IncidentAction

    title = factory.Sequence(lambda n: f"Incident Action {n}")
    description = factory.Sequence(lambda n: f"Action description for item {n}.")
    status = ActionStatus.OPEN
    priority = "medium"
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# Complaint
# ---------------------------------------------------------------------------


class ComplaintFactory(factory.Factory):
    class Meta:
        model = Complaint

    title = factory.Sequence(lambda n: f"Test Complaint {n}")
    description = factory.Sequence(lambda n: f"Complaint description for case {n}.")
    reference_number = _ref("CMP")
    complainant_name = factory.Sequence(lambda n: f"Complainant {n}")
    received_date = factory.LazyFunction(_fixed_ts)
    complaint_type = "OTHER"
    priority = "MEDIUM"
    status = "RECEIVED"
    tenant_id = 1
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# Near Miss
# ---------------------------------------------------------------------------


class NearMissFactory(factory.Factory):
    class Meta:
        model = NearMiss

    reference_number = _ref("NM")
    reporter_name = factory.Sequence(lambda n: f"Reporter {n}")
    contract = "Default Contract"
    location = factory.Sequence(lambda n: f"Site {n}, Bay A")
    event_date = factory.LazyFunction(_fixed_ts)
    description = factory.Sequence(lambda n: f"Near miss description for event {n}.")
    status = "REPORTED"
    priority = "MEDIUM"
    tenant_id = 1
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# Audit Template
# ---------------------------------------------------------------------------


class AuditTemplateFactory(factory.Factory):
    class Meta:
        model = AuditTemplate

    name = factory.Sequence(lambda n: f"Audit Template {n}")
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
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# CAPA Action
# ---------------------------------------------------------------------------


class CAPAActionFactory(factory.Factory):
    class Meta:
        model = CAPAAction

    reference_number = _ref("CAPA")
    title = factory.Sequence(lambda n: f"CAPA Action {n}")
    description = factory.Sequence(lambda n: f"Corrective action description {n}.")
    capa_type = "CORRECTIVE"
    status = "OPEN"
    priority = "MEDIUM"
    created_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# Risk
# ---------------------------------------------------------------------------


class RiskFactory(factory.Factory):
    class Meta:
        model = Risk

    title = factory.Sequence(lambda n: f"Test Risk {n}")
    description = factory.Sequence(lambda n: f"Risk description for case {n}.")
    reference_number = _ref("RSK")
    category = "operational"
    likelihood = 3
    impact = 3
    risk_score = 9
    risk_level = "medium"
    treatment_strategy = "mitigate"
    status = "open"
    is_active = True
    tenant_id = 1
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# Policy
# ---------------------------------------------------------------------------


class PolicyFactory(factory.Factory):
    class Meta:
        model = Policy

    title = factory.Sequence(lambda n: f"Policy Document {n}")
    reference_number = _ref("POL")
    document_type = "POLICY"
    status = "DRAFT"
    is_public = False
    review_frequency_months = 12
    tenant_id = 1
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# Road Traffic Collision (RTA)
# ---------------------------------------------------------------------------


class RTAFactory(factory.Factory):
    class Meta:
        model = RoadTrafficCollision

    title = factory.Sequence(lambda n: f"Test RTA {n}")
    description = factory.Sequence(lambda n: f"Road traffic collision description {n}.")
    reference_number = _ref("RTA")
    severity = "damage_only"
    status = "reported"
    collision_date = factory.LazyFunction(_fixed_ts)
    reported_date = factory.LazyFunction(_fixed_ts)
    location = factory.Sequence(lambda n: f"A1 Junction {n}, Northbound")
    driver_name = factory.Sequence(lambda n: f"Driver {n}")
    driver_injured = False
    company_vehicle_registration = factory.Sequence(lambda n: f"PE{n:02d} TST")
    tenant_id = 1
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# RTA Action
# ---------------------------------------------------------------------------


class RTAActionFactory(factory.Factory):
    class Meta:
        model = RTAAction

    title = factory.Sequence(lambda n: f"RTA Action {n}")
    description = factory.Sequence(lambda n: f"RTA action description {n}.")
    status = ActionStatus.OPEN
    priority = "medium"
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# Golden test data sets (deterministic snapshots for regression tests)
# ---------------------------------------------------------------------------

GOLDEN_INCIDENT = {
    "title": "Forklift near-miss in Warehouse B",
    "description": "Forklift reversed without audible alarm near pedestrian walkway.",
    "incident_type": "near_miss",
    "severity": "high",
    "location": "Warehouse B, Bay 7",
}

GOLDEN_RISK = {
    "title": "Key-person dependency on legacy ETL",
    "description": "Single engineer maintains the XML import pipeline with no documentation.",
    "category": "operational",
    "likelihood": 4,
    "impact": 4,
}

GOLDEN_RTA = {
    "title": "Low-speed reversing collision at depot",
    "description": "Company van reversed into bollard while manoeuvring in depot car park.",
    "severity": "damage_only",
    "location": "Depot Car Park, Space 12",
    "company_vehicle_registration": "PE01 VAN",
    "driver_name": "J. Smith",
}

GOLDEN_COMPLAINT = {
    "title": "Late delivery to customer site",
    "description": "Delivery arrived 3 hours after agreed window, customer escalated.",
    "complaint_type": "delivery",
    "priority": "high",
    "complainant_name": "ABC Construction Ltd",
    "complainant_email": "complaints@abcconstruction.example.com",
}


# ---------------------------------------------------------------------------
# Audit Run
# ---------------------------------------------------------------------------


class AuditRunFactory(factory.Factory):
    class Meta:
        model = AuditRunModel

    title = factory.Sequence(lambda n: f"Audit Run {n}")
    reference_number = _ref("AUD")
    template_id = 1
    template_version = 1
    status = "in_progress"
    tenant_id = 1
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# Audit Finding
# ---------------------------------------------------------------------------


class AuditFindingFactory(factory.Factory):
    class Meta:
        model = AuditFindingModel

    title = factory.Sequence(lambda n: f"Audit Finding {n}")
    description = factory.Sequence(lambda n: f"Finding description for item {n}.")
    reference_number = _ref("FND")
    finding_type = "nonconformity"
    severity = "medium"
    status = "open"
    corrective_action_required = True
    run_id = 1
    tenant_id = 1
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# Investigation Run
# ---------------------------------------------------------------------------


class InvestigationFactory(factory.Factory):
    class Meta:
        model = InvestigationRun

    reference_number = _ref("INV")
    status = "draft"
    tenant_id = 1
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# Enterprise Risk
# ---------------------------------------------------------------------------


class EnterpriseRiskFactory(factory.Factory):
    class Meta:
        model = EnterpriseRisk

    reference = factory.Sequence(lambda n: f"RSK-{n + 1:05d}")
    title = factory.Sequence(lambda n: f"Enterprise Risk {n}")
    description = factory.Sequence(lambda n: f"Risk description for case {n}.")
    category = "compliance"
    subcategory = "audit_finding"
    source = "audit_finding"
    status = "open"
    treatment_strategy = "treat"
    inherent_likelihood = 3
    inherent_impact = 4
    inherent_score = 12
    residual_likelihood = 2
    residual_impact = 4
    residual_score = 8
    risk_appetite = "cautious"
    appetite_threshold = 12
    is_within_appetite = True
    review_frequency_days = 30
    is_escalated = False
    tenant_id = 1
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# Evidence Asset
# ---------------------------------------------------------------------------


class EvidenceAssetFactory(factory.Factory):
    class Meta:
        model = EvidenceAsset

    storage_key = factory.Sequence(lambda n: f"evidence/asset-{n}.pdf")
    original_filename = factory.Sequence(lambda n: f"document-{n}.pdf")
    content_type = "application/pdf"
    file_size_bytes = 102400
    tenant_id = 1
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)


# ---------------------------------------------------------------------------
# External Audit Import Job
# ---------------------------------------------------------------------------


class ExternalAuditImportJobFactory(factory.Factory):
    class Meta:
        model = ExternalAuditImportJob

    reference_number = _ref("IMPORT")
    status = "pending"
    source_filename = factory.Sequence(lambda n: f"audit-report-{n}.pdf")
    tenant_id = 1
    created_at = factory.LazyFunction(_fixed_ts)
    updated_at = factory.LazyFunction(_fixed_ts)
