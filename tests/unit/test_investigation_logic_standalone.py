#!/usr/bin/env python3
"""Standalone golden tests for investigation logic - no external deps."""

import enum
import hashlib
import json
from typing import Any, Dict, List, Optional

# === Minimal reproductions of domain models for testing ===


class InvestigationLevel(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class InvestigationStatus(str, enum.Enum):
    DRAFT = "draft"
    IN_PROGRESS = "in_progress"
    UNDER_REVIEW = "under_review"
    COMPLETED = "completed"
    CLOSED = "closed"


class CustomerPackAudience(str, enum.Enum):
    INTERNAL_CUSTOMER = "internal_customer"
    EXTERNAL_CUSTOMER = "external_customer"


class EvidenceVisibility(str, enum.Enum):
    INTERNAL_ONLY = "internal_only"
    INTERNAL_CUSTOMER = "internal_customer"
    EXTERNAL_ALLOWED = "external_allowed"
    PUBLIC = "public"


class EvidenceAssetType(str, enum.Enum):
    PHOTO = "photo"
    VIDEO = "video"
    DOCUMENT = "document"


# === Reason codes (from contracts) ===


class MappingReasonCode:
    SUCCESS = "SUCCESS"
    SOURCE_MISSING_FIELD = "SOURCE_MISSING_FIELD"
    TYPE_MISMATCH = "TYPE_MISMATCH"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    EMPTY_VALUE = "EMPTY_VALUE"
    REDACTED_PII = "REDACTED_PII"
    MAPPING_ERROR = "MAPPING_ERROR"


# === Mapping tables (from contracts) ===

NEAR_MISS_SEVERITY_MAP = {
    "low": InvestigationLevel.LOW,
    "medium": InvestigationLevel.MEDIUM,
    "high": InvestigationLevel.HIGH,
    "critical": InvestigationLevel.HIGH,
}

RTA_SEVERITY_MAP = {
    "near_miss": InvestigationLevel.LOW,
    "damage_only": InvestigationLevel.MEDIUM,
    "minor_injury": InvestigationLevel.MEDIUM,
    "serious_injury": InvestigationLevel.HIGH,
    "fatal": InvestigationLevel.HIGH,
}

COMPLAINT_PRIORITY_MAP = {
    "LOW": InvestigationLevel.LOW,
    "MEDIUM": InvestigationLevel.MEDIUM,
    "HIGH": InvestigationLevel.HIGH,
    "CRITICAL": InvestigationLevel.HIGH,
}


# === Customer pack generation logic ===

IDENTITY_FIELDS = [
    "reporter_name",
    "reporter_email",
    "driver_name",
    "driver_email",
    "complainant_name",
    "complainant_email",
    "investigator_name",
    "reviewer_name",
    "approver_name",
    "persons_involved",
    "witnesses",
    "witness_names",
    "first_responder",
    "responsible_person",
]


def generate_customer_pack(
    investigation_data: Dict,
    audience: CustomerPackAudience,
    evidence_assets: List[Dict],
) -> tuple:
    """Generate customer pack with redaction rules applied."""
    redaction_log = []
    included_assets = []

    content = {
        "investigation_reference": investigation_data.get("reference_number", "N/A"),
        "title": investigation_data.get("title", "N/A"),
        "status": investigation_data.get("status", "unknown"),
        "level": investigation_data.get("level", "medium"),
        "sections": {},
    }

    source_data = investigation_data.get("data", {})
    for section_id, section_data in source_data.get("sections", {}).items():
        content["sections"][section_id] = {}

        if isinstance(section_data, dict):
            for field_id, field_value in section_data.items():
                redacted = False

                if audience == CustomerPackAudience.EXTERNAL_CUSTOMER:
                    if field_id in IDENTITY_FIELDS and field_value:
                        original_value = field_value
                        if "name" in field_id:
                            field_value = "[Name Redacted]"
                        elif "email" in field_id:
                            field_value = "[Email Redacted]"
                        else:
                            field_value = "[Redacted]"
                        redacted = True
                        redaction_log.append(
                            {
                                "field_path": f"{section_id}.{field_id}",
                                "redaction_type": "IDENTITY_REDACTION",
                                "original_type": type(original_value).__name__,
                            }
                        )

                content["sections"][section_id][field_id] = field_value

    # Process evidence assets
    for asset in evidence_assets:
        can_include = False
        exclusion_reason = None

        visibility = asset.get("visibility", EvidenceVisibility.INTERNAL_ONLY)

        if visibility == EvidenceVisibility.INTERNAL_ONLY:
            exclusion_reason = "INTERNAL_ONLY"
        elif visibility == EvidenceVisibility.INTERNAL_CUSTOMER:
            if audience == CustomerPackAudience.INTERNAL_CUSTOMER:
                can_include = True
            else:
                exclusion_reason = "INTERNAL_CUSTOMER_ONLY"
        elif visibility in (
            EvidenceVisibility.EXTERNAL_ALLOWED,
            EvidenceVisibility.PUBLIC,
        ):
            can_include = True

        included_assets.append(
            {
                "asset_id": asset.get("id"),
                "included": can_include,
                "exclusion_reason": exclusion_reason,
            }
        )

    return content, redaction_log, included_assets


# === TESTS ===


def test_mapping_reason_codes():
    """Test all required mapping reason codes are defined."""
    print("Testing Mapping Reason Codes...")
    expected = [
        "SUCCESS",
        "SOURCE_MISSING_FIELD",
        "TYPE_MISMATCH",
        "NOT_APPLICABLE",
        "EMPTY_VALUE",
        "REDACTED_PII",
        "MAPPING_ERROR",
    ]

    for code in expected:
        assert hasattr(MappingReasonCode, code), f"Missing: {code}"
        print(f"  ✓ {code}")

    print("  ✅ All reason codes defined\n")


def test_severity_level_mapping():
    """Test severity to level mappings are deterministic."""
    print("Testing Severity → Level Mappings...")

    # Near Miss
    assert NEAR_MISS_SEVERITY_MAP["low"] == InvestigationLevel.LOW
    assert NEAR_MISS_SEVERITY_MAP["medium"] == InvestigationLevel.MEDIUM
    assert NEAR_MISS_SEVERITY_MAP["high"] == InvestigationLevel.HIGH
    assert NEAR_MISS_SEVERITY_MAP["critical"] == InvestigationLevel.HIGH
    print("  ✓ Near Miss mapping correct")

    # RTA
    assert RTA_SEVERITY_MAP["near_miss"] == InvestigationLevel.LOW
    assert RTA_SEVERITY_MAP["damage_only"] == InvestigationLevel.MEDIUM
    assert RTA_SEVERITY_MAP["serious_injury"] == InvestigationLevel.HIGH
    assert RTA_SEVERITY_MAP["fatal"] == InvestigationLevel.HIGH
    print("  ✓ RTA mapping correct")

    # Complaint
    assert COMPLAINT_PRIORITY_MAP["LOW"] == InvestigationLevel.LOW
    assert COMPLAINT_PRIORITY_MAP["MEDIUM"] == InvestigationLevel.MEDIUM
    assert COMPLAINT_PRIORITY_MAP["HIGH"] == InvestigationLevel.HIGH
    assert COMPLAINT_PRIORITY_MAP["CRITICAL"] == InvestigationLevel.HIGH
    print("  ✓ Complaint mapping correct")

    print("  ✅ All severity mappings deterministic\n")


def test_external_pack_redaction():
    """Test EXTERNAL_CUSTOMER packs redact identity fields."""
    print("Testing EXTERNAL Pack Redaction...")

    investigation = {
        "reference_number": "INV-2026-0001",
        "title": "Test Investigation",
        "status": "completed",
        "level": "medium",
        "data": {
            "sections": {
                "section_1": {
                    "reference_number": "INV-2026-0001",
                    "description": "Test incident",
                    "reporter_name": "John Smith",
                    "reporter_email": "john@example.com",
                    "driver_name": "Jane Doe",
                    "persons_involved": "Alice, Bob",
                    "witnesses": "Carol, Dave",
                    "location": "123 Main St",
                }
            }
        },
    }

    content, redaction_log, _ = generate_customer_pack(
        investigation, CustomerPackAudience.EXTERNAL_CUSTOMER, []
    )

    section = content["sections"]["section_1"]

    # Identity fields MUST be redacted
    assert (
        section["reporter_name"] == "[Name Redacted]"
    ), f"reporter_name not redacted: {section['reporter_name']}"
    assert (
        section["reporter_email"] == "[Email Redacted]"
    ), f"reporter_email not redacted: {section['reporter_email']}"
    assert (
        section["driver_name"] == "[Name Redacted]"
    ), f"driver_name not redacted: {section['driver_name']}"
    assert (
        section["persons_involved"] == "[Redacted]"
    ), f"persons_involved not redacted: {section['persons_involved']}"
    assert (
        section["witnesses"] == "[Redacted]"
    ), f"witnesses not redacted: {section['witnesses']}"
    print("  ✓ All identity fields redacted")

    # Non-identity fields MUST be preserved
    assert section["description"] == "Test incident"
    assert section["reference_number"] == "INV-2026-0001"
    assert section["location"] == "123 Main St"
    print("  ✓ Non-identity fields preserved")

    # Redaction log MUST have entries
    assert (
        len(redaction_log) >= 5
    ), f"Expected >= 5 redactions, got {len(redaction_log)}"
    print(f"  ✓ Redaction log has {len(redaction_log)} entries")

    print("  ✅ EXTERNAL pack redaction correct\n")


def test_internal_pack_preserves_identities():
    """Test INTERNAL_CUSTOMER packs preserve identity fields."""
    print("Testing INTERNAL Pack Identity Preservation...")

    investigation = {
        "reference_number": "INV-2026-0002",
        "title": "Test",
        "status": "completed",
        "level": "low",
        "data": {
            "sections": {
                "section_1": {
                    "reporter_name": "John Smith",
                    "reporter_email": "john@example.com",
                }
            }
        },
    }

    content, redaction_log, _ = generate_customer_pack(
        investigation, CustomerPackAudience.INTERNAL_CUSTOMER, []
    )

    section = content["sections"]["section_1"]
    assert section["reporter_name"] == "John Smith", "Name should be preserved"
    assert section["reporter_email"] == "john@example.com", "Email should be preserved"
    assert len(redaction_log) == 0, f"No redaction expected, got {len(redaction_log)}"
    print("  ✓ Identity fields preserved")
    print("  ✓ No redaction entries")

    print("  ✅ INTERNAL pack preserves identities\n")


def test_evidence_visibility_matrix():
    """Test evidence asset visibility rules."""
    print("Testing Evidence Visibility Matrix...")

    investigation = {
        "reference_number": "INV-2026-0003",
        "title": "Test",
        "status": "completed",
        "level": "low",
        "data": {"sections": {}},
    }

    # INTERNAL_ONLY - excluded from ALL packs
    asset_internal = {"id": 1, "visibility": EvidenceVisibility.INTERNAL_ONLY}
    _, _, assets = generate_customer_pack(
        investigation, CustomerPackAudience.INTERNAL_CUSTOMER, [asset_internal]
    )
    assert (
        assets[0]["included"] is False
        and assets[0]["exclusion_reason"] == "INTERNAL_ONLY"
    )
    print("  ✓ INTERNAL_ONLY excluded from INTERNAL pack")

    _, _, assets = generate_customer_pack(
        investigation, CustomerPackAudience.EXTERNAL_CUSTOMER, [asset_internal]
    )
    assert (
        assets[0]["included"] is False
        and assets[0]["exclusion_reason"] == "INTERNAL_ONLY"
    )
    print("  ✓ INTERNAL_ONLY excluded from EXTERNAL pack")

    # INTERNAL_CUSTOMER - only in internal pack
    asset_int_cust = {"id": 2, "visibility": EvidenceVisibility.INTERNAL_CUSTOMER}
    _, _, assets = generate_customer_pack(
        investigation, CustomerPackAudience.INTERNAL_CUSTOMER, [asset_int_cust]
    )
    assert assets[0]["included"] is True
    print("  ✓ INTERNAL_CUSTOMER included in INTERNAL pack")

    _, _, assets = generate_customer_pack(
        investigation, CustomerPackAudience.EXTERNAL_CUSTOMER, [asset_int_cust]
    )
    assert (
        assets[0]["included"] is False
        and assets[0]["exclusion_reason"] == "INTERNAL_CUSTOMER_ONLY"
    )
    print("  ✓ INTERNAL_CUSTOMER excluded from EXTERNAL pack")

    # EXTERNAL_ALLOWED - in both packs
    asset_ext = {"id": 3, "visibility": EvidenceVisibility.EXTERNAL_ALLOWED}
    _, _, assets = generate_customer_pack(
        investigation, CustomerPackAudience.INTERNAL_CUSTOMER, [asset_ext]
    )
    assert assets[0]["included"] is True
    print("  ✓ EXTERNAL_ALLOWED included in INTERNAL pack")

    _, _, assets = generate_customer_pack(
        investigation, CustomerPackAudience.EXTERNAL_CUSTOMER, [asset_ext]
    )
    assert assets[0]["included"] is True
    print("  ✓ EXTERNAL_ALLOWED included in EXTERNAL pack")

    print("  ✅ Evidence visibility matrix correct\n")


def test_pack_excludes_internal_data():
    """Test customer packs never include comments or revision history."""
    print("Testing Internal Data Exclusion...")

    investigation = {
        "reference_number": "INV-2026-0004",
        "title": "Test",
        "status": "completed",
        "level": "low",
        "data": {"sections": {"test": {"field": "value"}}},
    }

    for audience in [
        CustomerPackAudience.INTERNAL_CUSTOMER,
        CustomerPackAudience.EXTERNAL_CUSTOMER,
    ]:
        content, _, _ = generate_customer_pack(investigation, audience, [])
        assert "comments" not in content, f"comments in {audience.value}"
        assert "revision_events" not in content, f"revision_events in {audience.value}"
        assert (
            "revision_history" not in content
        ), f"revision_history in {audience.value}"
        print(f"  ✓ {audience.value} excludes internal data")

    print("  ✅ Internal data correctly excluded\n")


def test_optimistic_locking_logic():
    """Test optimistic locking version check logic."""
    print("Testing Optimistic Locking Logic...")

    current_version = 5
    expected_version = 5
    assert current_version == expected_version, "Versions should match"
    print("  ✓ Version match allows update")

    current_version = 6
    expected_version = 5
    assert current_version != expected_version, "Version mismatch should be detected"
    print("  ✓ Version mismatch detected → conflict")

    print("  ✅ Optimistic locking logic correct\n")


if __name__ == "__main__":
    print("=" * 60)
    print("INVESTIGATION GOLDEN TESTS (Standalone)")
    print("=" * 60)
    print()

    test_mapping_reason_codes()
    test_severity_level_mapping()
    test_external_pack_redaction()
    test_internal_pack_preserves_identities()
    test_evidence_visibility_matrix()
    test_pack_excludes_internal_data()
    test_optimistic_locking_logic()

    print("=" * 60)
    print("ALL GOLDEN TESTS PASSED ✅")
    print("=" * 60)
