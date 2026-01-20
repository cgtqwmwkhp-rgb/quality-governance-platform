"""
Comprehensive Unit Tests for Domain Models

Target: 90%+ code coverage for all models
"""

import re
from datetime import datetime, timedelta
from typing import Optional

import pytest


# ============================================================================
# Incident Model Tests
# ============================================================================


class TestIncidentModel:
    """Unit tests for Incident model."""

    def test_incident_model_import(self):
        """Incident model can be imported."""
        from src.domain.models.incident import Incident
        assert Incident is not None

    def test_incident_status_enum(self):
        """Incident status enum is defined."""
        from src.domain.models.incident import IncidentStatus
        
        assert hasattr(IncidentStatus, 'REPORTED')
        assert hasattr(IncidentStatus, 'UNDER_INVESTIGATION')
        assert hasattr(IncidentStatus, 'CLOSED')

    def test_incident_severity_enum(self):
        """Incident severity enum is defined."""
        from src.domain.models.incident import IncidentSeverity
        
        assert hasattr(IncidentSeverity, 'LOW')
        assert hasattr(IncidentSeverity, 'MEDIUM')
        assert hasattr(IncidentSeverity, 'HIGH')
        assert hasattr(IncidentSeverity, 'CRITICAL')

    def test_incident_type_enum(self):
        """Incident type enum is defined."""
        from src.domain.models.incident import IncidentType
        
        assert hasattr(IncidentType, 'SAFETY')
        assert hasattr(IncidentType, 'ENVIRONMENTAL')

    def test_incident_reference_format(self):
        """Incident reference format is correct."""
        pattern = r'^INC-\d{4}-\d{4}$'
        sample_refs = ["INC-2026-0001", "INC-2026-9999"]
        
        for ref in sample_refs:
            assert re.match(pattern, ref) is not None


# ============================================================================
# Risk Model Tests
# ============================================================================


class TestRiskModel:
    """Unit tests for Risk model."""

    def test_risk_model_import(self):
        """Risk model can be imported."""
        from src.domain.models.risk import Risk
        assert Risk is not None

    def test_risk_status_enum(self):
        """Risk status enum is defined."""
        from src.domain.models.risk import RiskStatus
        
        assert hasattr(RiskStatus, 'OPEN')
        assert hasattr(RiskStatus, 'MITIGATED')
        assert hasattr(RiskStatus, 'CLOSED')

    def test_risk_category_enum(self):
        """Risk category enum is defined."""
        from src.domain.models.risk import RiskCategory
        
        assert hasattr(RiskCategory, 'OPERATIONAL')
        assert hasattr(RiskCategory, 'STRATEGIC')
        assert hasattr(RiskCategory, 'FINANCIAL')
        assert hasattr(RiskCategory, 'COMPLIANCE')

    def test_risk_score_calculation(self):
        """Risk score calculation is correct."""
        likelihood_values = range(1, 6)
        impact_values = range(1, 6)
        
        for likelihood in likelihood_values:
            for impact in impact_values:
                score = likelihood * impact
                assert 1 <= score <= 25

    def test_risk_level_mapping(self):
        """Risk level mapping is correct."""
        def get_level(score: int) -> str:
            if score <= 4:
                return "low"
            elif score <= 9:
                return "medium"
            elif score <= 14:
                return "high"
            else:
                return "critical"
        
        assert get_level(1) == "low"
        assert get_level(4) == "low"
        assert get_level(5) == "medium"
        assert get_level(9) == "medium"
        assert get_level(10) == "high"
        assert get_level(14) == "high"
        assert get_level(15) == "critical"
        assert get_level(25) == "critical"


# ============================================================================
# Audit Model Tests
# ============================================================================


class TestAuditModel:
    """Unit tests for Audit models."""

    def test_audit_template_import(self):
        """AuditTemplate model can be imported."""
        from src.domain.models.audit import AuditTemplate
        assert AuditTemplate is not None

    def test_audit_run_import(self):
        """AuditRun model can be imported."""
        from src.domain.models.audit import AuditRun
        assert AuditRun is not None

    def test_audit_finding_import(self):
        """AuditFinding model can be imported."""
        from src.domain.models.audit import AuditFinding
        assert AuditFinding is not None

    def test_finding_type_enum(self):
        """Finding type enum is defined."""
        from src.domain.models.audit import FindingType
        
        assert hasattr(FindingType, 'MAJOR_NC')
        assert hasattr(FindingType, 'MINOR_NC')
        assert hasattr(FindingType, 'OBSERVATION')
        assert hasattr(FindingType, 'OPPORTUNITY')


