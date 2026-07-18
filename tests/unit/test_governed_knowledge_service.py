"""Unit tests for GovernedKnowledgeService — threshold logic and scheme mapping."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.models.compliance_evidence import ComplianceEvidenceLink, EvidenceLinkMethod, EvidenceLinkStatus
from src.domain.services.governed_knowledge_service import (
    AUTO_CONFIRM_THRESHOLD,
    STRICT_DOC_TYPES,
    GovernedKnowledgeService,
    _normalize_confidence,
    resolve_link_status,
)


class TestNormalizeConfidence:
    def test_decimal_passthrough(self) -> None:
        assert _normalize_confidence(0.9) == 0.9

    def test_percentage_converted(self) -> None:
        assert _normalize_confidence(90.0) == 0.9

    def test_none_returns_zero(self) -> None:
        assert _normalize_confidence(None) == 0.0


class TestResolveLinkStatus:
    def test_high_confidence_auto_confirms(self) -> None:
        status, auto_applied = resolve_link_status(90.0, "procedure")
        assert status == EvidenceLinkStatus.CONFIRMED
        assert auto_applied is True

    def test_threshold_boundary_confirms(self) -> None:
        status, auto_applied = resolve_link_status(85.0, "policy")
        assert status == EvidenceLinkStatus.CONFIRMED
        assert auto_applied is True

    def test_below_threshold_stays_proposed(self) -> None:
        status, auto_applied = resolve_link_status(84.9, "policy")
        assert status == EvidenceLinkStatus.PROPOSED
        assert auto_applied is False

    def test_decimal_confidence_above_threshold(self) -> None:
        status, auto_applied = resolve_link_status(0.86, "manual")
        assert status == EvidenceLinkStatus.CONFIRMED
        assert auto_applied is True

    @pytest.mark.parametrize("doc_type", sorted(STRICT_DOC_TYPES))
    def test_strict_doc_types_never_auto_confirm(self, doc_type: str) -> None:
        status, auto_applied = resolve_link_status(99.0, doc_type)
        assert status == EvidenceLinkStatus.PROPOSED
        assert auto_applied is False

    def test_rams_alias_in_strict_set(self) -> None:
        assert "rams" in STRICT_DOC_TYPES
        assert "method_statement" in STRICT_DOC_TYPES

    def test_force_proposed_overrides_high_confidence(self) -> None:
        status, auto_applied = resolve_link_status(99.0, "procedure", force_proposed=True)
        assert status == EvidenceLinkStatus.PROPOSED
        assert auto_applied is False


class TestClassifyOperationalSignal:
    def test_incident_defaults_to_nonconformity(self) -> None:
        from src.domain.models.compliance_evidence import EvidenceSignalType
        from src.domain.services.governed_knowledge_service import classify_operational_signal

        assert classify_operational_signal("incident") == EvidenceSignalType.NONCONFORMITY

    def test_near_miss_defaults_to_gap(self) -> None:
        from src.domain.models.compliance_evidence import EvidenceSignalType
        from src.domain.services.governed_knowledge_service import classify_operational_signal

        assert classify_operational_signal("near_miss") == EvidenceSignalType.GAP

    def test_finding_type_opportunity(self) -> None:
        from src.domain.models.compliance_evidence import EvidenceSignalType
        from src.domain.services.governed_knowledge_service import classify_operational_signal

        assert (
            classify_operational_signal("audit_finding", finding_type="opportunity") == EvidenceSignalType.OPPORTUNITY
        )


class TestAssessOperationalEntity:
    @pytest.mark.asyncio
    async def test_never_auto_confirms_and_sets_signal(self) -> None:
        svc = GovernedKnowledgeService()
        user = MagicMock(id=5, email="ai@example.com")
        added: list = []

        async def fake_execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            result.all.return_value = []
            return result

        db = MagicMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        db.add = MagicMock(side_effect=lambda obj: added.append(obj))

        with (
            patch.object(svc, "_map_iso_schemes", new_callable=AsyncMock) as mock_iso,
            patch.object(svc, "_map_uvdb_schemes", new_callable=AsyncMock, return_value=[]),
            patch.object(svc, "_find_documents_for_query", new_callable=AsyncMock, return_value=[]),
            patch(
                "src.domain.services.governed_knowledge_service.iso_compliance_service.multi_stage_analyze",
                new_callable=AsyncMock,
                return_value={
                    "clause_matches": [],
                    "stages": {"stage_5_conformance": {"conformance_statement": "Control of work was not evidenced."}},
                },
            ),
        ):
            from src.domain.services.governed_knowledge_service import SchemeMapping

            mock_iso.return_value = [
                SchemeMapping(
                    clause_id="45001-8.1",
                    scheme="iso45001",
                    confidence=95.0,
                    rationale="operational control",
                )
            ]
            result = await svc.assess_operational_entity(
                db,
                entity_type="incident",
                entity_id="55",
                content="Worker injured due to missing isolation procedure.",
                tenant_id=7,
                user=user,
            )

        assert result.signal_type == "nonconformity"
        assert len(result.links) == 1
        assert result.links[0].status == EvidenceLinkStatus.PROPOSED
        assert result.links[0].auto_applied is False
        assert result.links[0].signal_type == "nonconformity"
        assert result.assessment_statement is not None
        assert any(getattr(obj, "action", None) == "operational_standards_assess" for obj in added)

    def test_manual_without_status_is_confirmed(self) -> None:
        link = ComplianceEvidenceLink(
            tenant_id=1,
            entity_type="document",
            entity_id="42",
            clause_id="9001-7.5",
            linked_by=EvidenceLinkMethod.MANUAL,
        )
        assert link.effective_status == EvidenceLinkStatus.CONFIRMED

    def test_ai_without_status_is_proposed(self) -> None:
        link = ComplianceEvidenceLink(
            tenant_id=1,
            entity_type="document",
            entity_id="42",
            clause_id="9001-7.5",
            linked_by=EvidenceLinkMethod.AI,
        )
        assert link.effective_status == EvidenceLinkStatus.PROPOSED


class TestPlanetMarkMapping:
    def test_scope_keywords_map_to_clauses(self) -> None:
        svc = GovernedKnowledgeService()
        content = "Our scope 1 direct emissions from fleet fuel and scope 2 purchased electricity."
        mappings = svc._map_planet_mark_schemes(content)
        clause_ids = {m.clause_id for m in mappings}
        assert "pm:scope1" in clause_ids
        assert "pm:scope2" in clause_ids

    def test_reduction_theme_detected(self) -> None:
        svc = GovernedKnowledgeService()
        content = "We have a carbon reduction plan targeting net zero by 2030."
        mappings = svc._map_planet_mark_schemes(content)
        assert any(m.clause_id == "pm:reduction" for m in mappings)


class TestIsoMappingStub:
    @pytest.mark.asyncio
    async def test_map_iso_uses_ai_enhanced_tagging(self) -> None:
        svc = GovernedKnowledgeService()
        fake_results = [
            {
                "clause_id": "9001-7.2",
                "standard": "iso9001",
                "confidence": 88.0,
                "title": "Competence",
                "evidence_snippet": (
                    "Staff competence and training programme records demonstrate "
                    "role-based competence requirements under the quality management system."
                ),
            }
        ]
        with patch(
            "src.domain.services.governed_knowledge_service.iso_compliance_service.ai_enhanced_tagging",
            new_callable=AsyncMock,
            return_value=fake_results,
        ):
            mappings = await svc._map_iso_schemes("Staff competence and training programme.")
        assert len(mappings) == 1
        assert mappings[0].clause_id == "9001-7.2"
        assert mappings[0].scheme == "iso9001"
        assert mappings[0].confidence == 88.0


class TestMapDocumentToSchemes:
    @pytest.mark.asyncio
    async def test_persists_links_with_ai_decision_log(self) -> None:
        svc = GovernedKnowledgeService()
        user = MagicMock(id=5, email="ai@example.com")

        added: list = []

        async def fake_execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        db = MagicMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        db.add = MagicMock(side_effect=lambda obj: added.append(obj))

        with (
            patch.object(svc, "_map_iso_schemes", new_callable=AsyncMock) as mock_iso,
            patch.object(svc, "_map_uvdb_schemes", new_callable=AsyncMock, return_value=[]),
            patch.object(svc, "_map_planet_mark_schemes", return_value=[]),
        ):
            from src.domain.services.governed_knowledge_service import SchemeMapping

            mock_iso.return_value = [
                SchemeMapping(
                    clause_id="9001-9.2",
                    scheme="iso9001",
                    confidence=90.0,
                    rationale="audit programme",
                )
            ]
            links = await svc.map_document_to_schemes(
                db,
                document_id=101,
                content="Internal audit programme for QMS.",
                doc_type="procedure",
                tenant_id=7,
                user=user,
            )

        assert len(links) == 1
        assert links[0].clause_id == "9001-9.2"
        assert links[0].status == EvidenceLinkStatus.CONFIRMED
        assert links[0].auto_applied is True
        assert links[0].linked_by == EvidenceLinkMethod.AI
        assert any(isinstance(obj, ComplianceEvidenceLink) for obj in added)
        assert any(getattr(obj, "action", None) == "evidence_map" for obj in added)

    @pytest.mark.asyncio
    async def test_strict_doc_type_forces_proposed(self) -> None:
        svc = GovernedKnowledgeService()
        user = MagicMock(id=5, email="ai@example.com")
        added: list = []

        async def fake_execute(stmt):
            result = MagicMock()
            result.scalar_one_or_none.return_value = None
            return result

        db = MagicMock()
        db.execute = AsyncMock(side_effect=fake_execute)
        db.add = MagicMock(side_effect=lambda obj: added.append(obj))

        with (
            patch.object(svc, "_map_iso_schemes", new_callable=AsyncMock) as mock_iso,
            patch.object(svc, "_map_uvdb_schemes", new_callable=AsyncMock, return_value=[]),
            patch.object(svc, "_map_planet_mark_schemes", return_value=[]),
        ):
            from src.domain.services.governed_knowledge_service import SchemeMapping

            mock_iso.return_value = [
                SchemeMapping(
                    clause_id="45001-8.1",
                    scheme="iso45001",
                    confidence=95.0,
                    rationale="hazard control",
                )
            ]
            links = await svc.map_document_to_schemes(
                db,
                document_id=102,
                content="Risk assessment for site works.",
                doc_type="rams",
                tenant_id=7,
                user=user,
            )

        assert links[0].status == EvidenceLinkStatus.PROPOSED
        assert links[0].auto_applied is False


class TestAutoConfirmThresholdConstant:
    def test_threshold_is_085(self) -> None:
        assert AUTO_CONFIRM_THRESHOLD == 0.85
