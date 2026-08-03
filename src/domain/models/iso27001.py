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

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base
from src.domain.models.enums import InformationAssetType

#: The migrated ISO 27001 tables hold ``jsonb``, not ``json``, on every column
#: created by ``20260120_add_iso27001_isms``. The variant records that without
#: making the models unusable on the SQLite bootstrap
#: ``tests/integration/conftest.py`` falls back to — the same idiom
#: ``governed_knowledge.py`` and ``uvdb_achilles.py`` already use. Converting the
#: database the other way would be a full table rewrite that also gives up
#: containment operators and GIN indexing, so the model is the side that moves.
_JSONB = JSON().with_variant(JSONB(astext_type=Text()), "postgresql")


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
    __table_args__ = (
        CheckConstraint("confidentiality_requirement BETWEEN 1 AND 3", name="ck_info_assets_confidentiality_range"),
        CheckConstraint("integrity_requirement BETWEEN 1 AND 3", name="ck_info_assets_integrity_range"),
        CheckConstraint("availability_requirement BETWEEN 1 AND 3", name="ck_info_assets_availability_range"),
        Index("ix_information_asset_asset_type", "asset_type"),
        Index("ix_information_asset_classification", "classification"),
        Index("ix_information_asset_criticality", "criticality"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Identification
    asset_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Classification
    asset_type: Mapped[str] = mapped_column(String(50), nullable=False)
    classification: Mapped[str] = mapped_column(String(50), default="internal")
    handling_requirements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Ownership
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    custodian_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    custodian_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Location
    location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    physical_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    logical_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Value & Criticality
    criticality: Mapped[str] = mapped_column(String(50), default="medium")  # low, medium, high, critical
    # ``text`` in the migrated table since 20260120; the model's String(50) was the
    # narrower of the two, and narrowing the column to match would truncate.
    business_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
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
    dependencies: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)
    dependent_processes: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)

    # Controls
    applied_controls: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)

    # Review
    last_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )


class ISO27001Control(Base):
    """ISO 27001:2022 Annex A Controls"""

    __tablename__ = "iso27001_controls"
    __table_args__ = (
        # control_id is unique per tenant (same control can exist in multiple tenants)
        UniqueConstraint("control_id", "tenant_id", name="uq_iso27001_controls_control_id_tenant"),
        Index("ix_iso27001_control_domain", "domain"),
        Index("ix_iso27001_control_implementation_status", "implementation_status"),
        {"comment": "ISO 27001:2022 Annex A controls — composite unique enforced at DB level"},
    )

    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Control identification — uniqueness is per-tenant; see migration uq_iso27001_controls_control_id_tenant
    control_id: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g., A.5.1
    control_name: Mapped[str] = mapped_column(String(255), nullable=False)
    control_description: Mapped[str] = mapped_column(Text, nullable=False)
    control_purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Classification
    domain: Mapped[str] = mapped_column(String(50), nullable=False)  # organizational, people, physical, technological
    category: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    attribute_types: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)

    # Authoring guidance carried by the migrated table (20260120)
    implementation_guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    other_information: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Control attributes (ISO 27001:2022)
    control_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # preventive, detective, corrective
    information_security_properties: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # C, I, A
    cybersecurity_concepts: Mapped[Optional[list]] = mapped_column(
        JSON, nullable=True
    )  # Identify, Protect, Detect, Respond, Recover
    operational_capabilities: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    security_domains: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Implementation
    implementation_status: Mapped[str] = mapped_column(String(50), default="not_implemented")
    implementation_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    implementation_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    implementation_evidence: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)

    # Applicability
    is_applicable: Mapped[bool] = mapped_column(Boolean, default=True)
    exclusion_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Effectiveness
    effectiveness_rating: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_effectiveness_review: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Ownership
    control_owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    control_owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Evidence
    evidence_required: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    evidence_location: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Mapping to other standards
    mapped_standards: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)  # ISO 9001, NIST, etc.

    # Linkage the migrated table carries as its own columns, distinct from
    # ``mapped_standards``: these name rows in this database, not other standards.
    related_policies: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)
    related_procedures: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)
    related_assets: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)
    related_risks: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)
    cross_references: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )


class StatementOfApplicability(Base):
    """Statement of Applicability (SoA) - Required by ISO 27001"""

    __tablename__ = "statement_of_applicability"

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
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

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )


