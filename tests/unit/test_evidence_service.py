"""Tests for src.domain.services.evidence_service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.evidence_service import ALLOWED_CONTENT_TYPES, MAX_FILE_SIZE_BYTES, EvidenceService

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------


class TestConstants:
    def test_allowed_content_types_has_common_types(self):
        assert "image/jpeg" in ALLOWED_CONTENT_TYPES
        assert "image/png" in ALLOWED_CONTENT_TYPES
        assert "application/pdf" in ALLOWED_CONTENT_TYPES
        assert "video/mp4" in ALLOWED_CONTENT_TYPES

    def test_max_file_size(self):
        assert MAX_FILE_SIZE_BYTES == 50 * 1024 * 1024

    def test_photo_types_map_correctly(self):
        assert ALLOWED_CONTENT_TYPES["image/jpeg"] == "photo"
        assert ALLOWED_CONTENT_TYPES["image/png"] == "photo"

    def test_video_types_map_correctly(self):
        assert ALLOWED_CONTENT_TYPES["video/mp4"] == "video"

    def test_document_types_map_correctly(self):
        assert ALLOWED_CONTENT_TYPES["application/pdf"] == "pdf"


# ---------------------------------------------------------------------------
# EvidenceService
# ---------------------------------------------------------------------------


class TestEvidenceService:
    @pytest.fixture
    def service(self):
        return EvidenceService(AsyncMock())

    # --- upload validation ---

    @pytest.mark.asyncio
    async def test_upload_invalid_source_module(self, service):
        with pytest.raises(ValueError, match="Invalid source module"):
            await service.upload(
                file_content=b"data",
                filename="test.jpg",
                content_type="image/jpeg",
                source_module="invalid_module",
                source_id=1,
                user_id=1,
                tenant_id=1,
            )

    @pytest.mark.asyncio
    @patch.object(EvidenceService, "validate_source_exists", new_callable=AsyncMock, return_value=True)
    async def test_upload_invalid_content_type(self, _validate, service):
        with pytest.raises(ValueError, match="not allowed"):
            await service.upload(
                file_content=b"data",
                filename="test.exe",
                content_type="application/x-executable",
                source_module="incident",
                source_id=1,
                user_id=1,
                tenant_id=1,
            )

    @pytest.mark.asyncio
    @patch.object(EvidenceService, "validate_source_exists", new_callable=AsyncMock, return_value=True)
    async def test_upload_file_too_large(self, _validate, service):
        big_content = b"x" * (MAX_FILE_SIZE_BYTES + 1)
        with pytest.raises(ValueError, match="exceeds maximum"):
            await service.upload(
                file_content=big_content,
                filename="huge.pdf",
                content_type="application/pdf",
                source_module="incident",
                source_id=1,
                user_id=1,
                tenant_id=1,
            )

    @pytest.mark.asyncio
    @patch.object(EvidenceService, "validate_source_exists", new_callable=AsyncMock, return_value=True)
    async def test_upload_invalid_asset_type(self, _validate, service):
        with pytest.raises(ValueError, match="Invalid asset type"):
            await service.upload(
                file_content=b"data",
                filename="test.jpg",
                content_type="image/jpeg",
                source_module="incident",
                source_id=1,
                user_id=1,
                tenant_id=1,
                asset_type="hologram",
            )

    # --- get_asset ---

    @pytest.mark.asyncio
    async def test_get_asset_not_found(self, service):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        service.db.execute.return_value = result

        with pytest.raises(LookupError, match="not found"):
            await service.get_asset(999)

    @pytest.mark.asyncio
    async def test_get_asset_found(self, service):
        asset = MagicMock(id=1)
        result = MagicMock()
        result.scalar_one_or_none.return_value = asset
        service.db.execute.return_value = result

        found = await service.get_asset(1)
        assert found is asset

    # --- delete_asset ---

    @pytest.mark.asyncio
    @patch("src.domain.services.evidence_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.evidence_service.track_metric")
    async def test_delete_asset_sets_deleted_at(self, _metric, _cache, service):
        asset = MagicMock(id=1, deleted_at=None)
        service.get_asset = AsyncMock(return_value=asset)

        await service.delete_asset(1, user_id=1, tenant_id=1)
        assert asset.deleted_at is not None
        assert asset.deleted_by_id == 1

    @pytest.mark.asyncio
    async def test_delete_asset_not_found(self, service):
        service.get_asset = AsyncMock(side_effect=LookupError("not found"))

        with pytest.raises(LookupError):
            await service.delete_asset(999, user_id=1, tenant_id=1)

    # --- link_to_investigation ---

    @pytest.mark.asyncio
    async def test_link_to_investigation_asset_not_found(self, service):
        service.get_asset = AsyncMock(side_effect=LookupError("not found"))

        with pytest.raises(LookupError):
            await service.link_to_investigation(999, 1, user_id=1, tenant_id=1)

    @pytest.mark.asyncio
    async def test_link_to_investigation_investigation_not_found(self, service):
        asset = MagicMock(id=1)
        service.get_asset = AsyncMock(return_value=asset)

        inv_result = MagicMock()
        inv_result.scalar_one_or_none.return_value = None
        service.db.execute.return_value = inv_result

        with pytest.raises(LookupError, match="Investigation"):
            await service.link_to_investigation(1, 999, user_id=1, tenant_id=1)

    # --- get_signed_url ---

    @pytest.mark.asyncio
    async def test_get_signed_url_asset_not_found(self, service):
        service.get_asset = AsyncMock(side_effect=LookupError("not found"))

        with pytest.raises(LookupError):
            await service.get_signed_url(999)

    @pytest.mark.asyncio
    async def test_get_signed_url_returns_dict(self, service):
        asset = MagicMock(
            id=1,
            storage_key="evidence/incident/1/uuid_file.jpg",
            original_filename="photo.jpg",
            content_type="image/jpeg",
        )
        service.get_asset = AsyncMock(return_value=asset)

        with patch("src.infrastructure.storage.storage_service") as mock_storage:
            mock_storage.return_value.get_signed_url.return_value = "https://signed.url/file"
            result = await service.get_signed_url(1, expires_in=600)

        assert result["asset_id"] == 1
        assert result["signed_url"] == "https://signed.url/file"
        assert result["expires_in_seconds"] == 600
        assert result["content_type"] == "image/jpeg"


# ---------------------------------------------------------------------------
# validate_source_exists
# ---------------------------------------------------------------------------


class TestValidateSourceExists:
    @pytest.fixture
    def service(self):
        return EvidenceService(AsyncMock())

    @pytest.mark.asyncio
    async def test_action_module_always_valid(self, service):
        result = await service.validate_source_exists("action", 1)
        assert result is True

    @pytest.mark.asyncio
    async def test_invalid_module_path_returns_true(self, service):
        result = await service.validate_source_exists("action", 42)
        assert result is True
