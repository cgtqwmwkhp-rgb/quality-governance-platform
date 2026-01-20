"""Domain models package."""

from src.domain.models.analytics import (
    BenchmarkData,
    CostRecord,
    Dashboard,
    DashboardWidget,
    ROIInvestment,
    SavedReport,
)
from src.domain.models.audit import AuditFinding, AuditQuestion, AuditRun, AuditTemplate
from src.domain.models.base import AuditTrailMixin, ReferenceNumberMixin, SoftDeleteMixin, TimestampMixin
from src.domain.models.complaint import Complaint, ComplaintAction
from src.domain.models.document import (
    Document,
    DocumentAnnotation,
    DocumentChunk,
    DocumentSearchLog,
    DocumentVersion,
    IndexJob,
)
from src.domain.models.incident import Incident, IncidentAction
from src.domain.models.policy import Policy, PolicyVersion
from src.domain.models.risk import Risk, RiskAssessment, RiskControl
from src.domain.models.rta import RoadTrafficCollision, RTAAction
from src.domain.models.standard import Clause, Control, Standard
from src.domain.models.user import Role, User, UserRole
# Enterprise Risk Register (Tier 1)
from src.domain.models.risk_register import (
    Risk as EnterpriseRisk,
    RiskControl as EnterpriseRiskControl,
    RiskControlMapping,
    BowTieElement,
    KeyRiskIndicator,
    RiskAssessmentHistory,
    RiskAppetiteStatement,
)
# IMS Unification (Tier 1)
from src.domain.models.ims_unification import (
    IMSRequirement,
    CrossStandardMapping,
    IMSControl,
    IMSControlRequirementMapping,
    UnifiedAuditPlan,
    ManagementReview,
    ManagementReviewInput,
    IMSProcessMap,
    IMSObjective,
)
# Document Control (Tier 1)
from src.domain.models.document_control import (
    ControlledDocument,
    DocumentVersion as ControlledDocumentVersion,
    DocumentApprovalWorkflow,
    DocumentApprovalInstance,
    DocumentApprovalAction,
    DocumentDistribution,
    DocumentTrainingLink,
    DocumentAccessLog,
    ObsoleteDocumentRecord,
)
# ISO 27001 Information Security (Tier 1)
from src.domain.models.iso27001 import (
    InformationAsset,
    ISO27001Control,
    StatementOfApplicability,
    SoAControlEntry,
    InformationSecurityRisk,
    SecurityIncident,
    AccessControlRecord,
    BusinessContinuityPlan,
    SupplierSecurityAssessment,
)
# UVDB Achilles Verify B2 Audit Protocol
from src.domain.models.uvdb_achilles import (
    UVDBSection,
    UVDBQuestion,
    UVDBAudit,
    UVDBAuditResponse,
    UVDBKPIRecord,
    UVDBISOCrossMapping,
)

__all__ = [
    # Base mixins
    "TimestampMixin",
    "ReferenceNumberMixin",
    "SoftDeleteMixin",
    "AuditTrailMixin",
    # User models
    "User",
    "Role",
    "UserRole",
    # Standard models
    "Standard",
    "Clause",
    "Control",
    # Audit models
    "AuditTemplate",
    "AuditQuestion",
    "AuditRun",
    "AuditFinding",
    # Risk models
    "Risk",
    "RiskControl",
    "RiskAssessment",
    # Incident models
    "Incident",
    "IncidentAction",
    # RTA models
    "RoadTrafficCollision",
    "RTAAction",
    # Complaint models
    "Complaint",
    "ComplaintAction",
    # Policy models
    "Policy",
    "PolicyVersion",
    # Document models
    "Document",
    "DocumentChunk",
    "DocumentAnnotation",
    "DocumentVersion",
    "DocumentSearchLog",
    "IndexJob",
    # Analytics models
    "Dashboard",
    "DashboardWidget",
    "SavedReport",
    "BenchmarkData",
    "CostRecord",
    "ROIInvestment",
    # Enterprise Risk Register (Tier 1)
    "EnterpriseRisk",
    "EnterpriseRiskControl",
    "RiskControlMapping",
    "BowTieElement",
    "KeyRiskIndicator",
    "RiskAssessmentHistory",
    "RiskAppetiteStatement",
    # IMS Unification (Tier 1)
    "IMSRequirement",
    "CrossStandardMapping",
    "IMSControl",
    "IMSControlRequirementMapping",
    "UnifiedAuditPlan",
    "ManagementReview",
    "ManagementReviewInput",
    "IMSProcessMap",
    "IMSObjective",
    # Document Control (Tier 1)
    "ControlledDocument",
    "ControlledDocumentVersion",
    "DocumentApprovalWorkflow",
    "DocumentApprovalInstance",
    "DocumentApprovalAction",
    "DocumentDistribution",
    "DocumentTrainingLink",
    "DocumentAccessLog",
    "ObsoleteDocumentRecord",
    # ISO 27001 Information Security (Tier 1)
    "InformationAsset",
    "ISO27001Control",
    "StatementOfApplicability",
    "SoAControlEntry",
    "InformationSecurityRisk",
    "SecurityIncident",
    "AccessControlRecord",
    "BusinessContinuityPlan",
    "SupplierSecurityAssessment",
    # UVDB Achilles Verify B2 Audit Protocol
    "UVDBSection",
    "UVDBQuestion",
    "UVDBAudit",
    "UVDBAuditResponse",
    "UVDBKPIRecord",
    "UVDBISOCrossMapping",
]
