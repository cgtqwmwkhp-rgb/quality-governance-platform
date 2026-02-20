"""Comprehensive E2E Tests for Phase 2 Implementation.

Tests all Phase 2 features:
- 2.1 RCA Tools (5-Whys, Fishbone, CAPA)
- 2.2 Auditor Competence Management

Target: 95%+ test coverage and functionality validation.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

# =============================================================================
# PHASE 2.1: RCA TOOLS TESTS
# =============================================================================


class TestFiveWhysAnalysis:
    """Tests for 5-Whys Analysis functionality."""

    def test_five_whys_model_creation(self):
        """Test creating a 5-Whys analysis."""
        from src.domain.models.rca_tools import FiveWhysAnalysis

        analysis = FiveWhysAnalysis(
            problem_statement="Equipment failure during production",
            entity_type="incident",
            entity_id=123,
            whys=[],
        )

        assert analysis.problem_statement == "Equipment failure during production"
        assert analysis.entity_type == "incident"
        assert analysis.whys == []
        assert not analysis.completed

    def test_add_why_iteration(self):
        """Test adding why iterations."""
        from src.domain.models.rca_tools import FiveWhysAnalysis

        analysis = FiveWhysAnalysis(
            problem_statement="Equipment failure",
            whys=[],
        )

        analysis.add_why("Why did the equipment fail?", "The motor overheated", "Temperature logs")

        assert len(analysis.whys) == 1
        assert analysis.whys[0]["level"] == 1
        assert analysis.whys[0]["why"] == "Why did the equipment fail?"
        assert analysis.whys[0]["answer"] == "The motor overheated"

    def test_add_multiple_whys(self):
        """Test adding multiple why iterations."""
        from src.domain.models.rca_tools import FiveWhysAnalysis

        analysis = FiveWhysAnalysis(problem_statement="Defect", whys=[])

        analysis.add_why("Why 1?", "Answer 1")
        analysis.add_why("Why 2?", "Answer 2")
        analysis.add_why("Why 3?", "Answer 3")
        analysis.add_why("Why 4?", "Answer 4")
        analysis.add_why("Why 5?", "Answer 5")

        assert len(analysis.whys) == 5
        assert analysis.whys[4]["level"] == 5

    def test_get_why_chain(self):
        """Test getting readable why chain."""
        from src.domain.models.rca_tools import FiveWhysAnalysis

        analysis = FiveWhysAnalysis(
            problem_statement="System crash",
            whys=[
                {"level": 1, "why": "Why crash?", "answer": "Memory full", "evidence": None},
                {"level": 2, "why": "Why memory full?", "answer": "Memory leak", "evidence": None},
            ],
            primary_root_cause="Memory leak in module X",
        )

        chain = analysis.get_why_chain()

        assert "System crash" in chain
        assert "Why crash?" in chain
        assert "Memory leak" in chain


class TestFishboneDiagram:
    """Tests for Fishbone Diagram functionality."""

    def test_fishbone_model_creation(self):
        """Test creating a Fishbone diagram."""
        from src.domain.models.rca_tools import FishboneCategory, FishboneDiagram

        diagram = FishboneDiagram(
            effect_statement="Product quality defect",
            causes={cat.value: [] for cat in FishboneCategory},
        )

        assert diagram.effect_statement == "Product quality defect"
        assert len(diagram.causes) == 6  # 6M categories

    def test_add_cause_to_category(self):
        """Test adding causes to categories."""
        from src.domain.models.rca_tools import FishboneCategory, FishboneDiagram

        diagram = FishboneDiagram(
            effect_statement="Defect",
            causes={cat.value: [] for cat in FishboneCategory},
        )

        diagram.add_cause(
            FishboneCategory.MANPOWER, "Inadequate training", ["No refresher courses", "Outdated materials"]
        )

        assert len(diagram.causes["manpower"]) == 1
        assert diagram.causes["manpower"][0]["cause"] == "Inadequate training"
        assert len(diagram.causes["manpower"][0]["sub_causes"]) == 2

    def test_add_causes_multiple_categories(self):
        """Test adding causes to multiple categories."""
        from src.domain.models.rca_tools import FishboneCategory, FishboneDiagram

        diagram = FishboneDiagram(
            effect_statement="Defect",
            causes={cat.value: [] for cat in FishboneCategory},
        )

        diagram.add_cause(FishboneCategory.MANPOWER, "Training gap")
        diagram.add_cause(FishboneCategory.METHOD, "Incorrect procedure")
        diagram.add_cause(FishboneCategory.MACHINE, "Worn tooling")

        counts = diagram.count_causes()

        assert counts["manpower"] == 1
        assert counts["method"] == 1
        assert counts["machine"] == 1

    def test_get_all_causes(self):
        """Test getting all causes across categories."""
        from src.domain.models.rca_tools import FishboneCategory, FishboneDiagram

        diagram = FishboneDiagram(
            effect_statement="Defect",
            causes={
                "manpower": [{"cause": "Cause 1", "sub_causes": []}],
                "method": [{"cause": "Cause 2", "sub_causes": []}],
                "machine": [],
                "material": [],
                "measurement": [],
                "mother_nature": [],
            },
        )

        all_causes = diagram.get_all_causes()

        assert len(all_causes) == 2
        assert all_causes[0]["category"] in ["manpower", "method"]


class TestBarrierAnalysis:
    """Tests for Barrier Analysis functionality."""

    def test_barrier_model_creation(self):
        """Test creating a Barrier Analysis."""
        from src.domain.models.rca_tools import BarrierAnalysis

        analysis = BarrierAnalysis(
            hazard_description="Fall from height",
            target_description="Worker",
            barriers=[],
        )

        assert analysis.hazard_description == "Fall from height"
        assert analysis.target_description == "Worker"

    def test_add_barrier(self):
        """Test adding barriers to analysis."""
        from src.domain.models.rca_tools import BarrierAnalysis

        analysis = BarrierAnalysis(
            hazard_description="Fall hazard",
            target_description="Worker",
            barriers=[],
        )

        analysis.add_barrier(
            barrier_name="Fall arrest system",
            barrier_type="physical",
            existed=True,
            status="failed",
            failure_reason="Not worn",
            failure_mode="human_error",
            recommendations=["Enforce PPE compliance"],
        )

        assert len(analysis.barriers) == 1
        assert analysis.barriers[0]["barrier_name"] == "Fall arrest system"
        assert analysis.barriers[0]["status"] == "failed"


class TestCAPAItem:
    """Tests for CAPA Item functionality."""

    def test_capa_model_creation(self):
        """Test creating a CAPA item."""
        from src.domain.models.rca_tools import CAPAItem

        capa = CAPAItem(
            action_type="corrective",
            title="Implement safety training",
            description="Develop and deliver training program",
            root_cause_addressed="Inadequate training",
            priority="high",
            status="open",
        )

        assert capa.action_type == "corrective"
        assert capa.priority == "high"
        assert capa.status == "open"

    def test_capa_types(self):
        """Test corrective vs preventive CAPA types."""
        from src.domain.models.rca_tools import CAPAItem

        corrective = CAPAItem(
            action_type="corrective",
            title="Fix existing problem",
            description="Address root cause",
        )

        preventive = CAPAItem(
            action_type="preventive",
            title="Prevent future occurrence",
            description="Implement controls",
        )

        assert corrective.action_type == "corrective"
        assert preventive.action_type == "preventive"


# =============================================================================
# PHASE 2.2: AUDITOR COMPETENCE TESTS
# =============================================================================


class TestAuditorProfile:
    """Tests for Auditor Profile functionality."""

    def test_profile_creation(self):
        """Test creating an auditor profile."""
        from src.domain.models.auditor_competence import AuditorProfile, CompetenceLevel

        profile = AuditorProfile(
            user_id=1,
            job_title="Safety Manager",
            department="QHSE",
            competence_level=CompetenceLevel.LEAD_AUDITOR,
            years_audit_experience=5.0,
            total_audits_conducted=25,
        )

        assert profile.user_id == 1
        assert profile.competence_level == CompetenceLevel.LEAD_AUDITOR
        assert profile.total_audits_conducted == 25

    def test_competence_levels(self):
        """Test competence level hierarchy."""
        from src.domain.models.auditor_competence import CompetenceLevel

        levels = list(CompetenceLevel)

        assert levels[0] == CompetenceLevel.TRAINEE
        assert levels[1] == CompetenceLevel.AUDITOR
        assert levels[2] == CompetenceLevel.LEAD_AUDITOR
        assert levels[3] == CompetenceLevel.PRINCIPAL_AUDITOR
        assert levels[4] == CompetenceLevel.EXPERT


class TestAuditorCertification:
    """Tests for Auditor Certification functionality."""

    def test_certification_creation(self):
        """Test creating a certification."""
        from src.domain.models.auditor_competence import AuditorCertification, CertificationStatus

        cert = AuditorCertification(
            profile_id=1,
            certification_name="ISO 9001 Lead Auditor",
            certification_body="IRCA",
            issued_date=datetime.utcnow(),
            expiry_date=datetime.utcnow() + timedelta(days=365 * 3),
            status=CertificationStatus.ACTIVE,
        )

        assert cert.certification_name == "ISO 9001 Lead Auditor"
        assert cert.status == CertificationStatus.ACTIVE

    def test_certification_validity_check(self):
        """Test certification validity checking."""
        from src.domain.models.auditor_competence import AuditorCertification, CertificationStatus

        # Valid certification
        valid_cert = AuditorCertification(
            profile_id=1,
            certification_name="Test Cert",
            certification_body="Test Body",
            issued_date=datetime.utcnow() - timedelta(days=365),
            expiry_date=datetime.utcnow() + timedelta(days=365),
            status=CertificationStatus.ACTIVE,
        )

        assert valid_cert.is_valid is True

        # Expired certification
        expired_cert = AuditorCertification(
            profile_id=1,
            certification_name="Test Cert",
            certification_body="Test Body",
            issued_date=datetime.utcnow() - timedelta(days=730),
            expiry_date=datetime.utcnow() - timedelta(days=1),
            status=CertificationStatus.ACTIVE,
        )

        assert expired_cert.is_valid is False

    def test_days_until_expiry(self):
        """Test days until expiry calculation."""
        from src.domain.models.auditor_competence import AuditorCertification, CertificationStatus

        cert = AuditorCertification(
            profile_id=1,
            certification_name="Test",
            certification_body="Body",
            issued_date=datetime.utcnow(),
            expiry_date=datetime.utcnow() + timedelta(days=90),
            status=CertificationStatus.ACTIVE,
        )

        days = cert.days_until_expiry
        assert days is not None
        assert 89 <= days <= 90


class TestAuditorTraining:
    """Tests for Auditor Training functionality."""

    def test_training_creation(self):
        """Test creating a training record."""
        from src.domain.models.auditor_competence import AuditorTraining

        training = AuditorTraining(
            profile_id=1,
            training_name="ISO 14001 Internal Auditor",
            training_type="course",
            training_provider="BSI",
            start_date=datetime.utcnow(),
            duration_hours=16,
        )

        assert training.training_name == "ISO 14001 Internal Auditor"
        assert not training.completed

    def test_training_completion(self):
        """Test training completion."""
        from src.domain.models.auditor_competence import AuditorTraining

        training = AuditorTraining(
            profile_id=1,
            training_name="Test Training",
            training_type="course",
            start_date=datetime.utcnow(),
            completed=True,
            completion_date=datetime.utcnow(),
            assessment_passed=True,
            assessment_score=92.0,
        )

        assert training.completed is True
        assert training.assessment_passed is True
        assert training.assessment_score == 92.0


class TestCompetencyArea:
    """Tests for Competency Area functionality."""

    def test_competency_area_creation(self):
        """Test creating a competency area."""
        from src.domain.models.auditor_competence import CompetencyArea

        area = CompetencyArea(
            code="AUDIT-TECH-01",
            name="Audit Techniques",
            category="technical",
            proficiency_scale={
                "1": "Basic awareness",
                "2": "Can perform with supervision",
                "3": "Competent practitioner",
                "4": "Advanced practitioner",
                "5": "Expert/Coach",
            },
            required_levels={
                "trainee": 1,
                "auditor": 2,
                "lead_auditor": 3,
                "principal_auditor": 4,
                "expert": 5,
            },
        )

        assert area.code == "AUDIT-TECH-01"
        assert area.category == "technical"
        assert area.required_levels["lead_auditor"] == 3


class TestAuditAssignmentCriteria:
    """Tests for Audit Assignment Criteria functionality."""

    def test_criteria_creation(self):
        """Test creating assignment criteria."""
        from src.domain.models.auditor_competence import AuditAssignmentCriteria, CompetenceLevel

        criteria = AuditAssignmentCriteria(
            audit_type="ISO 9001 Certification Audit",
            required_certifications=["ISO 9001 Lead Auditor"],
            minimum_auditor_level=CompetenceLevel.LEAD_AUDITOR,
            minimum_audits_conducted=10,
            minimum_years_experience=3.0,
        )

        assert criteria.audit_type == "ISO 9001 Certification Audit"
        assert criteria.minimum_auditor_level == CompetenceLevel.LEAD_AUDITOR
        assert criteria.minimum_audits_conducted == 10


# =============================================================================
# INTEGRATION TESTS
# =============================================================================


class TestRCAIntegration:
    """Integration tests for RCA tools."""

    def test_five_whys_to_capa_flow(self):
        """Test flow from 5-Whys analysis to CAPA creation."""
        from src.domain.models.rca_tools import CAPAItem, FiveWhysAnalysis

        # Create 5-Whys analysis
        analysis = FiveWhysAnalysis(
            id=1,
            problem_statement="Quality defect",
            whys=[],
            primary_root_cause="Inadequate training",
        )

        # Create CAPA linked to analysis
        capa = CAPAItem(
            five_whys_id=analysis.id,
            action_type="corrective",
            title="Develop training program",
            description="Create comprehensive training",
            root_cause_addressed=analysis.primary_root_cause,
        )

        assert capa.five_whys_id == 1
        assert capa.root_cause_addressed == "Inadequate training"

    def test_fishbone_to_capa_flow(self):
        """Test flow from Fishbone to CAPA creation."""
        from src.domain.models.rca_tools import CAPAItem, FishboneDiagram

        # Create Fishbone
        diagram = FishboneDiagram(
            id=1,
            effect_statement="Defect",
            causes={"manpower": [{"cause": "Training gap", "sub_causes": []}]},
            root_cause="Training gap",
            root_cause_category="manpower",
        )

        # Create CAPA
        capa = CAPAItem(
            fishbone_id=diagram.id,
            action_type="preventive",
            title="Training improvement",
            description="Address training gap",
            root_cause_addressed=diagram.root_cause,
        )

        assert capa.fishbone_id == 1


class TestCompetenceIntegration:
    """Integration tests for auditor competence."""

    def test_auditor_qualification_check(self):
        """Test checking if auditor meets criteria."""
        from src.domain.models.auditor_competence import AuditAssignmentCriteria, AuditorProfile, CompetenceLevel

        # Define criteria
        criteria = AuditAssignmentCriteria(
            audit_type="ISO 9001",
            minimum_auditor_level=CompetenceLevel.LEAD_AUDITOR,
            minimum_audits_conducted=5,
        )

        # Qualified auditor
        qualified = AuditorProfile(
            user_id=1,
            competence_level=CompetenceLevel.LEAD_AUDITOR,
            total_audits_conducted=10,
        )

        # Check qualification
        level_order = [l.value for l in CompetenceLevel]
        auditor_level_idx = level_order.index(qualified.competence_level.value)
        required_level_idx = level_order.index(criteria.minimum_auditor_level.value)

        meets_level = auditor_level_idx >= required_level_idx
        meets_experience = qualified.total_audits_conducted >= criteria.minimum_audits_conducted

        assert meets_level is True
        assert meets_experience is True


# =============================================================================
# EDGE CASES
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_whys_chain(self):
        """Test getting chain with no whys."""
        from src.domain.models.rca_tools import FiveWhysAnalysis

        analysis = FiveWhysAnalysis(
            problem_statement="Test",
            whys=[],
        )

        chain = analysis.get_why_chain()
        assert chain == ""

    def test_fishbone_empty_categories(self):
        """Test fishbone with no causes."""
        from src.domain.models.rca_tools import FishboneDiagram

        diagram = FishboneDiagram(
            effect_statement="Test",
            causes={},
        )

        all_causes = diagram.get_all_causes()
        assert all_causes == []

    def test_certification_no_expiry(self):
        """Test certification without expiry date."""
        from src.domain.models.auditor_competence import AuditorCertification, CertificationStatus

        cert = AuditorCertification(
            profile_id=1,
            certification_name="Lifetime Cert",
            certification_body="Body",
            issued_date=datetime.utcnow(),
            expiry_date=None,
            status=CertificationStatus.ACTIVE,
        )

        assert cert.days_until_expiry is None
        assert cert.is_valid is True  # No expiry = valid


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
