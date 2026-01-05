"""Investigation domain models.

Investigations replace standalone Root Cause Analysis (RCA) with a template-based
system that can be assigned to Road Traffic Collisions, Reporting Incidents, or Complaints.
"""

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from src.domain.models.base import AuditTrailMixin, ReferenceNumberMixin, TimestampMixin
from src.infrastructure.database import Base


class InvestigationStatus(str, enum.Enum):
    """Investigation status enumeration."""

    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    UNDER_REVIEW = "under_review"
    COMPLETED = "completed"
    CLOSED = "closed"


class AssignedEntityType(str, enum.Enum):
    """Entity types that can have investigations assigned."""

    ROAD_TRAFFIC_COLLISION = "road_traffic_collision"
    REPORTING_INCIDENT = "reporting_incident"
    COMPLAINT = "complaint"


class InvestigationTemplate(Base, TimestampMixin, AuditTrailMixin):
    """Investigation template model.

    Templates define the structure and sections of an investigation,
    including RCA (Root Cause Analysis) as a structured section.
    """

    __tablename__ = "investigation_templates"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text, nullable=True)
    version = Column(String(50), nullable=False, default="1.0")
    is_active = Column(Boolean, nullable=False, default=True)

    # Template structure stored as JSON
    # Example structure:
    # {
    #   "sections": [
    #     {
    #       "id": "rca",
    #       "title": "Root Cause Analysis",
    #       "fields": [
    #         {"id": "problem_statement", "type": "text", "required": true},
    #         {"id": "root_cause", "type": "text", "required": true},
    #         {"id": "contributing_factors", "type": "array", "required": false},
    #         {"id": "corrective_actions", "type": "array", "required": true}
    #       ]
    #     },
    #     {
    #       "id": "evidence",
    #       "title": "Evidence Collection",
    #       "fields": [...]
    #     }
    #   ]
    # }
    structure = Column(JSON, nullable=False)

    # Metadata
    applicable_entity_types = Column(JSON, nullable=False)  # List of AssignedEntityType values

    # Relationships
    investigation_runs = relationship("InvestigationRun", back_populates="template", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<InvestigationTemplate(id={self.id}, name='{self.name}', version='{self.version}')>"


class InvestigationRun(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """Investigation run model.

    Represents an actual investigation instance based on a template,
    assigned to a specific entity (RTA, Incident, or Complaint).
    """

    __tablename__ = "investigation_runs"

    id = Column(Integer, primary_key=True, index=True)

    # Template reference
    template_id = Column(Integer, ForeignKey("investigation_templates.id"), nullable=False, index=True)

    # Assignment to entity
    assigned_entity_type = Column(Enum(AssignedEntityType), nullable=False, index=True)
    assigned_entity_id = Column(Integer, nullable=False, index=True)

    # Investigation details
    status = Column(Enum(InvestigationStatus), nullable=False, default=InvestigationStatus.DRAFT)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Investigation data (responses to template fields)
    # Stored as JSON matching the template structure
    # Example:
    # {
    #   "sections": {
    #     "rca": {
    #       "problem_statement": "Equipment failure due to...",
    #       "root_cause": "Inadequate maintenance schedule",
    #       "contributing_factors": ["Human error", "Environmental conditions"],
    #       "corrective_actions": [
    #         {"action": "Implement preventive maintenance", "owner": "Maintenance Team", "due_date": "2026-02-01"}
    #       ]
    #     },
    #     "evidence": {...}
    #   }
    # }
    data = Column(JSON, nullable=False, default=dict)

    # Completion tracking
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    # Assigned users
    assigned_to_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewer_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)

    # Relationships
    template = relationship("InvestigationTemplate", back_populates="investigation_runs")
    assigned_to = relationship("User", foreign_keys=[assigned_to_user_id])
    reviewer = relationship("User", foreign_keys=[reviewer_user_id])

    def __repr__(self) -> str:
        return (
            f"<InvestigationRun(id={self.id}, ref='{self.reference_number}', "
            f"status='{self.status}', entity='{self.assigned_entity_type}:{self.assigned_entity_id}')>"
        )
