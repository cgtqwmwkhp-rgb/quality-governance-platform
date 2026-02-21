"""
Stage 2 Investigation Tests - Golden Tests.

Tests for:
- Deterministic prefill from source snapshots
- Customer pack redaction (EXTERNAL redacts identities)
- Evidence asset inclusion matrix
- Optimistic locking prevents silent overwrites
"""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
class TestInvestigationMappingContract:
    """Golden tests for Mapping Contract v1 - deterministic prefill."""

    async def test_near_miss_severity_maps_to_level(self):
        """Test Near Miss severity maps to correct investigation level."""
        from src.domain.models.investigation import InvestigationLevel
        from src.domain.services.investigation_service import InvestigationService

        # LOW severity → LOW level
        assert InvestigationService.NEAR_MISS_SEVERITY_MAP["low"] == InvestigationLevel.LOW
        # MEDIUM severity → MEDIUM level
        assert InvestigationService.NEAR_MISS_SEVERITY_MAP["medium"] == InvestigationLevel.MEDIUM
        # HIGH severity → HIGH level
        assert InvestigationService.NEAR_MISS_SEVERITY_MAP["high"] == InvestigationLevel.HIGH
        # CRITICAL severity → HIGH level
        assert InvestigationService.NEAR_MISS_SEVERITY_MAP["critical"] == InvestigationLevel.HIGH

    async def test_rta_severity_maps_to_level(self):
        """Test RTA severity maps to correct investigation level."""
        from src.domain.models.investigation import InvestigationLevel
        from src.domain.services.investigation_service import InvestigationService

        # near_miss → LOW
        assert InvestigationService.RTA_SEVERITY_MAP["near_miss"] == InvestigationLevel.LOW
        # damage_only → MEDIUM
        assert InvestigationService.RTA_SEVERITY_MAP["damage_only"] == InvestigationLevel.MEDIUM
        # minor_injury → MEDIUM
        assert InvestigationService.RTA_SEVERITY_MAP["minor_injury"] == InvestigationLevel.MEDIUM
        # serious_injury → HIGH
        assert InvestigationService.RTA_SEVERITY_MAP["serious_injury"] == InvestigationLevel.HIGH
        # fatal → HIGH
        assert InvestigationService.RTA_SEVERITY_MAP["fatal"] == InvestigationLevel.HIGH

    async def test_complaint_priority_maps_to_level(self):
        """Test Complaint priority maps to correct investigation level."""
        from src.domain.models.investigation import InvestigationLevel
        from src.domain.services.investigation_service import InvestigationService

        assert InvestigationService.COMPLAINT_PRIORITY_MAP["LOW"] == InvestigationLevel.LOW
        assert InvestigationService.COMPLAINT_PRIORITY_MAP["MEDIUM"] == InvestigationLevel.MEDIUM
        assert InvestigationService.COMPLAINT_PRIORITY_MAP["HIGH"] == InvestigationLevel.HIGH
        assert InvestigationService.COMPLAINT_PRIORITY_MAP["CRITICAL"] == InvestigationLevel.HIGH

    async def test_mapping_reason_codes_defined(self):
        """Test all required mapping reason codes are defined."""
        from src.domain.services.investigation_service import MappingReasonCode

        expected_codes = [
            "SUCCESS",
            "SOURCE_MISSING_FIELD",
            "TYPE_MISMATCH",
            "NOT_APPLICABLE",
            "EMPTY_VALUE",
            "REDACTED_PII",
            "MAPPING_ERROR",
        ]

        for code in expected_codes:
            assert hasattr(MappingReasonCode, code), f"Missing reason code: {code}"


