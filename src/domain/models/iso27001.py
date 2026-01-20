"""
ISO 27001:2022 Information Security Management System Models

Features:
- Information Security Policy
- Asset Management (Annex A.5)
- Access Control (Annex A.5.15-5.18)
- Cryptography (Annex A.8.24)
- Physical Security (Annex A.7)
- Operations Security (Annex A.8)
- Communications Security (Annex A.8)
- Supplier Relationships (Annex A.5.19-5.23)
- Incident Management (Annex A.5.24-5.28)
- Business Continuity (Annex A.5.29-5.30)
- Compliance (Annex A.5.31-5.37)
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database import Base


class AssetType(str, Enum):
    """Information asset types"""

    HARDWARE = "hardware"
    SOFTWARE = "software"
    DATA = "data"
    SERVICE = "service"
    PEOPLE = "people"
    INTANGIBLE = "intangible"
    PHYSICAL = "physical"


class AssetClassification(str, Enum):
    """Information classification levels"""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    SECRET = "secret"


class ControlDomain(str, Enum):
    """ISO 27001:2022 Annex A Control Domains (4 themes)"""

    ORGANIZATIONAL = "organizational"  # A.5 - 37 controls
    PEOPLE = "people"  # A.6 - 8 controls
    PHYSICAL = "physical"  # A.7 - 14 controls
    TECHNOLOGICAL = "technological"  # A.8 - 34 controls


class InformationAsset(Base):
    """Information asset register"""

    __tablename__ = "information_assets"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Identification
    asset_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Classification
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    classification: Mapped[str] = mapped_column(String(50), default="internal")
    handling_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Ownership
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    custodian_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    custodian_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Location
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    physical_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    logical_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Value & Criticality
    criticality: Mapped[str] = mapped_column(String(50), default="medium")  # low, medium, high, critical
    business_value: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    replacement_cost: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # CIA Triad Assessment
    confidentiality_requirement: Mapped[int] = mapped_column(Integer, default=2)  # 1-3
    integrity_requirement: Mapped[int] = mapped_column(Integer, default=2)  # 1-3
    availability_requirement: Mapped[int] = mapped_column(Integer, default=2)  # 1-3

    # Lifecycle
    acquisition_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    disposal_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    disposal_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="active")

    # Dependencies
    dependencies: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    dependent_processes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Controls
    applied_controls: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Review
    last_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ISO27001Control(Base):
    """ISO 27001:2022 Annex A Controls"""

    __tablename__ = "iso27001_controls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Control identification
    control_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)  # e.g., A.5.1
    control_name: Mapped[str] = mapped_column(String(255), nullable=False)
    control_description: Mapped[str] = mapped_column(Text, nullable=False)

    # Classification
    domain: Mapped[str] = mapped_column(String(50), nullable=False)  # organizational, people, physical, technological
    category: Mapped[str] = mapped_column(String(100), nullable=False)

    # Control attributes (ISO 27001:2022)
    control_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # preventive, detective, corrective
    information_security_properties: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # C, I, A
    cybersecurity_concepts: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # Identify, Protect, Detect, Respond, Recover
    operational_capabilities: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    security_domains: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Implementation
    implementation_status: Mapped[str] = mapped_column(String(50), default="not_implemented")
    implementation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    implementation_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Applicability
    is_applicable: Mapped[bool] = mapped_column(Boolean, default=True)
    exclusion_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Effectiveness
    effectiveness_rating: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_effectiveness_review: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Ownership
    control_owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    control_owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Evidence
    evidence_required: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    evidence_location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Mapping to other standards
    mapped_standards: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # ISO 9001, NIST, etc.

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class StatementOfApplicability(Base):
    """Statement of Applicability (SoA) - Required by ISO 27001"""

    __tablename__ = "statement_of_applicability"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # SoA Version
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    effective_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Scope
    scope_description: Mapped[str] = mapped_column(Text, nullable=False)

    # Summary
    total_controls: Mapped[int] = mapped_column(Integer, default=93)
    applicable_controls: Mapped[int] = mapped_column(Integer, default=0)
    excluded_controls: Mapped[int] = mapped_column(Integer, default=0)
    implemented_controls: Mapped[int] = mapped_column(Integer, default=0)
    partially_implemented: Mapped[int] = mapped_column(Integer, default=0)
    not_implemented: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="draft")
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)

    # Document
    document_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SoAControlEntry(Base):
    """Individual control entries in the Statement of Applicability"""

    __tablename__ = "soa_control_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    soa_id: Mapped[int] = mapped_column(
        ForeignKey("statement_of_applicability.id", ondelete="CASCADE"), nullable=False
    )
    control_id: Mapped[int] = mapped_column(
        ForeignKey("iso27001_controls.id"), nullable=False
    )

    # Applicability
    is_applicable: Mapped[bool] = mapped_column(Boolean, default=True)
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Implementation
    implementation_status: Mapped[str] = mapped_column(String(50), default="not_implemented")
    implementation_method: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Risk treatment
    risk_treatment_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class InformationSecurityRisk(Base):
    """Information security specific risks"""

    __tablename__ = "information_security_risks"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Identification
    risk_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Threat/Vulnerability
    threat_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    threat_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vulnerability: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Affected assets
    affected_assets: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    asset_classification: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # CIA Impact
    confidentiality_impact: Mapped[int] = mapped_column(Integer, default=2)  # 1-3
    integrity_impact: Mapped[int] = mapped_column(Integer, default=2)  # 1-3
    availability_impact: Mapped[int] = mapped_column(Integer, default=2)  # 1-3

    # Risk assessment
    likelihood: Mapped[int] = mapped_column(Integer, default=3)  # 1-5
    impact: Mapped[int] = mapped_column(Integer, default=3)  # 1-5
    inherent_risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    residual_likelihood: Mapped[int] = mapped_column(Integer, default=2)
    residual_impact: Mapped[int] = mapped_column(Integer, default=2)
    residual_risk_score: Mapped[int] = mapped_column(Integer, nullable=False)

    # Treatment
    treatment_option: Mapped[str] = mapped_column(String(50), default="mitigate")  # accept, avoid, mitigate, transfer
    treatment_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    treatment_status: Mapped[str] = mapped_column(String(50), default="planned")

    # Controls
    applicable_controls: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # List of ISO 27001 control IDs

    # Ownership
    risk_owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    risk_owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Review
    last_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SecurityIncident(Base):
    """Information security incidents (A.5.24-5.28)"""

    __tablename__ = "security_incidents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Identification
    incident_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Classification
    incident_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # Types: malware, phishing, unauthorized_access, data_breach, dos, insider_threat, physical, other
    severity: Mapped[str] = mapped_column(String(50), default="medium")  # low, medium, high, critical
    priority: Mapped[str] = mapped_column(String(50), default="medium")

    # Impact
    cia_impact: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # ["confidentiality", "integrity", "availability"]
    affected_assets: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    affected_users: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    data_compromised: Mapped[bool] = mapped_column(Boolean, default=False)
    data_types_affected: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Dates
    detected_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    occurred_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reported_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    contained_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Reporter
    reported_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reported_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Handler
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_to_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Investigation
    root_cause: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    attack_vector: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    indicators_of_compromise: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Response
    containment_actions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    eradication_actions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recovery_actions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    lessons_learned: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Regulatory
    regulatory_notification_required: Mapped[bool] = mapped_column(Boolean, default=False)
    regulatory_notification_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    regulatory_body: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="open")
    # open, investigating, contained, eradicating, recovering, closed

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class AccessControlRecord(Base):
    """Access control records (A.5.15-5.18, A.8.2-8.5)"""

    __tablename__ = "access_control_records"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # User
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    user_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # System/Asset
    system_name: Mapped[str] = mapped_column(String(255), nullable=False)
    asset_id: Mapped[Optional[int]] = mapped_column(ForeignKey("information_assets.id"), nullable=True)

    # Access details
    access_level: Mapped[str] = mapped_column(String(50), nullable=False)  # read, write, admin, owner
    access_type: Mapped[str] = mapped_column(String(50), default="role_based")  # role_based, discretionary, mandatory
    access_method: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # password, mfa, certificate, biometric

    # Validity
    granted_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    granted_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    revocation_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Review
    last_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reviewed_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(50), default="active")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class BusinessContinuityPlan(Base):
    """Business continuity for information security (A.5.29-5.30)"""

    __tablename__ = "business_continuity_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Identification
    plan_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Scope
    scope: Mapped[str] = mapped_column(Text, nullable=False)
    covered_systems: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    covered_processes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # RTO/RPO
    rto_hours: Mapped[int] = mapped_column(Integer, nullable=False)  # Recovery Time Objective
    rpo_hours: Mapped[int] = mapped_column(Integer, nullable=False)  # Recovery Point Objective
    mtpd_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Maximum Tolerable Period of Disruption

    # Procedures
    activation_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notification_procedures: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recovery_procedures: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resumption_procedures: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Team
    plan_owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    plan_owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    team_members: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    escalation_contacts: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Testing
    last_test_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_test_type: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # tabletop, walkthrough, simulation, full
    last_test_result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    next_test_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    test_frequency_months: Mapped[int] = mapped_column(Integer, default=12)

    # Version
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    effective_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SupplierSecurityAssessment(Base):
    """Supplier information security assessments (A.5.19-5.23)"""

    __tablename__ = "supplier_security_assessments"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Supplier
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_type: Mapped[str] = mapped_column(String(100), nullable=False)  # cloud, software, hardware, service, consultant
    services_provided: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_access_level: Mapped[str] = mapped_column(String(50), default="none")  # none, limited, full

    # Assessment
    assessment_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    assessment_type: Mapped[str] = mapped_column(String(100), nullable=False)  # initial, periodic, ad-hoc
    assessor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Results
    overall_rating: Mapped[str] = mapped_column(String(50), nullable=False)  # compliant, partially_compliant, non_compliant
    security_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-100

    # Certifications
    iso27001_certified: Mapped[bool] = mapped_column(Boolean, default=False)
    soc2_certified: Mapped[bool] = mapped_column(Boolean, default=False)
    other_certifications: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Findings
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    critical_findings: Mapped[int] = mapped_column(Integer, default=0)
    findings_details: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Risk
    risk_level: Mapped[str] = mapped_column(String(50), default="medium")
    risk_accepted: Mapped[bool] = mapped_column(Boolean, default=False)
    risk_accepted_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Next review
    next_assessment_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assessment_frequency_months: Mapped[int] = mapped_column(Integer, default=12)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="active")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
