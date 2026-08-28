"""``GET /api/v1/evidence-assets/{asset_id}/content`` over real HTTP.

The handler-level cases live in ``tests/unit/test_evidence_content_endpoint.py``.
What can only be shown here is that the route is actually mounted, that it
refuses an unauthenticated caller, and that a real row in another tenant is
answered the same way as a row that does not exist.

Storage is faked. The point of these tests is who may read the bytes, not
whether Azure returns them.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from src.domain.models.evidence_asset import (
    EvidenceAsset,
    EvidenceAssetType,
    EvidenceRetentionPolicy,
    EvidenceSourceModule,
    EvidenceVisibility,
)
from src.domain.models.tenant import Tenant
from src.infrastructure.database import async_session_maker

CALLER_TENANT = 1
OTHER_TENANT_SLUG = "evidence-content-cross-tenant-control"
PNG_BYTES = b"\x89PNG\r\n\x1a\n fake image payload"


async def _other_tenant_id() -> int:
    """Get-or-create the second tenant rather than assuming an id.

    ``tenants`` is only truncated between tests on SQLite; on PostgreSQL a
    hardcoded id would collide with rows left by earlier tests or violate the FK.
    """
    async with async_session_maker() as session:
        existing = (await session.execute(select(Tenant).where(Tenant.slug == OTHER_TENANT_SLUG))).scalar_one_or_none()
        if existing is not None:
            return existing.id
        tenant = Tenant(
            name="Evidence content control",
            slug=OTHER_TENANT_SLUG,
            admin_email=f"{OTHER_TENANT_SLUG}@test.example.com",
        )
        session.add(tenant)
        await session.commit()
        await session.refresh(tenant)
        return tenant.id


async def _seed_asset(*, tenant_id: int, deleted: bool = False, filename: str = "scene.png") -> int:
    async with async_session_maker() as session:
        asset = EvidenceAsset(
            storage_key=f"evidence/incident/1/{uuid.uuid4()}_{filename}",
            original_filename=filename,
            content_type="image/png",
            file_size_bytes=len(PNG_BYTES),
            asset_type=EvidenceAssetType.PHOTO,
            source_module=EvidenceSourceModule.INCIDENT,
            source_id="1",
            visibility=EvidenceVisibility.INTERNAL_CUSTOMER,
            retention_policy=EvidenceRetentionPolicy.STANDARD,
            tenant_id=tenant_id,
            deleted_at=datetime.now(timezone.utc) if deleted else None,
        )
        session.add(asset)
        await session.commit()
        await session.refresh(asset)
        return asset.id


@pytest.fixture
def fake_storage(monkeypatch):
    """Serve fixed bytes for any storage key, and record what was asked for."""
    reads: list[str] = []

    async def download(storage_key: str) -> bytes:
        reads.append(storage_key)
        return PNG_BYTES

    monkeypatch.setattr(
        "src.infrastructure.storage.storage_service",
        lambda: SimpleNamespace(download=download),
    )
    return reads


@pytest.mark.asyncio
async def test_unauthenticated_caller_is_refused(client: AsyncClient, fake_storage):
    asset_id = await _seed_asset(tenant_id=CALLER_TENANT)

    response = await client.get(f"/api/v1/evidence-assets/{asset_id}/content")

    assert response.status_code == 401, response.text
    assert fake_storage == [], "storage must not be read for an unauthenticated request"


@pytest.mark.asyncio
async def test_owning_tenant_gets_the_bytes_inline(admin_client: AsyncClient, fake_storage):
    asset_id = await _seed_asset(tenant_id=CALLER_TENANT)

    response = await admin_client.get(f"/api/v1/evidence-assets/{asset_id}/content")

    assert response.status_code == 200, response.text
    assert response.content == PNG_BYTES
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-disposition"] == 'inline; filename="scene.png"'
    assert len(fake_storage) == 1


@pytest.mark.asyncio
async def test_evidence_bytes_are_not_cacheable(admin_client: AsyncClient, fake_storage):
    """Evidence is tenant data and may carry PII, so nothing may store a copy.

    The directive comes from ``SecurityHeadersMiddleware`` rather than the handler.
    It is asserted here because a byte-serving endpoint is the one place where a
    cached response would leave tenant data on disk, and because the effective
    header is the only one that matters.
    """
    asset_id = await _seed_asset(tenant_id=CALLER_TENANT)

    response = await admin_client.get(f"/api/v1/evidence-assets/{asset_id}/content")

    assert "no-store" in response.headers["cache-control"]
    assert response.headers["x-content-type-options"] == "nosniff"


@pytest.mark.asyncio
async def test_attachment_can_still_be_requested(admin_client: AsyncClient, fake_storage):
    asset_id = await _seed_asset(tenant_id=CALLER_TENANT)

    response = await admin_client.get(f"/api/v1/evidence-assets/{asset_id}/content?disposition=attachment")

    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"] == 'attachment; filename="scene.png"'


@pytest.mark.asyncio
async def test_another_tenants_asset_is_a_404_and_is_never_read(admin_client: AsyncClient, fake_storage):
    """Indistinguishable from a missing id, and the blob is not touched."""
    asset_id = await _seed_asset(tenant_id=await _other_tenant_id())

    response = await admin_client.get(f"/api/v1/evidence-assets/{asset_id}/content")

    assert response.status_code == 404, response.text
    assert fake_storage == []


@pytest.mark.asyncio
async def test_soft_deleted_asset_is_a_404(admin_client: AsyncClient, fake_storage):
    asset_id = await _seed_asset(tenant_id=CALLER_TENANT, deleted=True)

    response = await admin_client.get(f"/api/v1/evidence-assets/{asset_id}/content")

    assert response.status_code == 404, response.text
    assert fake_storage == []


@pytest.mark.asyncio
async def test_unknown_asset_id_is_a_404(admin_client: AsyncClient, fake_storage):
    response = await admin_client.get("/api/v1/evidence-assets/99999999/content")

    assert response.status_code == 404, response.text


@pytest.mark.asyncio
async def test_the_content_route_does_not_shadow_the_by_id_route(admin_client: AsyncClient, fake_storage):
    """Two segments cannot be swallowed by ``GET /{asset_id}``, and vice versa."""
    asset_id = await _seed_asset(tenant_id=CALLER_TENANT)

    metadata = await admin_client.get(f"/api/v1/evidence-assets/{asset_id}")

    assert metadata.status_code == 200, metadata.text
    assert metadata.json()["id"] == asset_id
    assert fake_storage == [], "the metadata route must not read bytes"
