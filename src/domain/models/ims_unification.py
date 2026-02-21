"""
Integrated Management System (IMS) Unification Models

Features:
- Single Point of Truth for ISO 9001, 14001, 45001
- Cross-Standard Mapping
- Unified Audit Planning
- Consolidated Management Review
"""

from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.infrastructure.database import Base


class ManagementStandard(str, Enum):
    """Supported management system standards - Core IMS Standards"""

    ISO_9001 = "ISO 9001:2015"  # Quality Management System
    ISO_14001 = "ISO 14001:2015"  # Environmental Management System
    ISO_45001 = "ISO 45001:2018"  # OH&S Management System
    ISO_27001 = "ISO 27001:2022"  # Information Security Management System (FULLY INTEGRATED)
    # Additional standards for future expansion
    ISO_22301 = "ISO 22301:2019"  # Business Continuity
    ISO_50001 = "ISO 50001:2018"  # Energy
    ISO_37001 = "ISO 37001:2016"  # Anti-Bribery


class IMSRequirement(Base):
    """Unified requirements from all standards"""

    __tablename__ = "ims_requirements"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Clause identification
    clause_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    clause_title: Mapped[str] = mapped_column(String(255), nullable=False)
    clause_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Standard
    standard: Mapped[str] = mapped_column(String(50), nullable=False, index=True)

    # Hierarchy
    parent_clause: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    level: Mapped[int] = mapped_column(Integer, default=1)  # 1=main, 2=sub, 3=detail

    # Common elements (Annex SL)
    annex_sl_element: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    is_common_requirement: Mapped[bool] = mapped_column(Boolean, default=False)

    # Keywords for mapping
    keywords: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Status
    is_applicable: Mapped[bool] = mapped_column(Boolean, default=True)
    exclusion_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class CrossStandardMapping(Base):
    """Maps equivalent clauses across standards"""

    __tablename__ = "cross_standard_mappings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Primary clause
    primary_requirement_id: Mapped[int] = mapped_column(
        ForeignKey("ims_requirements.id", ondelete="CASCADE"), nullable=False
    )
    primary_standard: Mapped[str] = mapped_column(String(50), nullable=False)
    primary_clause: Mapped[str] = mapped_column(String(20), nullable=False)

    # Mapped clause
    mapped_requirement_id: Mapped[int] = mapped_column(
        ForeignKey("ims_requirements.id", ondelete="CASCADE"), nullable=False
    )
    mapped_standard: Mapped[str] = mapped_column(String(50), nullable=False)
    mapped_clause: Mapped[str] = mapped_column(String(20), nullable=False)

    # Mapping details
    mapping_type: Mapped[str] = mapped_column(String(50), default="equivalent")  # equivalent, partial, related
    mapping_strength: Mapped[int] = mapped_column(Integer, default=100)  # 0-100 percentage
    mapping_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Annex SL common element
    annex_sl_element: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class IMSControl(Base):
    """Unified controls that satisfy multiple standards"""

    __tablename__ = "ims_controls"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Control identification
    reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Process area
    process_area: Mapped[str] = mapped_column(String(100), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Standards satisfied
    standards_addressed: Mapped[list] = mapped_column(JSON, nullable=False)  # List of standards
    clauses_addressed: Mapped[list] = mapped_column(JSON, nullable=False)  # List of clause numbers

    # Implementation
    implementation_status: Mapped[str] = mapped_column(String(50), default="implemented")
    implementation_evidence: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Effectiveness
    effectiveness_rating: Mapped[str] = mapped_column(String(50), default="effective")
    last_effectiveness_review: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Ownership
    owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Documentation
    procedure_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    document_links: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IMSControlRequirementMapping(Base):
    """Links controls to specific requirements"""

    __tablename__ = "ims_control_requirement_mappings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    control_id: Mapped[int] = mapped_column(ForeignKey("ims_controls.id", ondelete="CASCADE"), nullable=False)
    requirement_id: Mapped[int] = mapped_column(ForeignKey("ims_requirements.id", ondelete="CASCADE"), nullable=False)

    # Coverage
    coverage_level: Mapped[str] = mapped_column(String(50), default="full")  # full, partial
    coverage_percentage: Mapped[int] = mapped_column(Integer, default=100)
    coverage_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class UnifiedAuditPlan(Base):
    """Integrated audit plans covering multiple standards"""

    __tablename__ = "unified_audit_plans"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Plan identification
    reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Scope
    standards_in_scope: Mapped[list] = mapped_column(JSON, nullable=False)
    clauses_in_scope: Mapped[list] = mapped_column(JSON, nullable=False)
    processes_in_scope: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    departments_in_scope: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Audit type
    audit_type: Mapped[str] = mapped_column(String(50), nullable=False)  # internal, surveillance, certification
    audit_cycle: Mapped[str] = mapped_column(String(50), default="annual")

    # Schedule
    planned_start_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    planned_end_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    actual_start_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    actual_end_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Team
    lead_auditor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    lead_auditor_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    audit_team: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="planned")
    completion_percentage: Mapped[int] = mapped_column(Integer, default=0)

    # Results
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    major_nc_count: Mapped[int] = mapped_column(Integer, default=0)
    minor_nc_count: Mapped[int] = mapped_column(Integer, default=0)
    observations_count: Mapped[int] = mapped_column(Integer, default=0)
    opportunities_count: Mapped[int] = mapped_column(Integer, default=0)

    # Report
    report_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    conclusion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    recommendation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ManagementReviewInput(Base):
    """Inputs for consolidated management review"""

    __tablename__ = "management_review_inputs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Review identification
    review_id: Mapped[int] = mapped_column(ForeignKey("management_reviews.id", ondelete="CASCADE"), nullable=False)

    # Input category (aligned with ISO Annex SL)
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    subcategory: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Source standard(s)
    source_standards: Mapped[list] = mapped_column(JSON, nullable=False)

    # Input content
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Metrics/Data
    current_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    previous_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    trend: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # improving, stable, declining
    target_value: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Analysis
    analysis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    risk_implications: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Supporting data
    data_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    data_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    data_source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    attachments: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Owner
    prepared_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    order_index: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class ManagementReview(Base):
    """Consolidated management review records"""

    __tablename__ = "management_reviews"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Review identification
    reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)

    # Scope
    standards_reviewed: Mapped[list] = mapped_column(JSON, nullable=False)
    review_period_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    review_period_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Meeting details
    meeting_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    meeting_location: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    attendees: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    chair_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(50), default="planned")

    # Outputs/Decisions
    outputs: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    decisions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    action_items: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Overall assessment
    ims_effectiveness: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    policy_adequacy: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    objectives_achievement: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    resource_adequacy: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Improvement
    continual_improvement_opportunities: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    changes_needed: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Minutes/Report
    minutes_link: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Next review
    next_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IMSProcessMap(Base):
    """Process mapping across standards"""

    __tablename__ = "ims_process_maps"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Process identification
    process_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    process_name: Mapped[str] = mapped_column(String(255), nullable=False)
    process_type: Mapped[str] = mapped_column(String(50), nullable=False)  # core, support, management

    # Description
    description: Mapped[str] = mapped_column(Text, nullable=False)
    purpose: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scope: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # SIPOC
    suppliers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    inputs: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    outputs: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    customers: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Standards relevance
    relevant_standards: Mapped[list] = mapped_column(JSON, nullable=False)
    relevant_clauses: Mapped[list] = mapped_column(JSON, nullable=False)

    # Ownership
    process_owner_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    process_owner_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Performance
    kpis: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    targets: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Documentation
    procedure_references: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    work_instructions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    forms_records: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Risks & Opportunities
    associated_risks: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    opportunities: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Interactions
    upstream_processes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    downstream_processes: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class IMSObjective(Base):
    """Unified objectives across standards"""

    __tablename__ = "ims_objectives"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # Objective identification
    reference: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)

    # Classification
    objective_type: Mapped[str] = mapped_column(String(50), nullable=False)  # quality, environmental, ohs, combined
    standards_addressed: Mapped[list] = mapped_column(JSON, nullable=False)
    policy_alignment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # SMART criteria
    specific: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    measurable_indicator: Mapped[str] = mapped_column(String(255), nullable=False)
    baseline_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    target_value: Mapped[float] = mapped_column(Float, nullable=False)
    current_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    unit_of_measure: Mapped[str] = mapped_column(String(50), nullable=False)
    target_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    # Progress
    progress_percentage: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="on_track")  # on_track, at_risk, behind, achieved

    # Responsibility
    responsible_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    responsible_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Resources
    resources_required: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    budget: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # Actions/Programmes
    action_plan: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    # Review
    last_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_review_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    review_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