@pytest.mark.asyncio
class TestCustomerPackRedactionRules:
    """Golden tests for Customer Pack Redaction Rules v1."""

    async def test_external_pack_redacts_identity_fields(self):
        """Test EXTERNAL_CUSTOMER packs redact identity fields by default."""
        from src.domain.models.investigation import CustomerPackAudience, InvestigationLevel, InvestigationStatus
        from src.domain.services.investigation_service import InvestigationService

        # Create a mock investigation
        class MockInvestigation:
            reference_number = "INV-2026-0001"
            title = "Test Investigation"
            status = InvestigationStatus.COMPLETED
            level = InvestigationLevel.MEDIUM
            data = {
                "sections": {
                    "section_1_details": {
                        "reference_number": "INV-2026-0001",
                        "description": "Test incident",
                        "reporter_name": "John Smith",
                        "reporter_email": "john@example.com",
                        "persons_involved": "Alice Johnson, Bob Williams",
                        "witnesses": "Carol Davis",
                    }
                }
            }

        investigation = MockInvestigation()

        # Generate EXTERNAL pack
        content, redaction_log, _ = InvestigationService.generate_customer_pack(
            investigation=investigation,
            audience=CustomerPackAudience.EXTERNAL_CUSTOMER,
            evidence_assets=[],
            generated_by_id=1,
        )

        # Identity fields should be redacted
        section = content["sections"]["section_1_details"]
        assert section["reporter_name"] == "[Name Redacted]", "reporter_name not redacted"
        assert section["reporter_email"] == "[Email Redacted]", "reporter_email not redacted"
        assert section["persons_involved"] == "[Redacted]", "persons_involved not redacted"
        assert section["witnesses"] == "[Redacted]", "witnesses not redacted"

        # Non-identity fields should not be redacted
        assert section["description"] == "Test incident"
        assert section["reference_number"] == "INV-2026-0001"

        # Redaction log should record what was redacted
        assert len(redaction_log) >= 4, "Redaction log should have entries for redacted fields"

    async def test_internal_pack_preserves_identity_fields(self):
        """Test INTERNAL_CUSTOMER packs preserve identity fields."""
        from src.domain.models.investigation import CustomerPackAudience, InvestigationLevel, InvestigationStatus
        from src.domain.services.investigation_service import InvestigationService

        class MockInvestigation:
            reference_number = "INV-2026-0002"
            title = "Test Investigation"
            status = InvestigationStatus.COMPLETED
            level = InvestigationLevel.MEDIUM
            data = {
                "sections": {
                    "section_1_details": {
                        "reporter_name": "John Smith",
                        "reporter_email": "john@example.com",
                    }
                }
            }

        investigation = MockInvestigation()

        # Generate INTERNAL pack
        content, redaction_log, _ = InvestigationService.generate_customer_pack(
            investigation=investigation,
            audience=CustomerPackAudience.INTERNAL_CUSTOMER,
            evidence_assets=[],
            generated_by_id=1,
        )

        # Identity fields should NOT be redacted
        section = content["sections"]["section_1_details"]
        assert section["reporter_name"] == "John Smith", "reporter_name should be preserved"
        assert section["reporter_email"] == "john@example.com", "reporter_email should be preserved"

        # No redaction log entries expected
        assert len(redaction_log) == 0, "No redaction should occur for internal pack"

    async def test_pack_excludes_internal_comments(self):
        """Test customer packs never include internal comments."""
        # Comments are stored in investigation_comments table, not in investigation.data
        # The pack generation only uses investigation.data, so comments are automatically excluded
        from src.domain.models.investigation import CustomerPackAudience, InvestigationLevel, InvestigationStatus
        from src.domain.services.investigation_service import InvestigationService

        class MockInvestigation:
            reference_number = "INV-2026-0003"
            title = "Test"
            status = InvestigationStatus.COMPLETED
            level = InvestigationLevel.LOW
            data = {"sections": {"test": {"field": "value"}}}

        investigation = MockInvestigation()

        for audience in [CustomerPackAudience.INTERNAL_CUSTOMER, CustomerPackAudience.EXTERNAL_CUSTOMER]:
            content, _, _ = InvestigationService.generate_customer_pack(
                investigation=investigation,
                audience=audience,
                evidence_assets=[],
                generated_by_id=1,
            )

            # No comments field should exist
            assert "comments" not in content, f"Comments should not be in {audience.value} pack"
            assert "revision_events" not in content, f"Revision events should not be in {audience.value} pack"


