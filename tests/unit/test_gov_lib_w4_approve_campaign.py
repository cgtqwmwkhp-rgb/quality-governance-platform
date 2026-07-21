"""Governance Library Wave W4a — HSEQ approve → DocumentCampaign offer."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.exceptions import BadRequestError
from src.domain.models.document_campaign import CampaignStatus
from src.domain.models.enums import DocumentStatus
from src.domain.services.document_library_campaign_offer_service import (
    build_campaign_offer_payload,
    campaign_offer_eligibility,
    offer_campaign_from_document,
)


def _doc(**overrides):
    base = dict(
        id=10,
        tenant_id=1,
        title="Fire Safety Policy",
        category_id=3,
        status=DocumentStatus.APPROVED,
        access_level="all_staff",
        is_statutory=False,
        pel_doc_ref="PEL-HSE-01-0001",
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_offer_eligible_for_approved_all_staff():
    eligible, reason = campaign_offer_eligibility(_doc())
    assert eligible is True
    assert reason is None


def test_offer_ineligible_when_not_filed():
    eligible, reason = campaign_offer_eligibility(_doc(category_id=None))
    assert eligible is False
    assert reason == "not_filed"


def test_offer_ineligible_when_managers_access():
    eligible, reason = campaign_offer_eligibility(_doc(access_level="managers"))
    assert eligible is False
    assert reason == "access_level_managers"


def test_offer_ineligible_when_not_approved():
    eligible, reason = campaign_offer_eligibility(_doc(status=DocumentStatus.UNDER_REVIEW))
    assert eligible is False
    assert reason == "not_approved"


def test_build_payload_includes_hseq_label_and_existing_ids():
    draft = SimpleNamespace(id=44, status=CampaignStatus.DRAFT)
    active = SimpleNamespace(id=55, status=CampaignStatus.ACTIVE)
    payload = build_campaign_offer_payload(_doc(), existing_campaigns=[draft, active])
    assert payload["eligible"] is True
    assert payload["ui_label"] == "HSEQ reading campaign"
    assert payload["suggested_title"].startswith("Read & acknowledge:")
    assert payload["existing_draft_campaign_id"] == 44
    assert payload["existing_active_campaign_id"] == 55
    assert payload["default_audience"] == {"audience_type": "all_users"}


@pytest.mark.asyncio
async def test_offer_creates_draft_via_campaign_service(monkeypatch):
    document = _doc()
    created = SimpleNamespace(id=99, status=CampaignStatus.DRAFT)

    class FakeService:
        def __init__(self, _db):
            pass

        async def list_campaigns_for_document(self, *, tenant_id, document_id):
            return []

        async def create_campaign(self, **kwargs):
            assert kwargs["audience"] == {"all_users": True}
            assert kwargs["require_sign"] is True
            assert kwargs["document_id"] == 10
            return created

        async def launch_campaign(self, **kwargs):  # pragma: no cover
            raise AssertionError("launch should not run when launch=false")

    monkeypatch.setattr(
        "src.domain.services.document_library_campaign_offer_service.DocumentCampaignService",
        FakeService,
    )
    monkeypatch.setattr(
        "src.domain.services.document_library_campaign_offer_service.user_can_read_library_document",
        lambda *_a, **_k: True,
    )

    result = await offer_campaign_from_document(
        MagicMock(),
        tenant_id=1,
        document=document,
        actor_id=7,
        actor=SimpleNamespace(id=7),
        launch=False,
    )
    assert result["offered"] is True
    assert result["campaign_id"] == 99
    assert result["status"] == "draft"
    assert result["launched"] is False


@pytest.mark.asyncio
async def test_offer_idempotent_when_draft_exists(monkeypatch):
    document = _doc()
    draft = SimpleNamespace(id=12, status=CampaignStatus.DRAFT)

    class FakeService:
        def __init__(self, _db):
            pass

        async def list_campaigns_for_document(self, *, tenant_id, document_id):
            return [draft]

        create_campaign = AsyncMock()

    monkeypatch.setattr(
        "src.domain.services.document_library_campaign_offer_service.DocumentCampaignService",
        FakeService,
    )
    monkeypatch.setattr(
        "src.domain.services.document_library_campaign_offer_service.user_can_read_library_document",
        lambda *_a, **_k: True,
    )

    result = await offer_campaign_from_document(
        MagicMock(),
        tenant_id=1,
        document=document,
        actor_id=7,
        actor=SimpleNamespace(id=7),
    )
    assert result["offered"] is False
    assert result["reason"] == "draft_already_exists"
    assert result["campaign_id"] == 12
    FakeService.create_campaign.assert_not_called()


@pytest.mark.asyncio
async def test_offer_launch_true_activates(monkeypatch):
    document = _doc()
    created = SimpleNamespace(id=77, status=CampaignStatus.DRAFT)

    class FakeService:
        def __init__(self, _db):
            pass

        async def list_campaigns_for_document(self, *, tenant_id, document_id):
            return []

        async def create_campaign(self, **kwargs):
            return created

        async def launch_campaign(self, **kwargs):
            assert kwargs["campaign_id"] == 77
            return {"assigned_count": 3, "status": "active"}

    monkeypatch.setattr(
        "src.domain.services.document_library_campaign_offer_service.DocumentCampaignService",
        FakeService,
    )
    monkeypatch.setattr(
        "src.domain.services.document_library_campaign_offer_service.user_can_read_library_document",
        lambda *_a, **_k: True,
    )

    result = await offer_campaign_from_document(
        MagicMock(),
        tenant_id=1,
        document=document,
        actor_id=7,
        actor=SimpleNamespace(id=7),
        launch=True,
    )
    assert result["offered"] is True
    assert result["launched"] is True
    assert result["assigned_count"] == 3
    assert result["status"] == "active"


@pytest.mark.asyncio
async def test_offer_denied_when_acl_blocks(monkeypatch):
    monkeypatch.setattr(
        "src.domain.services.document_library_campaign_offer_service.user_can_read_library_document",
        lambda *_a, **_k: False,
    )
    with pytest.raises(BadRequestError, match="not readable"):
        await offer_campaign_from_document(
            MagicMock(),
            tenant_id=1,
            document=_doc(access_level="restricted"),
            actor_id=7,
            actor=SimpleNamespace(id=7),
        )
