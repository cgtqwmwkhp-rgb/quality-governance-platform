"""Doc Graph P0: CEL version pin + standard_edition + campaign version pins."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.models.compliance_evidence import ComplianceEvidenceLink
from src.domain.models.document_campaign import CampaignAssignment, DocumentCampaign
from src.domain.services.cel_version_pin import parse_document_entity_id, pin_evidence_link_document_version
from src.domain.services.document_campaign_service import DocumentCampaignService

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20261014_doc_graph_version_pins.py"
REVISION = "20261014_doc_graph_pins"


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_revision_id_within_32_chars():
    body = MIGRATION_PATH.read_text(encoding="utf-8")
    assert f'revision: str = "{REVISION}"' in body
    assert len(REVISION) <= 32


def test_migration_chains_from_rls_sso_head_not_20261013():
    """Avoid colliding with sibling 20261013_cs_reg_link / 20261013_cs_fra_ocr heads."""
    body = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'down_revision: Union[str, Sequence[str], None] = "20261012_rls_sso_prov"' in body
    assert f'revision: str = "{REVISION}"' in body
    assert 'revision: str = "20261013' not in body
    assert "document_version_id" in body
    assert "standard_edition" in body
    assert "acknowledged_version_id" in body
    assert "fk_cel_document_version_id" in body
    assert '"document_versions"' in body or "'document_versions'" in body


def test_cel_model_exposes_version_pin_and_edition():
    assert ComplianceEvidenceLink.__tablename__ == "compliance_evidence_links"
    assert "document_version_id" in ComplianceEvidenceLink.__table__.c
    assert "standard_edition" in ComplianceEvidenceLink.__table__.c
    assert ComplianceEvidenceLink.__table__.c.document_version_id.nullable is True
    assert ComplianceEvidenceLink.__table__.c.standard_edition.nullable is True


def test_campaign_models_expose_version_pins():
    assert "document_version_id" in DocumentCampaign.__table__.c
    assert "acknowledged_version_id" in CampaignAssignment.__table__.c
    assert DocumentCampaign.__table__.c.document_version_id.nullable is True
    assert CampaignAssignment.__table__.c.acknowledged_version_id.nullable is True


def test_parse_document_entity_id():
    assert parse_document_entity_id("42") == 42
    assert parse_document_entity_id(7) == 7
    assert parse_document_entity_id("not-an-id") is None
    assert parse_document_entity_id(None) is None


@pytest.mark.asyncio
async def test_pin_evidence_link_sets_tip_version_for_document_entity(monkeypatch):
    link = SimpleNamespace(entity_type="document", entity_id="99", document_version_id=None)
    tip = SimpleNamespace(id=555)

    async def fake_resolve(_db, *, document_id, tenant_id):
        assert document_id == 99
        assert tenant_id == 7
        return tip

    monkeypatch.setattr(
        "src.domain.services.document_version_service.document_version_service.resolve_tip_library_version",
        fake_resolve,
    )

    pinned = await pin_evidence_link_document_version(
        SimpleNamespace(),
        link,
        tenant_id=7,
    )
    assert pinned == 555
    assert link.document_version_id == 555


@pytest.mark.asyncio
async def test_pin_evidence_link_skips_non_document_entity(monkeypatch):
    link = SimpleNamespace(entity_type="audit_finding", entity_id="99", document_version_id=None)
    resolve = AsyncMock()
    monkeypatch.setattr(
        "src.domain.services.document_version_service.document_version_service.resolve_tip_library_version",
        resolve,
    )
    pinned = await pin_evidence_link_document_version(SimpleNamespace(), link, tenant_id=7)
    assert pinned is None
    resolve.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_campaign_pins_tip_document_version():
    db = SimpleNamespace(add=MagicMock(), commit=AsyncMock(), refresh=AsyncMock())
    service = DocumentCampaignService(db)
    service._mint_campaign_reference = AsyncMock(return_value="CAM-2026-0009")
    service._resolve_tip_document_version_id = AsyncMock(return_value=321)

    campaign = await service.create_campaign(
        tenant_id=1,
        created_by_id=7,
        document_id=99,
        audience={"user_ids": [1]},
    )

    assert campaign.document_version_id == 321
    service._resolve_tip_document_version_id.assert_awaited_once_with(tenant_id=1, document_id=99)


@pytest.mark.asyncio
async def test_complete_assignment_sets_acknowledged_version_from_campaign_pin(monkeypatch):
    from src.domain.models.document_campaign import AssignmentStatus

    assignment = SimpleNamespace(
        id=1,
        user_id=7,
        tenant_id=1,
        campaign_id=1,
        quiz_passed=None,
        status=AssignmentStatus.PENDING,
        completed_at=None,
        acknowledged_version_id=None,
        acceptance_statement=None,
        signature_data=None,
        signature_disposition=None,
        ip_address=None,
        user_agent=None,
    )
    campaign = SimpleNamespace(
        id=1,
        tenant_id=1,
        require_quiz=False,
        document_id=99,
        document_version_id=777,
        competence_asset_type_id=None,
    )
    db = SimpleNamespace(commit=AsyncMock(), refresh=AsyncMock())
    service = DocumentCampaignService(db)
    service._get_own_assignment = AsyncMock(return_value=assignment)
    service.get_campaign = AsyncMock(return_value=campaign)
    service._has_open_assignee_question = AsyncMock(return_value=False)
    service._enforce_complete_competence_gate_if_enabled = AsyncMock()
    service._resolve_tip_document_version_id = AsyncMock(return_value=999)

    monkeypatch.setattr(
        "src.domain.services.document_campaign_service.settings",
        SimpleNamespace(
            campaign_complete_competence_gate_enabled=False,
            campaign_complete_competence_gate_feature_flag="campaign_complete_competence_gate",
        ),
    )

    result = await service.complete_assignment(
        user_id=7,
        assignment_id=1,
        acceptance_statement="I have read and understood this document.",
        signature_data="data:image/png;base64,abc",
    )

    assert result.status == AssignmentStatus.COMPLETED
    assert assignment.acknowledged_version_id == 777
    service._resolve_tip_document_version_id.assert_not_awaited()