class SoAControlEntry(Base):
    """Individual control entries in the Statement of Applicability

    Two designs live side by side here, and that is deliberate. The physical
    table began as the singular ``soa_control_entry`` created by
    ``20260120_add_iso27001_isms`` with a separate inclusion and exclusion
    rationale; the model was written later with a single ``justification``.
    ``20260908_soa_align`` added the model's columns to the database rather than
    choosing between them, because which of the two rationales the single column
    means is an IMS decision about live certification evidence and copying either
    one into it would mis-file that evidence. The same applies to
    ``implementation_method`` beside ``implementation_description``. See
    ``docs/governance/attribution_schema_drift.md``.
    """

    __tablename__ = "soa_control_entries"

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    soa_id: Mapped[int] = mapped_column(ForeignKey("statement_of_applicability.id", ondelete="CASCADE"), nullable=False)
    control_id: Mapped[int] = mapped_column(ForeignKey("iso27001_controls.id", ondelete="CASCADE"), nullable=False)

    # Applicability
    is_applicable: Mapped[bool] = mapped_column(Boolean, default=True)
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    inclusion_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exclusion_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Implementation
    implementation_status: Mapped[str] = mapped_column(String(50), default="not_implemented")
    implementation_method: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    implementation_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    responsible_party: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    target_completion_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Risk treatment
    risk_treatment_reference: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )


class InformationSecurityRisk(Base):
    """Information security specific risks"""

    __tablename__ = "information_security_risks"
    __table_args__ = (
        CheckConstraint("confidentiality_impact BETWEEN 1 AND 3", name="ck_info_sec_risks_confidentiality_range"),
        CheckConstraint("integrity_impact BETWEEN 1 AND 3", name="ck_info_sec_risks_integrity_range"),
        CheckConstraint("availability_impact BETWEEN 1 AND 3", name="ck_info_sec_risks_availability_range"),
        CheckConstraint("likelihood BETWEEN 1 AND 5", name="ck_info_sec_risks_likelihood_range"),
        CheckConstraint("impact BETWEEN 1 AND 5", name="ck_info_sec_risks_impact_range"),
        Index("ix_info_sec_risk_status", "status"),
        Index("ix_info_sec_risk_treatment", "treatment_option"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Identification
    risk_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Threat/Vulnerability
    threat_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    threat_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    vulnerability: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Affected assets
    affected_assets: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)
    asset_classification: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # CIA Impact
    confidentiality_impact: Mapped[int] = mapped_column(Integer, default=2)  # 1-3
    integrity_impact: Mapped[int] = mapped_column(Integer, default=2)  # 1-3
    availability_impact: Mapped[int] = mapped_column(Integer, default=2)  # 1-3

    # Risk assessment
    likelihood: Mapped[int] = mapped_column(Integer, default=3)  # 1-5
    impact: Mapped[int] = mapped_column(Integer, default=3)  # 1-5
    inherent_risk_score: Mapped[int] = mapped_column(Integer, nullable=False)
    # Nullable in the migrated table: residual figures are only known after the
    # treatment is assessed, and 20260120 created all three that way.
    residual_likelihood: Mapped[Optional[int]] = mapped_column(Integer, default=2, nullable=True)
    residual_impact: Mapped[Optional[int]] = mapped_column(Integer, default=2, nullable=True)
    residual_risk_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Treatment
    treatment_option: Mapped[str] = mapped_column(String(50), default="mitigate")  # accept, avoid, mitigate, transfer
    treatment_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    treatment_status: Mapped[Optional[str]] = mapped_column(String(50), default="planned", nullable=True)

    # Controls
    applicable_controls: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)  # ISO 27001 control IDs

    # Ownership
    risk_owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    risk_owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Review
    last_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="open")

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )


class SecurityIncident(Base):
    """Information security incidents (A.5.24-5.28)"""

    __tablename__ = "security_incidents"
    __table_args__ = (
        Index("ix_security_incident_severity", "severity"),
        Index("ix_security_incident_status", "status"),
        Index("ix_security_incident_type", "incident_type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Identification
    incident_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Classification
    incident_type: Mapped[str] = mapped_column(String(100), nullable=False)
    # Types: malware, phishing, unauthorized_access, data_breach, dos, insider_threat, physical, other
    severity: Mapped[str] = mapped_column(String(50), default="medium")  # low, medium, high, critical
    priority: Mapped[Optional[str]] = mapped_column(String(50), default="medium", nullable=True)

    # Impact
    cia_impact: Mapped[Optional[list]] = mapped_column(
        _JSONB, nullable=True
    )  # ["confidentiality", "integrity", "availability"]
    affected_assets: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)
    affected_systems: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)
    affected_users: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    data_compromised: Mapped[bool] = mapped_column(Boolean, default=False)
    data_types_affected: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)

    # Dates
    detected_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    occurred_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reported_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None), nullable=True
    )
    contained_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolved_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Reporter
    reported_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reported_by_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Handler
    assigned_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
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
    preventive_actions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Regulatory
    regulatory_notification_required: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    regulatory_notification_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    regulatory_body: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # The 20260120 notification trio, which predates the ``regulatory_*`` columns
    # 20260407_iso27001_drift_02 added beside it. Which of the two a given
    # deployment populates is an IMS question; both are kept.
    notification_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    notification_authority: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notification_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Linkage carried by the migrated table
    related_risks: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)
    related_controls: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="open")
    # open, investigating, contained, eradicating, recovering, closed

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )


class AccessControlRecord(Base):
    """Access control records (A.5.15-5.18, A.8.2-8.5)"""

    __tablename__ = "access_control_records"
    __table_args__ = (
        Index("ix_access_control_resource", "resource_name"),
        Index("ix_access_control_user", "user_id"),
    )

    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # User
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    user_name: Mapped[str] = mapped_column(String(255), nullable=False)
    user_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    user_department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    user_role: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # System/Asset. ``system_name`` was added by 20260407_iso27001_drift_02 beside
    # the ``resource_type`` / ``resource_name`` pair 20260120 created, not instead
    # of it; the create route populates the former and the database defaults the
    # latter.
    system_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    resource_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="system")
    resource_name: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    asset_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("information_assets.id", ondelete="SET NULL"), nullable=True
    )

    # Access details
    access_level: Mapped[str] = mapped_column(String(50), nullable=False)  # read, write, admin, owner
    access_type: Mapped[str] = mapped_column(String(50), default="role_based")  # role_based, discretionary, mandatory
    access_method: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # password, mfa, certificate, biometric
    justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Approval (20260120; no foreign key on approved_by_id in the migrated table)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_by_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    approved_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Validity
    granted_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
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
    status: Mapped[Optional[str]] = mapped_column(String(50), default="active", nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )


class BusinessContinuityPlan(Base):
    """Business continuity for information security (A.5.29-5.30)"""

    __tablename__ = "business_continuity_plans"
    __table_args__ = (
        Index("ix_bcp_status", "status"),
        Index("ix_bcp_type", "plan_type"),
    )

    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Identification. ``name`` / ``description`` came from
    # 20260407_iso27001_drift_02; ``plan_name`` / ``plan_type`` / ``status`` are the
    # 20260120 originals, still NOT NULL and still defaulted by the database.
    plan_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    plan_name: Mapped[str] = mapped_column(String(255), nullable=False, server_default="")
    plan_type: Mapped[str] = mapped_column(String(50), nullable=False, server_default="continuity")
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="draft")
    name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Scope
    scope: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    covered_systems: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    covered_processes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    critical_processes: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)
    related_assets: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)
    dependencies: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)

    # RTO/RPO. The numeric hour columns are the ORM's; the free-text originals
    # beside them are the 20260120 design and are not derived from each other.
    rto_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Recovery Time Objective
    rpo_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Recovery Point Objective
    mtpd_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Maximum Tolerable Period of Disruption
    recovery_time_objective: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    recovery_point_objective: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    maximum_tolerable_downtime: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Procedures
    activation_criteria: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notification_procedures: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recovery_procedures: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resumption_procedures: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    communication_plan: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    alternate_site_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Team
    plan_owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    plan_owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    team_members: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    escalation_contacts: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    key_personnel: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)
    contact_information: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)

    # Testing
    last_test_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_test_type: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )  # tabletop, walkthrough, simulation, full
    last_test_result: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    test_results: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_test_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    test_frequency_months: Mapped[Optional[int]] = mapped_column(Integer, default=12, nullable=True)

    # Version
    version: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    effective_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    approved_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    approved_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )


class SupplierSecurityAssessment(Base):
    """Supplier information security assessments (A.5.19-5.23)"""

    __tablename__ = "supplier_security_assessments"
    __table_args__ = (
        Index("ix_supplier_assessment_rating", "overall_rating"),
        Index("ix_supplier_assessment_risk", "risk_level"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Multi-tenancy
    tenant_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("tenants.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # Supplier
    supplier_name: Mapped[str] = mapped_column(String(255), nullable=False)
    supplier_type: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # cloud, software, hardware, service, consultant
    contact_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    services_provided: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    data_access_level: Mapped[str] = mapped_column(String(50), default="none")  # none, limited, full
    data_types_accessed: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)
    integration_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Assessment
    assessment_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assessment_type: Mapped[str] = mapped_column(String(100), nullable=False)  # initial, periodic, ad-hoc
    assessor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Results
    overall_rating: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # compliant, partially_compliant, non_compliant
    security_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-100

    # Certifications
    iso27001_certified: Mapped[bool] = mapped_column(Boolean, default=False)
    iso27001_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    soc2_certified: Mapped[bool] = mapped_column(Boolean, default=False)
    soc2_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    other_certifications: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)

    # Findings. ``findings`` is the 20260120 column; ``findings_details`` was added
    # beside it by 20260407_iso27001_drift_02 and neither is derived from the other.
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    critical_findings: Mapped[int] = mapped_column(Integer, default=0)
    findings: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)
    findings_details: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Risk
    risk_level: Mapped[str] = mapped_column(String(50), default="medium")
    risk_accepted: Mapped[Optional[bool]] = mapped_column(Boolean, default=False, nullable=True)
    risk_accepted_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Contract
    contract_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    contract_expiry: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    sla_requirements: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)
    security_requirements: Mapped[Optional[list]] = mapped_column(_JSONB, nullable=True)

    # Next review
    next_assessment_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assessment_frequency_months: Mapped[int] = mapped_column(Integer, default=12)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="active")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