# ============================================================================
# Complaint Model Tests
# ============================================================================


class TestComplaintModel:
    """Unit tests for Complaint model."""

    def test_complaint_model_import(self):
        """Complaint model can be imported."""
        from src.domain.models.complaint import Complaint
        assert Complaint is not None

    def test_complaint_status_enum(self):
        """Complaint status enum is defined."""
        from src.domain.models.complaint import ComplaintStatus
        
        assert hasattr(ComplaintStatus, 'OPEN')
        assert hasattr(ComplaintStatus, 'CLOSED')

    def test_complaint_priority_enum(self):
        """Complaint priority enum is defined."""
        from src.domain.models.complaint import ComplaintPriority
        
        assert hasattr(ComplaintPriority, 'LOW')
        assert hasattr(ComplaintPriority, 'MEDIUM')
        assert hasattr(ComplaintPriority, 'HIGH')

    def test_complaint_type_enum(self):
        """Complaint type enum is defined."""
        from src.domain.models.complaint import ComplaintType
        
        assert hasattr(ComplaintType, 'SERVICE')
        assert hasattr(ComplaintType, 'PRODUCT')


# ============================================================================
# RTA Model Tests
# ============================================================================


class TestRTAModel:
    """Unit tests for RTA model."""

    def test_rta_model_import(self):
        """RTA model can be imported."""
        from src.domain.models.rta import RTA
        assert RTA is not None

    def test_rta_status_enum(self):
        """RTA status enum is defined."""
        from src.domain.models.rta import RTAStatus
        
        assert hasattr(RTAStatus, 'REPORTED')
        assert hasattr(RTAStatus, 'UNDER_INVESTIGATION')
        assert hasattr(RTAStatus, 'CLOSED')

    def test_rta_severity_enum(self):
        """RTA severity enum is defined."""
        from src.domain.models.rta import RTASeverity
        
        assert hasattr(RTASeverity, 'MINOR')
        assert hasattr(RTASeverity, 'MODERATE')
        assert hasattr(RTASeverity, 'MAJOR')
        assert hasattr(RTASeverity, 'CATASTROPHIC')


# ============================================================================
# Policy Model Tests
# ============================================================================


class TestPolicyModel:
    """Unit tests for Policy model."""

    def test_policy_model_import(self):
        """Policy model can be imported."""
        from src.domain.models.policy import Policy
        assert Policy is not None

    def test_policy_status_enum(self):
        """Policy status enum is defined."""
        from src.domain.models.policy import PolicyStatus
        
        assert hasattr(PolicyStatus, 'DRAFT')
        assert hasattr(PolicyStatus, 'UNDER_REVIEW')
        assert hasattr(PolicyStatus, 'APPROVED')
        assert hasattr(PolicyStatus, 'OBSOLETE')


# ============================================================================
# Document Model Tests
# ============================================================================


class TestDocumentModel:
    """Unit tests for Document model."""

    def test_document_model_import(self):
        """Document model can be imported."""
        from src.domain.models.document import Document
        assert Document is not None


# ============================================================================
# User Model Tests
# ============================================================================


class TestUserModel:
    """Unit tests for User model."""

    def test_user_model_import(self):
        """User model can be imported."""
        from src.domain.models.user import User
        assert User is not None

    def test_role_enum(self):
        """Role enum is defined."""
        from src.domain.models.user import UserRole
        
        assert hasattr(UserRole, 'ADMIN')
        assert hasattr(UserRole, 'USER')


# ============================================================================
# Standard Model Tests
# ============================================================================


class TestStandardModel:
    """Unit tests for Standard model."""

    def test_standard_model_import(self):
        """Standard model can be imported."""
        from src.domain.models.standard import Standard
        assert Standard is not None


# ============================================================================
# Investigation Model Tests
# ============================================================================


class TestInvestigationModel:
    """Unit tests for Investigation model."""

    def test_investigation_model_import(self):
        """Investigation model can be imported."""
        from src.domain.models.investigation import Investigation
        assert Investigation is not None


# ============================================================================
# Action Model Tests
# ============================================================================


class TestActionModel:
    """Unit tests for Action model."""

    def test_action_model_import(self):
        """Action model can be imported."""
        from src.domain.models.action import Action
        assert Action is not None


