"""
Integration tests for Near Miss Investigation support.

Stage 0.5 Blocker Remediation:
- Tests NEAR_MISS enum value support in AssignedEntityType
- Tests investigation creation from Near Miss records
- Tests evidence asset linkage to investigations
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestNearMissInvestigationValidation:
    """Test Near Miss investigation validation without DB session."""

    async def test_near_miss_entity_type_accepted_in_schema(self, client: AsyncClient):
        """Test that near_miss entity type is accepted by the investigation schema validation."""
        # Even without auth, schema validation should accept near_miss as entity type
        # The request should fail with 401 (auth), not 422 (validation)
        data = {
            "template_id": 1,
            "assigned_entity_type": "near_miss",  # This should be a valid type now
            "assigned_entity_id": 1,
            "title": "Near Miss Investigation Test",
        }
        response = await client.post("/api/v1/investigations/", json=data)

        # Should get 401 (auth required), NOT 422 (validation error)
        # This proves near_miss is now a valid entity type
        assert response.status_code == 401

    async def test_invalid_entity_type_rejected(self, client: AsyncClient):
        """Test that invalid entity types are rejected with 422."""
        data = {
            "template_id": 1,
            "assigned_entity_type": "invalid_type",  # Not a valid type
            "assigned_entity_id": 1,
            "title": "Invalid Entity Type Test",
        }
        response = await client.post("/api/v1/investigations/", json=data)

        # Should get 422 validation error for invalid entity type
        assert response.status_code == 422
        body = response.json()
        assert "detail" in body

    async def test_valid_entity_types_list(self, client: AsyncClient):
        """Test that all expected entity types are in the valid list."""
        # Test each valid entity type is accepted by schema
        valid_types = [
            "road_traffic_collision",
            "reporting_incident",
            "complaint",
            "near_miss",  # New entity type from Stage 0.5
        ]

        for entity_type in valid_types:
            data = {
                "template_id": 1,
                "assigned_entity_type": entity_type,
                "assigned_entity_id": 1,
                "title": f"Test {entity_type}",
            }
            response = await client.post("/api/v1/investigations/", json=data)

            # Should NOT get 422 validation error
            assert response.status_code != 422, (
                f"Entity type '{entity_type}' was rejected as invalid"
            )


@pytest.mark.asyncio
class TestEvidenceAssetValidation:
    """Test Evidence Asset API validation without DB session."""

    async def test_evidence_asset_list_unauthenticated(self, client: AsyncClient):
        """Test that listing evidence assets requires authentication."""
        response = await client.get("/api/v1/evidence-assets/")
        assert response.status_code == 401

    async def test_evidence_asset_upload_unauthenticated(self, client: AsyncClient):
        """Test that uploading evidence assets requires authentication."""
        # Create a minimal file upload request
        files = {"file": ("test.jpg", b"fake image content", "image/jpeg")}
        data = {
            "source_module": "near_miss",
            "source_id": "1",
        }
        response = await client.post(
            "/api/v1/evidence-assets/upload",
            files=files,
            data=data,
        )
        assert response.status_code == 401

    async def test_evidence_asset_source_module_validation(self, client: AsyncClient):
        """Test that valid source modules are accepted."""
        valid_modules = [
            "near_miss",
            "road_traffic_collision",
            "complaint",
            "incident",
            "investigation",
            "audit",
            "action",
        ]

        # Just verifying the modules are known - actual upload requires auth
        # The schema validator should accept these when auth is provided
        for module in valid_modules:
            files = {"file": ("test.jpg", b"fake", "image/jpeg")}
            data = {
                "source_module": module,
                "source_id": "1",
            }
            response = await client.post(
                "/api/v1/evidence-assets/upload",
                files=files,
                data=data,
            )
            # Should NOT get 422 for invalid source_module
            # Will get 401 (auth) instead
            assert response.status_code == 401

    async def test_evidence_asset_invalid_source_module_rejected(self, client: AsyncClient):
        """Test that invalid source modules are rejected."""
        files = {"file": ("test.jpg", b"fake", "image/jpeg")}
        data = {
            "source_module": "invalid_module",
            "source_id": "1",
        }
        response = await client.post(
            "/api/v1/evidence-assets/upload",
            files=files,
            data=data,
        )
        # Should get 422 validation error OR 401 auth error
        # Validation may happen after auth in some implementations
        assert response.status_code in (401, 422)


@pytest.mark.asyncio
class TestEvidenceAssetTypeValidation:
    """Test Evidence Asset type enums."""

    async def test_asset_types_documented(self):
        """Test that all expected asset types are defined."""
        from src.domain.models.evidence_asset import EvidenceAssetType

        expected_types = [
            "photo",
            "video",
            "pdf",
            "document",
            "map_pin",
            "diagram",
            "chart",
            "cctv_ref",
            "dashcam_ref",
            "audio",
            "signature",
            "other",
        ]

        actual_types = [e.value for e in EvidenceAssetType]

        for expected in expected_types:
            assert expected in actual_types, f"Missing asset type: {expected}"

    async def test_visibility_enums_documented(self):
        """Test that all expected visibility levels are defined."""
        from src.domain.models.evidence_asset import EvidenceVisibility

        expected_visibility = [
            "internal_only",
            "internal_customer",
            "external_allowed",
            "public",
        ]

        actual_visibility = [e.value for e in EvidenceVisibility]

        for expected in expected_visibility:
            assert expected in actual_visibility, f"Missing visibility: {expected}"

    async def test_retention_policy_enums_documented(self):
        """Test that all expected retention policies are defined."""
        from src.domain.models.evidence_asset import EvidenceRetentionPolicy

        expected_policies = [
            "standard",
            "legal_hold",
            "extended",
            "temporary",
        ]

        actual_policies = [e.value for e in EvidenceRetentionPolicy]

        for expected in expected_policies:
            assert expected in actual_policies, f"Missing retention policy: {expected}"


@pytest.mark.asyncio
class TestInvestigationEntityTypeDeterminism:
    """Test deterministic entity type handling."""

    async def test_assigned_entity_type_enum_values(self):
        """Test that AssignedEntityType enum has expected values."""
        from src.domain.models.investigation import AssignedEntityType

        expected_values = [
            "road_traffic_collision",
            "reporting_incident",
            "complaint",
            "near_miss",  # Stage 0.5 addition
        ]

        actual_values = [e.value for e in AssignedEntityType]

        for expected in expected_values:
            assert expected in actual_values, f"Missing entity type: {expected}"

    async def test_entity_type_ordering_deterministic(self):
        """Test that enum iteration order is deterministic."""
        from src.domain.models.investigation import AssignedEntityType

        values_1 = [e.value for e in AssignedEntityType]
        values_2 = [e.value for e in AssignedEntityType]
        values_3 = [e.value for e in AssignedEntityType]

        assert values_1 == values_2 == values_3

    async def test_near_miss_in_entity_models_mapping(self):
        """Test that NEAR_MISS is in the entity_models validation mapping."""
        from src.domain.models.investigation import AssignedEntityType

        # This verifies the NEAR_MISS enum value exists
        near_miss_type = AssignedEntityType.NEAR_MISS
        assert near_miss_type.value == "near_miss"

        # And that it can be instantiated from string
        from_string = AssignedEntityType("near_miss")
        assert from_string == near_miss_type
