"""Unit tests for Investigation Service - can run standalone."""

import os
import sys

# Add src to path for standalone execution
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))


def test_mapping_reason_codes():
    """Test all required mapping reason codes are defined."""
    from src.services.investigation_service import MappingReasonCode

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
        print(f"✓ {code}")

    print("\n✅ All reason codes defined correctly")


def test_severity_level_mapping():
    """Test severity to investigation level mappings are deterministic."""
    from src.domain.models.investigation import InvestigationLevel
    from src.services.investigation_service import InvestigationService

    # Near Miss mapping
    nm = InvestigationService.NEAR_MISS_SEVERITY_MAP
    assert nm["low"] == InvestigationLevel.LOW
    assert nm["medium"] == InvestigationLevel.MEDIUM
    assert nm["high"] == InvestigationLevel.HIGH
    assert nm["critical"] == InvestigationLevel.HIGH
    print("✓ Near Miss severity mapping correct")

    # RTA mapping
    rta = InvestigationService.RTA_SEVERITY_MAP
    assert rta["near_miss"] == InvestigationLevel.LOW
    assert rta["damage_only"] == InvestigationLevel.MEDIUM
    assert rta["serious_injury"] == InvestigationLevel.HIGH
    assert rta["fatal"] == InvestigationLevel.HIGH
    print("✓ RTA severity mapping correct")

    # Complaint mapping
    comp = InvestigationService.COMPLAINT_PRIORITY_MAP
    assert comp["LOW"] == InvestigationLevel.LOW
    assert comp["MEDIUM"] == InvestigationLevel.MEDIUM
    assert comp["HIGH"] == InvestigationLevel.HIGH
    assert comp["CRITICAL"] == InvestigationLevel.HIGH
    print("✓ Complaint priority mapping correct")

    print("\n✅ All severity/level mappings are deterministic")


def test_customer_pack_redaction_external():
    """Test EXTERNAL_CUSTOMER packs redact identity fields."""
    from src.domain.models.investigation import CustomerPackAudience, InvestigationLevel, InvestigationStatus
    from src.services.investigation_service import InvestigationService

    class MockInvestigation:
        reference_number = "INV-TEST-0001"
        title = "Test Investigation"
        status = InvestigationStatus.COMPLETED
        level = InvestigationLevel.MEDIUM
        data = {
            "sections": {
                "section_1_details": {
                    "reference_number": "INV-TEST-0001",
                    "description": "Test incident description",
                    "reporter_name": "John Smith",
                    "reporter_email": "john@example.com",
                    "driver_name": "Jane Doe",
                    "persons_involved": "Alice, Bob",
                    "witnesses": "Carol, Dave",
                    "location": "123 Main St",
                }
            }
        }

    investigation = MockInvestigation()

    content, redaction_log, _ = InvestigationService.generate_customer_pack(
        investigation=investigation,
        audience=CustomerPackAudience.EXTERNAL_CUSTOMER,
        evidence_assets=[],
        generated_by_id=1,
    )

    section = content["sections"]["section_1_details"]

    # These should be redacted
    assert section["reporter_name"] == "[Name Redacted]", f"Expected redacted, got: {section['reporter_name']}"
    assert section["reporter_email"] == "[Email Redacted]", f"Expected redacted, got: {section['reporter_email']}"
    assert section["driver_name"] == "[Name Redacted]", f"Expected redacted, got: {section['driver_name']}"
    assert section["persons_involved"] == "[Redacted]", f"Expected redacted, got: {section['persons_involved']}"
    assert section["witnesses"] == "[Redacted]", f"Expected redacted, got: {section['witnesses']}"
    print("✓ Identity fields redacted correctly")

    # These should NOT be redacted
    assert section["description"] == "Test incident description"
    assert section["reference_number"] == "INV-TEST-0001"
    assert section["location"] == "123 Main St"
    print("✓ Non-identity fields preserved")

    # Redaction log should have entries
    assert len(redaction_log) >= 5, f"Expected >= 5 redactions, got {len(redaction_log)}"
    print(f"✓ Redaction log has {len(redaction_log)} entries")

    print("\n✅ EXTERNAL_CUSTOMER pack redaction working correctly")


def test_customer_pack_internal_preserves_identities():
    """Test INTERNAL_CUSTOMER packs preserve identity fields."""
    from src.domain.models.investigation import CustomerPackAudience, InvestigationLevel, InvestigationStatus
    from src.services.investigation_service import InvestigationService

    class MockInvestigation:
        reference_number = "INV-TEST-0002"
        title = "Test"
        status = InvestigationStatus.COMPLETED
        level = InvestigationLevel.LOW
        data = {
            "sections": {
                "section_1": {
                    "reporter_name": "John Smith",
                    "reporter_email": "john@example.com",
                }
            }
        }

    investigation = MockInvestigation()

    content, redaction_log, _ = InvestigationService.generate_customer_pack(
        investigation=investigation,
        audience=CustomerPackAudience.INTERNAL_CUSTOMER,
        evidence_assets=[],
        generated_by_id=1,
    )

    section = content["sections"]["section_1"]
    assert section["reporter_name"] == "John Smith"
    assert section["reporter_email"] == "john@example.com"
    assert len(redaction_log) == 0
    print("✓ INTERNAL_CUSTOMER pack preserves identities")
    print(f"✓ Redaction log empty (length: {len(redaction_log)})")

    print("\n✅ INTERNAL_CUSTOMER pack working correctly")


