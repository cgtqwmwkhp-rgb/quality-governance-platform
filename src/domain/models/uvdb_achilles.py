"""
UVDB Achilles Verify B2 Audit Protocol Models

The UVDB (Utilities Vendor Database) Verify B2 Audit is a comprehensive
supply chain qualification audit used by UK utilities sector.

Protocol Reference: UVDB-QS-003 - Verify B2 Audit Protocol V11.2

Sections:
1. System Assurance and Compliance (21 points)
2. Quality Control and Assurance (21 points)
3. Health and Safety Leadership (18 points)
4. Health and Safety Management (21 points)
5. Health and Safety Arrangements (21 points)
6. Occupational Health (15 points)
7. Safety Critical Personnel (15 points)
8. Environmental Leadership (15 points)
9. Environmental Management (21 points)
10. Environmental Arrangements (15 points)
11. Waste Management (12 points)
12. Selection and Management of Sub-contractors (12 points)
13. Sourcing of Goods and Products (12 points)
14. Use of Work Equipment, Vehicles and Machines (6 points)
15. Key Performance Indicators (KPIs)

Cross-Mapping to ISO Standards:
- Section 1.1 → ISO 9001:2015 (Quality Management)
- Section 1.2 → ISO 45001:2018 (OH&S Management)
- Section 1.3 → ISO 14001:2015 (Environmental Management)
- Section 2.3 → ISO 27001:2022 (Information Security)
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database import Base


class UVDBSection(Base):
    """UVDB B2 Audit Protocol Sections"""

    __tablename__ = "uvdb_section"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section_number: Mapped[str] = mapped_column(String(10), nullable=False, unique=True)
    section_title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    max_score: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Cross-mapping to ISO standards
    iso_9001_mapping: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    iso_14001_mapping: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    iso_45001_mapping: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    iso_27001_mapping: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Metadata
    is_mse_only: Mapped[bool] = mapped_column(Boolean, default=False)  # MSE = Main Site Evaluation
    is_site_applicable: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    questions = relationship("UVDBQuestion", back_populates="section")


class UVDBQuestion(Base):
    """Individual UVDB Audit Questions"""

    __tablename__ = "uvdb_question"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    section_id: Mapped[int] = mapped_column(Integer, ForeignKey("uvdb_section.id"), nullable=False)
    question_number: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g., "1.1", "2.3.1"
    question_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Sub-questions for detailed compliance checking
    sub_questions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Scoring
    max_score: Mapped[int] = mapped_column(Integer, default=3)  # Typically 0-3 scale
    scoring_criteria: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Evidence requirements
    evidence_requirements: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    document_types: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Applicability
    mse_applicable: Mapped[bool] = mapped_column(Boolean, default=True)  # Main Site Evaluation
    site_applicable: Mapped[bool] = mapped_column(Boolean, default=True)  # Site Audit

    # Cross-reference to ISO clauses
    iso_clause_mapping: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Guidance
    auditor_guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    positive_indicators: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)
    negative_indicators: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    section = relationship("UVDBSection", back_populates="questions")


class UVDBAudit(Base):
    """UVDB B2 Audit Instance"""

    __tablename__ = "uvdb_audit"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_reference: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    # Company details
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # e.g., "00019685"
    supplier_registration: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Audit type
    audit_type: Mapped[str] = mapped_column(String(50), nullable=False)  # "B2", "B1", "C2"
    audit_scope: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Dates
    audit_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    next_audit_due: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    declaration_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expiry_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Auditor details
    lead_auditor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    auditor_organization: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Scoring
    total_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    max_possible_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    percentage_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    section_scores: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Status
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="scheduled")
    # scheduled, in_progress, completed, expired, suspended

    # Findings
    findings_count: Mapped[int] = mapped_column(Integer, default=0)
    major_findings: Mapped[int] = mapped_column(Integer, default=0)
    minor_findings: Mapped[int] = mapped_column(Integer, default=0)
    observations: Mapped[int] = mapped_column(Integer, default=0)

    # Certifications verified
    iso_9001_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    iso_14001_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    iso_45001_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    iso_27001_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    ukas_accredited: Mapped[bool] = mapped_column(Boolean, default=False)

    # CDM and licensing
    cdm_compliant: Mapped[bool] = mapped_column(Boolean, default=False)
    fors_accredited: Mapped[bool] = mapped_column(Boolean, default=False)
    fors_level: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # Bronze, Silver, Gold

    # Notes
    audit_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    improvement_actions: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    responses = relationship("UVDBAuditResponse", back_populates="audit")


class UVDBAuditResponse(Base):
    """Individual Question Responses in a UVDB Audit"""

    __tablename__ = "uvdb_audit_response"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_id: Mapped[int] = mapped_column(Integer, ForeignKey("uvdb_audit.id", ondelete="CASCADE"), nullable=False)
    question_id: Mapped[int] = mapped_column(Integer, ForeignKey("uvdb_question.id"), nullable=False)

    # Response
    mse_response: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-3 score
    site_response: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0-3 score

    # Sub-question responses (Yes/No/N/A for each)
    sub_question_responses: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # Evidence
    evidence_provided: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    documents_presented: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    # Findings
    finding_type: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    # positive, major_nc, minor_nc, observation, opportunity
    finding_description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Auditor notes
    auditor_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    positive_elements: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    audit = relationship("UVDBAudit", back_populates="responses")
    question = relationship("UVDBQuestion")


class UVDBKPIRecord(Base):
    """UVDB Key Performance Indicators (Section 15)"""

    __tablename__ = "uvdb_kpi_record"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    audit_id: Mapped[int] = mapped_column(Integer, ForeignKey("uvdb_audit.id", ondelete="CASCADE"), nullable=False)

    # Reporting period
    year: Mapped[int] = mapped_column(Integer, nullable=False)
    period_start: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    period_end: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Exposure (15.1)
    total_man_hours: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Safety KPIs (15.2-15.11)
    fatalities: Mapped[int] = mapped_column(Integer, default=0)
    riddor_reportable: Mapped[int] = mapped_column(Integer, default=0)  # HSE Reportable (15.3)
    lost_time_incidents_1_7_days: Mapped[int] = mapped_column(Integer, default=0)  # 15.4
    medical_treatment_incidents: Mapped[int] = mapped_column(Integer, default=0)  # MTI (15.5)
    first_aid_incidents: Mapped[int] = mapped_column(Integer, default=0)  # 15.6
    dangerous_occurrences: Mapped[int] = mapped_column(Integer, default=0)  # 15.7
    near_misses: Mapped[int] = mapped_column(Integer, default=0)  # 15.8
    hse_improvement_notices: Mapped[int] = mapped_column(Integer, default=0)  # 15.9
    hse_prohibition_notices: Mapped[int] = mapped_column(Integer, default=0)  # 15.10
    hse_prosecutions: Mapped[int] = mapped_column(Integer, default=0)  # 15.11

    # Environmental KPIs (15.12-15.14)
    env_minor_incidents: Mapped[int] = mapped_column(Integer, default=0)  # 15.12
    env_reportable_incidents: Mapped[int] = mapped_column(Integer, default=0)  # 15.13
    env_enforcement_actions: Mapped[int] = mapped_column(Integer, default=0)  # 15.14

    # Calculated rates
    ltifr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Lost Time Injury Frequency Rate
    trifr: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # Total Recordable Injury Frequency Rate

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class UVDBISOCrossMapping(Base):
    """Cross-mapping between UVDB questions and ISO standard clauses"""

    __tablename__ = "uvdb_iso_cross_mapping"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    uvdb_question_id: Mapped[int] = mapped_column(Integer, ForeignKey("uvdb_question.id"), nullable=False)

    # ISO Standard mappings
    iso_standard: Mapped[str] = mapped_column(String(20), nullable=False)  # "9001", "14001", "45001", "27001"
    iso_clause: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g., "5.1", "6.1.2"
    iso_clause_title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Mapping strength
    mapping_type: Mapped[str] = mapped_column(String(20), nullable=False, default="direct")
    # direct, partial, related

    mapping_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    uvdb_question = relationship("UVDBQuestion")
