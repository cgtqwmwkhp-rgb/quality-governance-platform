"""CAPA (Corrective and Preventive Action) domain model."""

from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from src.infrastructure.database import Base


class CAPAStatus(str, PyEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    VERIFICATION = "verification"
    CLOSED = "closed"
    OVERDUE = "overdue"


class CAPAType(str, PyEnum):
    CORRECTIVE = "corrective"
    PREVENTIVE = "preventive"


class CAPAPriority(str, PyEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class CAPASource(str, PyEnum):
    INCIDENT = "incident"
    AUDIT_FINDING = "audit_finding"
    COMPLAINT = "complaint"
    NCR = "ncr"
    RISK = "risk"
    MANAGEMENT_REVIEW = "management_review"


class CAPAAction(Base):
    __tablename__ = "capa_actions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    reference_number = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    capa_type = Column(Enum(CAPAType), nullable=False)
    status = Column(Enum(CAPAStatus), default=CAPAStatus.OPEN, nullable=False, index=True)
    priority = Column(Enum(CAPAPriority), default=CAPAPriority.MEDIUM, nullable=False)
    source_type = Column(Enum(CAPASource), nullable=True)
    source_id = Column(Integer, nullable=True)

    root_cause = Column(Text, nullable=True)
    proposed_action = Column(Text, nullable=True)
    verification_method = Column(Text, nullable=True)
    verification_result = Column(Text, nullable=True)
    effectiveness_criteria = Column(Text, nullable=True)

    assigned_to_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    verified_by_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_by_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    tenant_id = Column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    due_date = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    verified_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    iso_standard = Column(String(50), nullable=True)
    clause_reference = Column(String(50), nullable=True)
