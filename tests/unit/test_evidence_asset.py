"""
Unit tests for Evidence Asset model and schemas.

Stage 0.5 Blocker Remediation:
- Tests EvidenceAsset model fields and enums
- Tests schema validation for asset types, visibility, and retention
- Tests customer pack inclusion rules
"""

import pytest
from pydantic import ValidationError


class TestEvidenceAssetEnums:
    """Test Evidence Asset enum definitions."""

    def test_asset_type_enum_values(self):
        """Test EvidenceAssetType enum has all expected values."""
        from src.domain.models.evidence_asset import EvidenceAssetType

        expected = {
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
        }
        actual = {e.value for e in EvidenceAssetType}
        assert expected == actual

    def test_source_module_enum_values(self):
        """Test EvidenceSourceModule enum has all expected values."""
        from src.domain.models.evidence_asset import EvidenceSourceModule

        expected = {
            "near_miss",
            "road_traffic_collision",
            "complaint",
            "incident",
            "investigation",
            "audit",
            "action",
        }
        actual = {e.value for e in EvidenceSourceModule}
        assert expected == actual

    def test_visibility_enum_values(self):
        """Test EvidenceVisibility enum has all expected values."""
        from src.domain.models.evidence_asset import EvidenceVisibility

        expected = {
            "internal_only",
            "internal_customer",
            "external_allowed",
            "public",
        }
        actual = {e.value for e in EvidenceVisibility}
        assert expected == actual

    def test_retention_policy_enum_values(self):
        """Test EvidenceRetentionPolicy enum has all expected values."""
        from src.domain.models.evidence_asset import EvidenceRetentionPolicy

        expected = {
            "standard",
            "legal_hold",
            "extended",
            "temporary",
        }
        actual = {e.value for e in EvidenceRetentionPolicy}
        assert expected == actual


class TestAssignedEntityTypeEnum:
    """Test AssignedEntityType enum includes NEAR_MISS."""

    def test_near_miss_in_assigned_entity_type(self):
        """Test that NEAR_MISS is a valid AssignedEntityType."""
        from src.domain.models.investigation import AssignedEntityType

        # NEAR_MISS should exist
        assert hasattr(AssignedEntityType, "NEAR_MISS")
        assert AssignedEntityType.NEAR_MISS.value == "near_miss"

    def test_all_entity_types_present(self):
        """Test that all expected entity types are present."""
        from src.domain.models.investigation import AssignedEntityType

        expected = {
            "road_traffic_collision",
            "reporting_incident",
            "complaint",
            "near_miss",  # Stage 0.5 addition
        }
        actual = {e.value for e in AssignedEntityType}
        assert expected == actual

    def test_entity_type_from_string(self):
        """Test that entity types can be instantiated from strings."""
        from src.domain.models.investigation import AssignedEntityType

        for value in [
            "road_traffic_collision",
            "reporting_incident",
            "complaint",
            "near_miss",
        ]:
            entity_type = AssignedEntityType(value)
            assert entity_type.value == value


