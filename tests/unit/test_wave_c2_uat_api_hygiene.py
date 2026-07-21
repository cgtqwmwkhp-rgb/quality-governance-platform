"""Wave C2 UAT API hygiene — NM validation, campaign list, evidence PDF bytes."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pydantic import ValidationError

from src.api.routes.near_miss import router as near_miss_router
from src.api.schemas.near_miss import NearMissCreate, NearMissUpdate
from src.core.pagination import PaginatedResponse
from src.domain.models.document_campaign import CampaignStatus
from src.domain.services.document_campaign_service import DocumentCampaignService


def _valid_near_miss_payload(**overrides: object) -> dict:
    payload = {
        "reporter_name": "Alex Engineer",
        "contract": "Main",
        "location": "Yard A",
        "event_date": datetime(2026, 1, 15, 10, 0, tzinfo=timezone.utc),
        "description": "Near miss while unloading pallets safely.",
    }
    payload.update(overrides)
    return payload


def test_near_miss_create_rejects_future_event_date():
    with pytest.raises(ValidationError, match="Date must not be in the future"):
        NearMissCreate(**_valid_near_miss_payload(event_date=datetime(2099, 1, 1, tzinfo=timezone.utc)))


def test_near_miss_update_rejects_invalid_potential_severity():
    with pytest.raises(ValidationError):
        NearMissUpdate(potential_severity="extreme")


def test_near_miss_update_rejects_empty_body():
    with pytest.raises(ValidationError, match="At least one field"):
        NearMissUpdate()


def test_near_miss_dual_mount_without_trailing_slash():
    list_paths = {
        getattr(r, "path", None) for r in near_miss_router.routes if "GET" in (getattr(r, "methods", None) or set())
    }
    assert "" in list_paths
    assert "/" in list_paths


@pytest.mark.asyncio
async def test_list_campaigns_global_without_document_id(monkeypatch):
    campaign = SimpleNamespace(
        id=1,
        document_id=3,
        quiz_draft_id=None,
        title="Read",
        status=CampaignStatus.DRAFT,
        due_within_days=7,
        require_quiz=False,
        require_sign=False,
        competence_asset_type_id=None,
        reminder_offsets_hours=[],
        created_at=datetime.now(timezone.utc),
        launched_at=None,
        closed_at=None,
    )
    mock_service = SimpleNamespace(
        list_campaigns=AsyncMock(return_value=([campaign], 1)),
    )
    monkeypatch.setattr(
        "src.api.routes.document_campaign.DocumentCampaignService",
        lambda _db: mock_service,
    )

    from src.api.routes import document_campaign as routes

    response = await routes.list_campaigns(
        db=SimpleNamespace(),
        current_user=SimpleNamespace(tenant_id=1),
        document_id=None,
        page=1,
        page_size=10,
    )
    assert response.total == 1
    assert len(response.items) == 1
    mock_service.list_campaigns.assert_awaited_once_with(tenant_id=1, document_id=None, page=1, page_size=10)


@pytest.mark.asyncio
async def test_evidence_pack_pdf_empty_roster_returns_bytes():
    campaign = SimpleNamespace(
        id=9,
        tenant_id=1,
        document_id=3,
        title="Annual read",
        status=CampaignStatus.ACTIVE,
    )
    db = SimpleNamespace(execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [])))
    service = DocumentCampaignService(db)
    service.get_campaign = AsyncMock(return_value=campaign)
    service._document_title = AsyncMock(return_value="Safety Policy")

    pdf_bytes, filename = await service.build_evidence_pack_pdf(tenant_id=1, campaign_id=9)

    assert filename == "campaign-9-evidence-pack.pdf"
    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF")


@pytest.mark.asyncio
async def test_document_campaign_service_list_campaigns_paginates(monkeypatch):
    campaign = SimpleNamespace(id=5)
    monkeypatch.setattr(
        "src.domain.services.document_campaign_service.paginate",
        AsyncMock(
            return_value=PaginatedResponse(items=[campaign], total=1, page=1, page_size=10, pages=1),
        ),
    )
    db = SimpleNamespace()
    service = DocumentCampaignService(db)
    items, total = await service.list_campaigns(tenant_id=1, page=1, page_size=10)
    assert items == [campaign]
    assert total == 1
