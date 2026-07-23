"""Domain models package."""

# AI Copilot (Tier 2)
from src.domain.models.action_owner_note import ActionOwnerNote
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
from src.domain.models.api_idempotency import ApiIdempotencyKey
from src.domain.models.assessment import (
    AssessmentOutcome,
    AssessmentResponse,
    AssessmentRun,
    AssessmentStatus,
    CompetencyVerdict,
)
from src.domain.models.asset import (
    Asset,
    AssetAssignmentEvent,
    AssetCategory,
    AssetStatus,
    AssetType,
    TemplateAssetType,
)
from src.domain.models.audit import (
    AuditFinding,
    AuditQuestion,
    AuditResponse,
    AuditRun,
    AuditSection,
    AuditStatus,
    AuditTemplate,
    FindingSeverity,
    FindingStatus,
    QuestionCriticality,
    TemplateLifecycleStatus,
    TemplateVersion,
)
from src.domain.models.base import AuditTrailMixin, Base, ReferenceNumberMixin, SoftDeleteMixin, TimestampMixin
from src.domain.models.capa import CAPAAction
from src.domain.models.competence_gap import (
    CompetenceGapAction,
    CompetenceGapSignalType,
    CompetenceGapSourceType,
    CompetenceGapStatus,
)
from src.domain.models.complaint import Complaint, ComplaintAction
from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkMethod, EvidenceLinkStatus

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
from src.domain.models.document_campaign import (
    AssignmentStatus,
    CampaignAssignment,
    CampaignStatus,
    DocumentCampaign,
    EngineerGroup,
    EngineerGroupMember,
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

# Governance Library taxonomy (Wave W0)
from src.domain.models.document_library import DocumentCategory, DocumentTag, PelDocRefCounter
from src.domain.models.driver_profile import AcknowledgementStatus, DriverAcknowledgement, DriverProfile
from src.domain.models.engineer import (
    CompetencyLifecycleState,
    CompetencyRecord,
    CompetencyRequirement,
    Engineer,
    OnboardingChecklist,
    OnboardingStatus,
    TicketVerifyState,
    TrainingTicket,
)
from src.domain.models.evidence_asset import (
    EvidenceAsset,
    EvidenceAssetType,
    EvidenceRetentionPolicy,
    EvidenceSourceModule,
    EvidenceVisibility,
)
from src.domain.models.external_audit_import import (
    ExternalAuditDraft,
    ExternalAuditDraftStatus,
    ExternalAuditImportJob,
    ExternalAuditImportStatus,
)
from src.domain.models.external_audit_record import ExternalAuditRecord
from src.domain.models.failed_task import FailedTask

# Evidence Assets (Shared Attachments Module)
from src.domain.models.feature_flag import FeatureFlag

# Form Configuration (Admin Form Builder)
from src.domain.models.form_config import Contract, FormField, FormStep, FormTemplate, LookupOption, SystemSetting
from src.domain.models.governed_knowledge import (
    AiDecisionLog,
    DiscussionThreadStatus,
    DocumentDiscussionMessage,
    DocumentDiscussionThread,
    DocumentQuizDraft,
    QuizDraftStatus,
    RegulatoryImpactStatus,
    RegulatoryWatchImpact,
)

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
from src.domain.models.hs_reporting_period import HsReportingPeriod
from src.domain.models.induction import (
    InductionResponse,
    InductionRun,
    InductionStage,
    InductionStatus,
    UnderstandingVerdict,
)

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
from src.domain.models.legal_hold import LegalHoldStatus, MatterLegalHold

# Governance Library review packs (Wave W3)
from src.domain.models.library_review import (
    FindingDisposition,
    HorizonProvider,
    LibraryRegulatoryFinding,
    LibraryReviewPack,
    ReviewPackStatus,
)
from src.domain.models.location import Location, LocationKind
from src.domain.models.loler import LOLERDefect, LOLERDefectCategory, LOLERExamination, LOLERExaminationType
from src.domain.models.partner_webhook import (
    PARTNER_WEBHOOK_EVENTS,
    WebhookDeliveryLog,
    WebhookDeliveryStatus,
    WebhookSubscription,
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
    CaseRiskLink,
    EnterpriseKeyRiskIndicator,
    EnterpriseRisk,
    EnterpriseRiskControl,
    RiskActivityEvent,
    RiskAppetiteStatement,
    RiskAssessmentHistory,
    RiskControlMapping,
    RiskNote,
)
from src.domain.models.rta import RoadTrafficCollision, RTAAction
from src.domain.models.standard import Clause, Control, Standard
from src.domain.models.tenant import Tenant, TenantInvitation, TenantUser
from src.domain.models.token_blacklist import TokenBlacklist
from src.domain.models.training_matrix import (
    TrainingMatrixCell,
    TrainingMatrixCourse,
    TrainingMatrixFrequencyChangeRequest,
    TrainingMatrixImport,
    TrainingMatrixNameMap,
    TrainingMatrixPerson,
    TrainingMatrixRequirement,
)
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
from src.domain.models.vehicle_registry import ComplianceStatus, FleetStatus, VehicleRegistry

__all__ = [
    # ORM base
    "Base",
    # Base mixins
    "TimestampMixin",
    "ReferenceNumberMixin",
    "SoftDeleteMixin",
    "AuditTrailMixin",
    # User models
    "User",
    "Role",
    "UserRole",
    "Tenant",
    "TenantUser",
    "TenantInvitation",
    "TokenBlacklist",
    "FailedTask",
    "ApiIdempotencyKey",
    # Standard models
    "Standard",
    "Clause",
    "Control",
    # Audit models
    "Asset",
    "AssetAssignmentEvent",
    "AssetCategory",
    "AssetStatus",
    "AssetType",
    "TemplateAssetType",
    "Location",
    "LocationKind",
    "MatterLegalHold",
    "LegalHoldStatus",
    "AuditTemplate",
    "AuditQuestion",
    "AuditRun",
    "AuditSection",
    "AuditResponse",
    "ComplianceEvidenceLink",
    "EvidenceLinkMethod",
    "EvidenceLinkStatus",
    "AiDecisionLog",
    "DocumentDiscussionMessage",
    "DocumentDiscussionThread",
    "DocumentQuizDraft",
    "DiscussionThreadStatus",
    "QuizDraftStatus",
    "RegulatoryImpactStatus",
    "RegulatoryWatchImpact",
    "AuditStatus",
    "AuditFinding",
    "FindingStatus",
    "FindingSeverity",
    "TemplateVersion",
    "TemplateLifecycleStatus",
    "QuestionCriticality",
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
    # CAPA models
    "CAPAAction",
    "ActionOwnerNote",
    # Policy models
    "Policy",
    "PolicyVersion",
    # Partner webhook models (Wave5)
    "PARTNER_WEBHOOK_EVENTS",
    "WebhookDeliveryLog",
    "WebhookDeliveryStatus",
    "WebhookSubscription",
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
    "CaseRiskLink",
    "EnterpriseRisk",
    "EnterpriseRiskControl",
    "EnterpriseKeyRiskIndicator",
    "RiskControlMapping",
    "BowTieElement",
    "RiskAssessmentHistory",
    "RiskActivityEvent",
    "RiskNote",
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
    # Governance Library taxonomy (Wave W0)
    "DocumentCategory",
    "DocumentTag",
    "PelDocRefCounter",
    # Governance Library review packs (Wave W3)
    "LibraryReviewPack",
    "LibraryRegulatoryFinding",
    "ReviewPackStatus",
    "FindingDisposition",
    "HorizonProvider",
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
    # Feature Flags
    "FeatureFlag",
    # Evidence Assets (Shared Attachments Module)
    "EvidenceAsset",
    "EvidenceAssetType",
    "EvidenceSourceModule",
    "EvidenceVisibility",
    "EvidenceRetentionPolicy",
    "ExternalAuditImportJob",
    "ExternalAuditImportStatus",
    "ExternalAuditDraft",
    "ExternalAuditDraftStatus",
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
    # Workforce Development (Assessment & Induction)
    "Engineer",
    "CompetencyRecord",
    "CompetencyRequirement",
    "CompetencyLifecycleState",
    "TrainingTicket",
    "TrainingMatrixImport",
    "TrainingMatrixCourse",
    "TrainingMatrixPerson",
    "TrainingMatrixCell",
    "TrainingMatrixNameMap",
    "TrainingMatrixRequirement",
    "TrainingMatrixFrequencyChangeRequest",
    "TicketVerifyState",
    "CompetenceGapAction",
    "CompetenceGapSignalType",
    "CompetenceGapSourceType",
    "CompetenceGapStatus",
    "OnboardingChecklist",
    "OnboardingStatus",
    "LOLERExamination",
    "LOLERDefect",
    "LOLERDefectCategory",
    "LOLERExaminationType",
    "AssessmentRun",
    "AssessmentResponse",
    "AssessmentStatus",
    "CompetencyVerdict",
    "AssessmentOutcome",
    "InductionRun",
    "InductionResponse",
    "InductionStatus",
    "InductionStage",
    "UnderstandingVerdict",
    # Vehicle Registry (Fleet Governance)
    "VehicleRegistry",
    "FleetStatus",
    "ComplianceStatus",
    # Driver Profiles (Driver Accountability)
    "DriverProfile",
    "DriverAcknowledgement",
    "AcknowledgementStatus",
    # Document Campaigns (Engineer document read/quiz/sign-off spine)
    "EngineerGroup",
    "EngineerGroupMember",
    "DocumentCampaign",
    "CampaignAssignment",
    "CampaignStatus",
    "AssignmentStatus",
]