def test_evidence_visibility_matrix():
    """Test evidence asset visibility rules."""
    from src.domain.models.evidence_asset import EvidenceAssetType, EvidenceVisibility
    from src.domain.models.investigation import CustomerPackAudience, InvestigationLevel, InvestigationStatus
    from src.services.investigation_service import InvestigationService

    class MockInvestigation:
        reference_number = "INV-TEST-0003"
        title = "Test"
        status = InvestigationStatus.COMPLETED
        level = InvestigationLevel.LOW
        data = {"sections": {}}

    investigation = MockInvestigation()

    class MockAsset:
        def __init__(self, visibility):
            self.id = 1
            self.title = "Test Asset"
            self.asset_type = EvidenceAssetType.PHOTO
            self.visibility = visibility
            self.contains_pii = False
            self.redaction_required = False

    # Test INTERNAL_ONLY - excluded from all
    asset_internal = MockAsset(EvidenceVisibility.INTERNAL_ONLY)
    _, _, assets = InvestigationService.generate_customer_pack(
        investigation, CustomerPackAudience.INTERNAL_CUSTOMER, [asset_internal], 1
    )
    assert assets[0]["included"] is False
    assert assets[0]["exclusion_reason"] == "INTERNAL_ONLY"
    print("✓ INTERNAL_ONLY excluded from INTERNAL_CUSTOMER pack")

    _, _, assets = InvestigationService.generate_customer_pack(
        investigation, CustomerPackAudience.EXTERNAL_CUSTOMER, [asset_internal], 1
    )
    assert assets[0]["included"] is False
    print("✓ INTERNAL_ONLY excluded from EXTERNAL_CUSTOMER pack")

    # Test INTERNAL_CUSTOMER - only in internal pack
    asset_internal_cust = MockAsset(EvidenceVisibility.INTERNAL_CUSTOMER)
    _, _, assets = InvestigationService.generate_customer_pack(
        investigation, CustomerPackAudience.INTERNAL_CUSTOMER, [asset_internal_cust], 1
    )
    assert assets[0]["included"] is True
    print("✓ INTERNAL_CUSTOMER included in INTERNAL_CUSTOMER pack")

    _, _, assets = InvestigationService.generate_customer_pack(
        investigation, CustomerPackAudience.EXTERNAL_CUSTOMER, [asset_internal_cust], 1
    )
    assert assets[0]["included"] is False
    assert assets[0]["exclusion_reason"] == "INTERNAL_CUSTOMER_ONLY"
    print("✓ INTERNAL_CUSTOMER excluded from EXTERNAL_CUSTOMER pack")

    # Test EXTERNAL_ALLOWED - in both
    asset_external = MockAsset(EvidenceVisibility.EXTERNAL_ALLOWED)
    for audience in [
        CustomerPackAudience.INTERNAL_CUSTOMER,
        CustomerPackAudience.EXTERNAL_CUSTOMER,
    ]:
        _, _, assets = InvestigationService.generate_customer_pack(investigation, audience, [asset_external], 1)
        assert assets[0]["included"] is True
        print(f"✓ EXTERNAL_ALLOWED included in {audience.value} pack")

    print("\n✅ Evidence visibility matrix working correctly")


def test_pack_excludes_comments_and_revisions():
    """Test customer packs never include comments or revision history."""
    from src.domain.models.investigation import CustomerPackAudience, InvestigationLevel, InvestigationStatus
    from src.services.investigation_service import InvestigationService

    class MockInvestigation:
        reference_number = "INV-TEST-0004"
        title = "Test"
        status = InvestigationStatus.COMPLETED
        level = InvestigationLevel.LOW
        data = {"sections": {"test": {"field": "value"}}}

    investigation = MockInvestigation()

    for audience in [
        CustomerPackAudience.INTERNAL_CUSTOMER,
        CustomerPackAudience.EXTERNAL_CUSTOMER,
    ]:
        content, _, _ = InvestigationService.generate_customer_pack(investigation, audience, [], 1)
        assert "comments" not in content, f"comments in {audience.value} pack"
        assert "revision_events" not in content, f"revision_events in {audience.value} pack"
        assert "revision_history" not in content, f"revision_history in {audience.value} pack"
        print(f"✓ {audience.value} pack excludes internal data")

    print("\n✅ Comments and revision history correctly excluded")


if __name__ == "__main__":
    print("=" * 60)
    print("INVESTIGATION SERVICE GOLDEN TESTS")
    print("=" * 60)
    print()

    test_mapping_reason_codes()
    print()
    test_severity_level_mapping()
    print()
    test_customer_pack_redaction_external()
    print()
    test_customer_pack_internal_preserves_identities()
    print()
    test_evidence_visibility_matrix()
    print()
    test_pack_excludes_comments_and_revisions()

    print()
    print("=" * 60)
    print("ALL GOLDEN TESTS PASSED ✅")
    print("=" * 60)