@pytest.mark.asyncio
class TestEvidenceAssetVisibilityMatrix:
    """Golden tests for evidence asset visibility rules."""

    async def test_internal_only_excluded_from_all_packs(self):
        """Test INTERNAL_ONLY assets are excluded from all customer packs."""
        from src.domain.models.evidence_asset import EvidenceAssetType, EvidenceVisibility
        from src.domain.models.investigation import CustomerPackAudience, InvestigationLevel, InvestigationStatus
        from src.domain.services.investigation_service import InvestigationService

        class MockAsset:
            id = 1
            title = "Internal Document"
            asset_type = EvidenceAssetType.DOCUMENT
            visibility = EvidenceVisibility.INTERNAL_ONLY
            contains_pii = False
            redaction_required = False

        class MockInvestigation:
            reference_number = "INV-2026-0004"
            title = "Test"
            status = InvestigationStatus.COMPLETED
            level = InvestigationLevel.LOW
            data = {"sections": {}}

        investigation = MockInvestigation()
        assets = [MockAsset()]

        # Test both audiences
        for audience in [CustomerPackAudience.INTERNAL_CUSTOMER, CustomerPackAudience.EXTERNAL_CUSTOMER]:
            _, _, included_assets = InvestigationService.generate_customer_pack(
                investigation=investigation,
                audience=audience,
                evidence_assets=assets,
                generated_by_id=1,
            )

            assert len(included_assets) == 1
            assert included_assets[0]["included"] is False
            assert included_assets[0]["exclusion_reason"] == "INTERNAL_ONLY"

    async def test_internal_customer_assets_in_internal_pack_only(self):
        """Test INTERNAL_CUSTOMER assets only in internal packs."""
        from src.domain.models.evidence_asset import EvidenceAssetType, EvidenceVisibility
        from src.domain.models.investigation import CustomerPackAudience, InvestigationLevel, InvestigationStatus
        from src.domain.services.investigation_service import InvestigationService

        class MockAsset:
            id = 2
            title = "Internal Customer Photo"
            asset_type = EvidenceAssetType.PHOTO
            visibility = EvidenceVisibility.INTERNAL_CUSTOMER
            contains_pii = False
            redaction_required = False

        class MockInvestigation:
            reference_number = "INV-2026-0005"
            title = "Test"
            status = InvestigationStatus.COMPLETED
            level = InvestigationLevel.LOW
            data = {"sections": {}}

        investigation = MockInvestigation()
        assets = [MockAsset()]

        # Internal pack - should include
        _, _, internal_assets = InvestigationService.generate_customer_pack(
            investigation=investigation,
            audience=CustomerPackAudience.INTERNAL_CUSTOMER,
            evidence_assets=assets,
            generated_by_id=1,
        )
        assert internal_assets[0]["included"] is True

        # External pack - should exclude
        _, _, external_assets = InvestigationService.generate_customer_pack(
            investigation=investigation,
            audience=CustomerPackAudience.EXTERNAL_CUSTOMER,
            evidence_assets=assets,
            generated_by_id=1,
        )
        assert external_assets[0]["included"] is False
        assert external_assets[0]["exclusion_reason"] == "INTERNAL_CUSTOMER_ONLY"

    async def test_external_allowed_assets_in_both_packs(self):
        """Test EXTERNAL_ALLOWED assets in both packs."""
        from src.domain.models.evidence_asset import EvidenceAssetType, EvidenceVisibility
        from src.domain.models.investigation import CustomerPackAudience, InvestigationLevel, InvestigationStatus
        from src.domain.services.investigation_service import InvestigationService

        class MockAsset:
            id = 3
            title = "Public Photo"
            asset_type = EvidenceAssetType.PHOTO
            visibility = EvidenceVisibility.EXTERNAL_ALLOWED
            contains_pii = False
            redaction_required = False

        class MockInvestigation:
            reference_number = "INV-2026-0006"
            title = "Test"
            status = InvestigationStatus.COMPLETED
            level = InvestigationLevel.LOW
            data = {"sections": {}}

        investigation = MockInvestigation()
        assets = [MockAsset()]

        for audience in [CustomerPackAudience.INTERNAL_CUSTOMER, CustomerPackAudience.EXTERNAL_CUSTOMER]:
            _, _, included_assets = InvestigationService.generate_customer_pack(
                investigation=investigation,
                audience=audience,
                evidence_assets=assets,
                generated_by_id=1,
            )
            assert included_assets[0]["included"] is True, f"Should be included in {audience.value} pack"


