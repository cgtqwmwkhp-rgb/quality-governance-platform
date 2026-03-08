"""Canonical enum definitions for the domain model layer.

All domain enums live here to prevent duplicate definitions across model files.
Model files re-export the enums they need for backward compatibility.

Design decisions:
- DocumentType is a superset of all document-type values across domains.
- DocumentStatus covers both ingestion-pipeline and governance-lifecycle states.
- RiskStatus covers operational risk (Risk model).
- EnterpriseRiskStatus covers enterprise risk (EnterpriseRisk model).
- InformationAssetType replaces the generic AssetType from iso27001.
"""

import enum
from enum import Enum


class DocumentType(str, enum.Enum):
    """Canonical document type — superset of document, policy, and controlled-document types."""

    POLICY = "policy"
    PROCEDURE = "procedure"
    WORK_INSTRUCTION = "work_instruction"
    SOP = "sop"
    FORM = "form"
    TEMPLATE = "template"
    GUIDELINE = "guideline"
    MANUAL = "manual"
    RECORD = "record"
    FAQ = "faq"
    STANDARD = "standard"
    SPECIFICATION = "specification"
    DRAWING = "drawing"
    REGISTER = "register"
    PLAN = "plan"
    REPORT = "report"
    EXTERNAL = "external"
    OTHER = "other"


class DocumentStatus(str, enum.Enum):
    """Canonical document status — covers ingestion pipeline and governance lifecycle."""

    # Ingestion pipeline states
    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"

    # Governance lifecycle states
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    UNDER_REVIEW = "under_review"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    PUBLISHED = "published"
    ACTIVE = "active"
    UNDER_REVISION = "under_revision"
    SUPERSEDED = "superseded"
    RETIRED = "retired"
    OBSOLETE = "obsolete"
    ARCHIVED = "archived"
    REJECTED = "rejected"


class RiskStatus(str, enum.Enum):
    """Status for operational risks (Risk model in risk.py)."""

    OPEN = "open"
    MITIGATING = "mitigating"
    ACCEPTED = "accepted"
    CLOSED = "closed"

    # Backward-compatible aliases for legacy callers.
    IDENTIFIED = "open"
    ASSESSING = "mitigating"
    TREATING = "mitigating"
    MONITORING = "accepted"


class EnterpriseRiskStatus(str, Enum):
    """Status for enterprise risks (EnterpriseRisk model in risk_register.py)."""

    IDENTIFIED = "identified"
    ASSESSING = "assessing"
    TREATING = "treating"
    MONITORING = "monitoring"
    CLOSED = "closed"
    ESCALATED = "escalated"


class InformationAssetType(str, Enum):
    """ISO 27001 information asset classification (replaces generic AssetType)."""

    HARDWARE = "hardware"
    SOFTWARE = "software"
    DATA = "data"
    SERVICE = "service"
    PEOPLE = "people"
    INTANGIBLE = "intangible"
    PHYSICAL = "physical"
