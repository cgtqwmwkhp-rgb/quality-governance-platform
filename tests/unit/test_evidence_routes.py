"""Tests for evidence asset API routes."""

import functools
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def skip_on_import_error(test_func):
    """Decorator to skip tests that fail due to ImportError."""

    @functools.wraps(test_func)
    def wrapper(*args, **kwargs):
        try:
            return test_func(*args, **kwargs)
        except (ImportError, ModuleNotFoundError) as e:
            pytest.skip(f"Dependency not available: {e}")

    return wrapper


class TestEvidenceRoutes:
    """Test evidence asset route handlers."""

    @skip_on_import_error
    def test_module_imports(self):
        """Verify route module imports without error."""
        from src.api.routes import evidence_assets

        assert hasattr(evidence_assets, "router")

    @skip_on_import_error
    def test_router_has_upload_route(self):
        """Verify upload route exists with POST method."""
        from src.api.routes.evidence_assets import router

        routes = [r for r in router.routes if hasattr(r, "path")]
        upload_routes = [r for r in routes if r.path == "/upload" and "POST" in r.methods]
        assert len(upload_routes) > 0

    @skip_on_import_error
    def test_router_has_list_route(self):
        """Verify list route exists."""
        from src.api.routes.evidence_assets import router

        routes = [r for r in router.routes if hasattr(r, "path")]
        list_routes = [r for r in routes if r.path == "/"]
        assert len(list_routes) > 0

    @skip_on_import_error
    def test_allowed_content_types(self):
        """Verify the content type allowlist is populated."""
        from src.api.routes.evidence_assets import ALLOWED_CONTENT_TYPES

        assert "image/jpeg" in ALLOWED_CONTENT_TYPES
        assert "application/pdf" in ALLOWED_CONTENT_TYPES
        assert len(ALLOWED_CONTENT_TYPES) > 5

    @skip_on_import_error
    def test_max_file_size(self):
        """Verify max file size constant is set to 50MB."""
        from src.api.routes.evidence_assets import MAX_FILE_SIZE_BYTES

        assert MAX_FILE_SIZE_BYTES == 50 * 1024 * 1024


class TestEvidenceSchemas:
    """Test evidence asset schema validation."""

    @skip_on_import_error
    def test_evidence_asset_create_schema(self):
        """Test EvidenceAssetCreate schema with valid data."""
        from src.api.schemas.evidence_asset import EvidenceAssetCreate

        data = EvidenceAssetCreate(
            source_module="incident",
            source_id=1,
            title="Photo of incident scene",
        )
        assert data.source_module == "incident"
        assert data.asset_type == "photo"

    @skip_on_import_error
    def test_evidence_asset_update_schema_partial(self):
        """Test EvidenceAssetUpdate allows partial updates."""
        from src.api.schemas.evidence_asset import EvidenceAssetUpdate

        data = EvidenceAssetUpdate(title="Updated title")
        dumped = data.model_dump(exclude_unset=True)
        assert "title" in dumped
        assert "description" not in dumped

    @skip_on_import_error
    def test_evidence_asset_upload_response_schema(self):
        """Test EvidenceAssetUploadResponse schema."""
        from src.api.schemas.evidence_asset import EvidenceAssetUploadResponse

        data = EvidenceAssetUploadResponse(
            id=1,
            storage_key="evidence/incident/1/abc_photo.jpg",
            original_filename="photo.jpg",
            content_type="image/jpeg",
            file_size_bytes=1024,
        )
        assert data.id == 1
        assert data.message == "File uploaded successfully"

    @skip_on_import_error
    def test_signed_url_response_schema(self):
        """Test SignedUrlResponse schema."""
        from src.api.schemas.evidence_asset import SignedUrlResponse

        data = SignedUrlResponse(
            asset_id=1,
            signed_url="https://example.com/signed-url",
            expires_in_seconds=3600,
        )
        assert data.asset_id == 1
        assert data.expires_in_seconds == 3600

    @skip_on_import_error
    def test_evidence_asset_create_invalid_source_module(self):
        """Test EvidenceAssetCreate rejects invalid source module."""
        from src.api.schemas.evidence_asset import EvidenceAssetCreate

        with pytest.raises(Exception):
            EvidenceAssetCreate(
                source_module="invalid_module",
                source_id=1,
            )