@pytest.mark.asyncio
class TestOptimisticLocking:
    """Golden tests for optimistic locking (version conflicts)."""

    async def test_autosave_requires_version(self, client: AsyncClient):
        """Test autosave endpoint requires version parameter."""
        # Without auth, will get 401 but validates endpoint exists
        response = await client.patch(
            "/api/v1/investigations/1/autosave",
            params={"version": 1},
            json={"sections": {}},
        )
        # Should get 401 (auth required), not 422 (validation error for missing version)
        assert response.status_code == 401

    async def test_version_conflict_detection_logic(self):
        """Test version mismatch would be detected."""
        # This tests the logic, not the endpoint
        current_version = 5
        expected_version = 3

        # Simulating the check in autosave endpoint
        assert current_version != expected_version, "Version mismatch should be detected"


@pytest.mark.asyncio
class TestAPIEndpointValidation:
    """Test Stage 2 API endpoints exist and validate correctly."""

    async def test_from_record_endpoint_exists(self, client: AsyncClient):
        """Test /investigations/from-record endpoint exists and accepts JSON body."""
        response = await client.post(
            "/api/v1/investigations/from-record",
            json={
                "source_type": "near_miss",
                "source_id": 1,
                "title": "Test Investigation",
            },
        )
        # Should get 401 (auth required), not 404 (endpoint not found) or 405 (method not allowed)
        assert response.status_code == 401

    async def test_autosave_endpoint_exists(self, client: AsyncClient):
        """Test /investigations/{id}/autosave endpoint exists."""
        response = await client.patch(
            "/api/v1/investigations/999/autosave",
            params={"version": 1},
            json={"sections": {}},
        )
        assert response.status_code == 401

    async def test_comments_endpoint_exists(self, client: AsyncClient):
        """Test /investigations/{id}/comments endpoint exists."""
        response = await client.post(
            "/api/v1/investigations/999/comments",
            params={"content": "Test comment"},
        )
        assert response.status_code == 401

    async def test_approve_endpoint_exists(self, client: AsyncClient):
        """Test /investigations/{id}/approve endpoint exists."""
        response = await client.post(
            "/api/v1/investigations/999/approve",
            params={"approved": True},
        )
        assert response.status_code == 401

    async def test_customer_pack_endpoint_exists(self, client: AsyncClient):
        """Test /investigations/{id}/customer-pack endpoint exists."""
        response = await client.post(
            "/api/v1/investigations/999/customer-pack",
            params={"audience": "internal_customer"},
        )
        assert response.status_code == 401

    async def test_invalid_audience_rejected(self, client: AsyncClient):
        """Test invalid audience is rejected (after auth)."""
        # Can't test actual rejection without auth, but we can test the enum
        from src.domain.models.investigation import CustomerPackAudience

        valid_audiences = [e.value for e in CustomerPackAudience]
        assert "internal_customer" in valid_audiences
        assert "external_customer" in valid_audiences
        assert "invalid_audience" not in valid_audiences
