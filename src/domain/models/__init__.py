"""Domain models package."""

# AI Copilot (Tier 2)
from src.domain.models.ai_copilot import (
    CopilotAction,
    CopilotFeedback,
    CopilotKnowledge,
    CopilotMessage,
    CopilotSession,
)
from src.domain.models.analytics import (
    BenchmarkData,
    CostRecord,
    Dashboard,
    DashboardWidget,
    ROIInvestment,
    SavedReport,
)
from src.domain.models.audit import AuditFinding, AuditQuestion, AuditRun, AuditTemplate

# CAPA (Corrective and Preventive Action)
from src.domain.models.capa import CAPAAction, CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.models.base import AuditTrailMixin, ReferenceNumberMixin, SoftDeleteMixin, TimestampMixin
from src.domain.models.complaint import Complaint, ComplaintAction

# Compliance Automation
from src.domain.models.compliance_automation import (
    Certificate,
    ComplianceScore,
    GapAnalysis,
    RegulatoryUpdate,
    RIDDORSubmission,
    ScheduledAudit,
)

# Compliance Evidence Links
from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkMethod

# Digital Signatures (Tier 2)
from src.domain.models.digital_signature import (
    Signature,
    SignatureAuditLog,
    SignatureRequest,
    SignatureRequestSigner,
    SignatureTemplate,
)
from src.domain.models.document import (
    Document,
    DocumentAnnotation,
    DocumentChunk,
    DocumentSearchLog,
    DocumentVersion,
    IndexJob,
)

# Document Control (Tier 1)
from src.domain.models.document_control import (
    ControlledDocument,
    ControlledDocumentVersion,
    DocumentAccessLog,
    DocumentApprovalAction,
    DocumentApprovalInstance,
    DocumentApprovalWorkflow,
    DocumentDistribution,
    DocumentTrainingLink,
    ObsoleteDocumentRecord,
)

# Evidence Assets (Shared Attachments Module)
from src.domain.models.evidence_asset import (
    EvidenceAsset,
    EvidenceAssetType,
    EvidenceRetentionPolicy,
    EvidenceSourceModule,
    EvidenceVisibility,
)

# Form Configuration (Admin Form Builder)
from src.domain.models.form_config import Contract, FormField, FormStep, FormTemplate, LookupOption, SystemSetting

# IMS Unification (Tier 1)
from src.domain.models.ims_unification import (
    CrossStandardMapping,
    IMSControl,
    IMSControlRequirementMapping,
    IMSObjective,
    IMSProcessMap,
    IMSRequirement,
    ManagementReview,
    ManagementReviewInput,
    UnifiedAuditPlan,
)
from src.domain.models.incident import Incident, IncidentAction

# Investigations (Stage 2)
from src.domain.models.investigation import (
    AssignedEntityType,
    CustomerPackAudience,
    InvestigationComment,
    InvestigationCustomerPack,
    InvestigationLevel,
    InvestigationRevisionEvent,
    InvestigationRun,
    InvestigationStatus,
    InvestigationTemplate,
)

# ISO 27001 Information Security (Tier 1)
from src.domain.models.iso27001 import (
    AccessControlRecord,
    BusinessContinuityPlan,
    InformationAsset,
    InformationSecurityRisk,
    ISO27001Control,
    SecurityIncident,
    SoAControlEntry,
    StatementOfApplicability,
    SupplierSecurityAssessment,
)

# Planet Mark Carbon Management
from src.domain.models.planet_mark import (
    CarbonEvidence,
    CarbonReportingYear,
    DataQualityAssessment,
    EmissionSource,
    FleetEmissionRecord,
    ImprovementAction,
    ISO14001CrossMapping,
    Scope3CategoryData,
    SupplierEmissionData,
    UtilityMeterReading,
)
from src.domain.models.policy import Policy, PolicyVersion
from src.domain.models.risk import OperationalRiskControl, Risk, RiskAssessment

# Enterprise Risk Register (Tier 1)
from src.domain.models.risk_register import (
    BowTieElement,
    EnterpriseKeyRiskIndicator,
    EnterpriseRisk,
    EnterpriseRiskControl,
    RiskAppetiteStatement,
    RiskAssessmentHistory,
    RiskControlMapping,
)
from src.domain.models.rta import RoadTrafficCollision, RTAAction
from src.domain.models.standard import Clause, Control, Standard
from src.domain.models.token_blacklist import TokenBlacklist
from src.domain.models.user import Role, User, UserRole

# UVDB Achilles Verify B2 Audit Protocol
from src.domain.models.uvdb_achilles import (
    UVDBAudit,
    UVDBAuditResponse,
    UVDBISOCrossMapping,
    UVDBKPIRecord,
    UVDBQuestion,
    UVDBSection,
)

# Workflow Persistence Models
from src.domain.models.workflow import ApprovalRequest as WorkflowApprovalRequest
from src.domain.models.workflow import (
    EscalationLog,
    EscalationRule,
    UserDelegation,
    WorkflowInstance,
    WorkflowStep,
    WorkflowTemplate,
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
    "OperationalRiskControl",
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
    "EnterpriseKeyRiskIndicator",
    "RiskControlMapping",
    "BowTieElement",
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
    # Planet Mark Carbon Management
    "CarbonReportingYear",
    "EmissionSource",
    "Scope3CategoryData",
    "ImprovementAction",
    "DataQualityAssessment",
    "CarbonEvidence",
    "FleetEmissionRecord",
    "UtilityMeterReading",
    "SupplierEmissionData",
    "ISO14001CrossMapping",
    # AI Copilot (Tier 2)
    "CopilotSession",
    "CopilotMessage",
    "CopilotAction",
    "CopilotKnowledge",
    "CopilotFeedback",
    # Digital Signatures (Tier 2)
    "SignatureRequest",
    "SignatureRequestSigner",
    "Signature",
    "SignatureTemplate",
    "SignatureAuditLog",
    # Form Configuration (Admin Form Builder)
    "FormTemplate",
    "FormStep",
    "FormField",
    "Contract",
    "SystemSetting",
    "LookupOption",
    # Evidence Assets (Shared Attachments Module)
    "EvidenceAsset",
    "EvidenceAssetType",
    "EvidenceSourceModule",
    "EvidenceVisibility",
    "EvidenceRetentionPolicy",
    # Investigations (Stage 2)
    "InvestigationTemplate",
    "InvestigationRun",
    "InvestigationStatus",
    "InvestigationLevel",
    "AssignedEntityType",
    "CustomerPackAudience",
    "InvestigationComment",
    "InvestigationRevisionEvent",
    "InvestigationCustomerPack",
    # Compliance Evidence Links
    "ComplianceEvidenceLink",
    "EvidenceLinkMethod",
    # Compliance Automation
    "RegulatoryUpdate",
    "GapAnalysis",
    "Certificate",
    "ScheduledAudit",
    "ComplianceScore",
    "RIDDORSubmission",
    # Workflow Persistence Models
    "WorkflowTemplate",
    "WorkflowInstance",
    "WorkflowStep",
    "WorkflowApprovalRequest",
    "EscalationRule",
    "EscalationLog",
    "UserDelegation",
    # Token Blacklist (JWT Revocation)
    "TokenBlacklist",
    # CAPA (Corrective and Preventive Action)
    "CAPAAction",
    "CAPAStatus",
    "CAPAType",
    "CAPAPriority",
    "CAPASource",
]