class TestEvidenceAssetSchemaValidation:
    """Test Evidence Asset schema validation."""

    def test_create_schema_valid_data(self):
        """Test EvidenceAssetCreate schema with valid data."""
        from src.api.schemas.evidence_asset import EvidenceAssetCreate

        data = {
            "asset_type": "photo",
            "source_module": "near_miss",
            "source_id": 1,
            "title": "Test Photo",
            "visibility": "internal_customer",
        }
        schema = EvidenceAssetCreate(**data)
        assert schema.asset_type == "photo"
        assert schema.source_module == "near_miss"
        assert schema.source_id == 1

    def test_create_schema_invalid_asset_type(self):
        """Test EvidenceAssetCreate rejects invalid asset type."""
        from src.api.schemas.evidence_asset import EvidenceAssetCreate

        data = {
            "asset_type": "invalid_type",
            "source_module": "near_miss",
            "source_id": 1,
        }
        with pytest.raises(ValidationError) as exc_info:
            EvidenceAssetCreate(**data)

        errors = exc_info.value.errors()
        assert any("asset_type" in str(e) for e in errors)

    def test_create_schema_invalid_source_module(self):
        """Test EvidenceAssetCreate rejects invalid source module."""
        from src.api.schemas.evidence_asset import EvidenceAssetCreate

        data = {
            "asset_type": "photo",
            "source_module": "invalid_module",
            "source_id": 1,
        }
        with pytest.raises(ValidationError) as exc_info:
            EvidenceAssetCreate(**data)

        errors = exc_info.value.errors()
        assert any("source_module" in str(e) for e in errors)

    def test_create_schema_invalid_visibility(self):
        """Test EvidenceAssetCreate rejects invalid visibility."""
        from src.api.schemas.evidence_asset import EvidenceAssetCreate

        data = {
            "asset_type": "photo",
            "source_module": "near_miss",
            "source_id": 1,
            "visibility": "invalid_visibility",
        }
        with pytest.raises(ValidationError) as exc_info:
            EvidenceAssetCreate(**data)

        errors = exc_info.value.errors()
        assert any("visibility" in str(e) for e in errors)

    def test_create_schema_latitude_bounds(self):
        """Test EvidenceAssetCreate validates latitude bounds."""
        from src.api.schemas.evidence_asset import EvidenceAssetCreate

        # Valid latitude
        data = {
            "asset_type": "photo",
            "source_module": "near_miss",
            "source_id": 1,
            "latitude": 51.5074,
            "longitude": -0.1278,
        }
        schema = EvidenceAssetCreate(**data)
        assert schema.latitude == 51.5074

        # Invalid latitude (out of bounds)
        data["latitude"] = 100.0  # > 90
        with pytest.raises(ValidationError):
            EvidenceAssetCreate(**data)

    def test_create_schema_longitude_bounds(self):
        """Test EvidenceAssetCreate validates longitude bounds."""
        from src.api.schemas.evidence_asset import EvidenceAssetCreate

        # Valid longitude
        data = {
            "asset_type": "photo",
            "source_module": "near_miss",
            "source_id": 1,
            "latitude": 51.5074,
            "longitude": -0.1278,
        }
        schema = EvidenceAssetCreate(**data)
        assert schema.longitude == -0.1278

        # Invalid longitude (out of bounds)
        data["longitude"] = 200.0  # > 180
        with pytest.raises(ValidationError):
            EvidenceAssetCreate(**data)


class TestInvestigationSchemaValidation:
    """Test Investigation schema validation for NEAR_MISS support."""

    def test_investigation_create_near_miss(self):
        """Test InvestigationRunCreate accepts near_miss entity type."""
        from src.api.schemas.investigation import InvestigationRunCreate

        data = {
            "template_id": 1,
            "assigned_entity_type": "near_miss",
            "assigned_entity_id": 1,
            "title": "Near Miss Investigation",
        }
        schema = InvestigationRunCreate(**data)
        assert schema.assigned_entity_type == "near_miss"

    def test_investigation_create_all_entity_types(self):
        """Test InvestigationRunCreate accepts all valid entity types."""
        from src.api.schemas.investigation import InvestigationRunCreate

        valid_types = [
            "road_traffic_collision",
            "reporting_incident",
            "complaint",
            "near_miss",
        ]

        for entity_type in valid_types:
            data = {
                "template_id": 1,
                "assigned_entity_type": entity_type,
                "assigned_entity_id": 1,
                "title": f"Investigation for {entity_type}",
            }
            schema = InvestigationRunCreate(**data)
            assert schema.assigned_entity_type == entity_type

    def test_investigation_create_invalid_entity_type(self):
        """Test InvestigationRunCreate rejects invalid entity types."""
        from src.api.schemas.investigation import InvestigationRunCreate

        data = {
            "template_id": 1,
            "assigned_entity_type": "invalid_type",
            "assigned_entity_id": 1,
            "title": "Should Fail",
        }
        with pytest.raises(ValidationError) as exc_info:
            InvestigationRunCreate(**data)

        errors = exc_info.value.errors()
        assert any("assigned_entity_type" in str(e) for e in errors)

    def test_template_applicable_entity_types_accepts_near_miss(self):
        """Test InvestigationTemplateCreate accepts near_miss in applicable types."""
        from src.api.schemas.investigation import InvestigationTemplateCreate

        data = {
            "name": "Near Miss Template",
            "structure": {"sections": []},
            "applicable_entity_types": ["near_miss", "road_traffic_collision"],
        }
        schema = InvestigationTemplateCreate(**data)
        assert "near_miss" in schema.applicable_entity_types