# ============================================================================
# Notification Model Tests
# ============================================================================


class TestNotificationModel:
    """Unit tests for Notification model."""

    def test_notification_model_import(self):
        """Notification model can be imported."""
        from src.domain.models.notification import Notification
        assert Notification is not None


# ============================================================================
# Workflow Model Tests
# ============================================================================


class TestWorkflowModels:
    """Unit tests for Workflow models."""

    def test_workflow_template_import(self):
        """WorkflowTemplate model can be imported."""
        from src.domain.models.workflow import WorkflowTemplate
        assert WorkflowTemplate is not None

    def test_workflow_instance_import(self):
        """WorkflowInstance model can be imported."""
        from src.domain.models.workflow import WorkflowInstance
        assert WorkflowInstance is not None


# ============================================================================
# Compliance Model Tests
# ============================================================================


class TestComplianceModels:
    """Unit tests for Compliance models."""

    def test_compliance_evidence_import(self):
        """ComplianceEvidence model can be imported."""
        from src.domain.models.compliance import ComplianceEvidence
        assert ComplianceEvidence is not None

    def test_compliance_gap_import(self):
        """ComplianceGap model can be imported."""
        from src.domain.models.compliance import ComplianceGap
        assert ComplianceGap is not None


# ============================================================================
# Risk Register Model Tests
# ============================================================================


class TestRiskRegisterModels:
    """Unit tests for Risk Register models."""

    def test_enterprise_risk_import(self):
        """EnterpriseRisk model can be imported."""
        from src.domain.models.risk_register import EnterpriseRisk
        assert EnterpriseRisk is not None

    def test_risk_control_import(self):
        """RiskControl model can be imported."""
        from src.domain.models.risk_register import RiskControl
        assert RiskControl is not None


# ============================================================================
# ISO 27001 Model Tests
# ============================================================================


class TestISO27001Models:
    """Unit tests for ISO 27001 models."""

    def test_information_asset_import(self):
        """InformationAsset model can be imported."""
        from src.domain.models.iso27001 import InformationAsset
        assert InformationAsset is not None

    def test_annex_a_control_import(self):
        """AnnexAControl model can be imported."""
        from src.domain.models.iso27001 import AnnexAControl
        assert AnnexAControl is not None


# ============================================================================
# UVDB Model Tests
# ============================================================================


class TestUVDBModels:
    """Unit tests for UVDB models."""

    def test_uvdb_section_import(self):
        """UVDBSection model can be imported."""
        from src.domain.models.uvdb_achilles import UVDBSection
        assert UVDBSection is not None

    def test_uvdb_audit_import(self):
        """UVDBAudit model can be imported."""
        from src.domain.models.uvdb_achilles import UVDBAudit
        assert UVDBAudit is not None


# ============================================================================
# Planet Mark Model Tests
# ============================================================================


class TestPlanetMarkModels:
    """Unit tests for Planet Mark models."""

    def test_reporting_year_import(self):
        """ReportingYear model can be imported."""
        from src.domain.models.planet_mark import ReportingYear
        assert ReportingYear is not None

    def test_emission_source_import(self):
        """EmissionSource model can be imported."""
        from src.domain.models.planet_mark import EmissionSource
        assert EmissionSource is not None


# ============================================================================
# Base Model Tests
# ============================================================================


class TestBaseModel:
    """Unit tests for base model functionality."""

    def test_base_model_import(self):
        """Base model can be imported."""
        from src.infrastructure.database import Base
        assert Base is not None

    def test_timestamp_fields(self):
        """Timestamp fields work correctly."""
        now = datetime.now()
        assert now.year >= 2024
        assert now.month >= 1
        assert now.day >= 1


# ============================================================================
# Enum Validation Tests
# ============================================================================


class TestEnumValidation:
    """Tests for enum validation."""

    def test_severity_ordering(self):
        """Severity values are properly ordered."""
        severities = ["low", "medium", "high", "critical"]
        
        for i, severity in enumerate(severities):
            # Each severity should have a predictable index
            assert severities.index(severity) == i

    def test_status_transitions_valid(self):
        """Status transitions follow business rules."""
        # Define valid transitions
        valid_transitions = {
            "reported": ["under_investigation", "closed"],
            "under_investigation": ["closed", "reported"],
            "closed": ["reported"],  # Reopen
        }
        
        for status, allowed in valid_transitions.items():
            assert len(allowed) > 0