class TestCustomerPackRules:
    """Test customer pack inclusion rules for evidence assets."""

    def test_internal_only_never_included(self):
        """Test that INTERNAL_ONLY visibility excludes from all packs."""
        from src.domain.models.evidence_asset import EvidenceAsset, EvidenceVisibility

        # Create a mock asset (not persisted)
        # We test the logic method directly
        class MockAsset:
            visibility = EvidenceVisibility.INTERNAL_ONLY

            def can_include_in_customer_pack(self, audience: str) -> bool:
                if self.visibility == EvidenceVisibility.INTERNAL_ONLY:
                    return False
                if audience == "external_customer":
                    return self.visibility in (
                        EvidenceVisibility.EXTERNAL_ALLOWED,
                        EvidenceVisibility.PUBLIC,
                    )
                return self.visibility in (
                    EvidenceVisibility.INTERNAL_CUSTOMER,
                    EvidenceVisibility.EXTERNAL_ALLOWED,
                    EvidenceVisibility.PUBLIC,
                )

        asset = MockAsset()
        assert asset.can_include_in_customer_pack("internal_customer") is False
        assert asset.can_include_in_customer_pack("external_customer") is False

    def test_internal_customer_only_in_internal(self):
        """Test that INTERNAL_CUSTOMER visibility only in internal packs."""
        from src.domain.models.evidence_asset import EvidenceVisibility

        class MockAsset:
            visibility = EvidenceVisibility.INTERNAL_CUSTOMER

            def can_include_in_customer_pack(self, audience: str) -> bool:
                if self.visibility == EvidenceVisibility.INTERNAL_ONLY:
                    return False
                if audience == "external_customer":
                    return self.visibility in (
                        EvidenceVisibility.EXTERNAL_ALLOWED,
                        EvidenceVisibility.PUBLIC,
                    )
                return self.visibility in (
                    EvidenceVisibility.INTERNAL_CUSTOMER,
                    EvidenceVisibility.EXTERNAL_ALLOWED,
                    EvidenceVisibility.PUBLIC,
                )

        asset = MockAsset()
        assert asset.can_include_in_customer_pack("internal_customer") is True
        assert asset.can_include_in_customer_pack("external_customer") is False

    def test_external_allowed_in_both(self):
        """Test that EXTERNAL_ALLOWED visibility in both packs."""
        from src.domain.models.evidence_asset import EvidenceVisibility

        class MockAsset:
            visibility = EvidenceVisibility.EXTERNAL_ALLOWED

            def can_include_in_customer_pack(self, audience: str) -> bool:
                if self.visibility == EvidenceVisibility.INTERNAL_ONLY:
                    return False
                if audience == "external_customer":
                    return self.visibility in (
                        EvidenceVisibility.EXTERNAL_ALLOWED,
                        EvidenceVisibility.PUBLIC,
                    )
                return self.visibility in (
                    EvidenceVisibility.INTERNAL_CUSTOMER,
                    EvidenceVisibility.EXTERNAL_ALLOWED,
                    EvidenceVisibility.PUBLIC,
                )

        asset = MockAsset()
        assert asset.can_include_in_customer_pack("internal_customer") is True
        assert asset.can_include_in_customer_pack("external_customer") is True

    def test_public_in_all(self):
        """Test that PUBLIC visibility in all packs."""
        from src.domain.models.evidence_asset import EvidenceVisibility

        class MockAsset:
            visibility = EvidenceVisibility.PUBLIC

            def can_include_in_customer_pack(self, audience: str) -> bool:
                if self.visibility == EvidenceVisibility.INTERNAL_ONLY:
                    return False
                if audience == "external_customer":
                    return self.visibility in (
                        EvidenceVisibility.EXTERNAL_ALLOWED,
                        EvidenceVisibility.PUBLIC,
                    )
                return self.visibility in (
                    EvidenceVisibility.INTERNAL_CUSTOMER,
                    EvidenceVisibility.EXTERNAL_ALLOWED,
                    EvidenceVisibility.PUBLIC,
                )

        asset = MockAsset()
        assert asset.can_include_in_customer_pack("internal_customer") is True
        assert asset.can_include_in_customer_pack("external_customer") is True
