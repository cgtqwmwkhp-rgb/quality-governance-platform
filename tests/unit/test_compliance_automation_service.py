"""Unit tests for Compliance Automation Service - can run standalone."""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

import pytest  # noqa: E402


def test_compliance_automation_service_instantiation():
    """Test ComplianceAutomationService can be instantiated and has expected methods."""
    from src.domain.services.compliance_automation_service import ComplianceAutomationService

    service = ComplianceAutomationService()

    expected_methods = [
        "get_regulatory_updates",
        "mark_update_reviewed",
        "run_gap_analysis",
        "get_gap_analyses",
        "get_certificates",
        "get_expiring_certificates_summary",
        "add_certificate",
        "get_scheduled_audits",
        "schedule_audit",
        "calculate_compliance_score",
        "get_compliance_trend",
        "get_riddor_submissions",
        "check_riddor_required",
        "prepare_riddor_submission",
        "submit_riddor",
        "seed_default_data",
    ]

    for method in expected_methods:
        assert hasattr(service, method), f"Missing method: {method}"
        print(f"✓ {method}")

    print(f"\n✅ All {len(expected_methods)} methods present")


def test_row_to_dict_helper():
    """Test _row_to_dict correctly converts model instances to dicts."""
    from src.domain.services.compliance_automation_service import _row_to_dict

    class MockColumn:
        def __init__(self, name):
            self.name = name

    class MockTable:
        columns = [MockColumn("id"), MockColumn("name"), MockColumn("created_at")]

    class MockObj:
        __table__ = MockTable()
        id = 42
        name = "Test Certificate"
        created_at = datetime(2026, 1, 15, 10, 30, 0)

    result = _row_to_dict(MockObj())

    assert result["id"] == 42
    assert result["name"] == "Test Certificate"
    assert result["created_at"] == "2026-01-15T10:30:00"
    print("✓ Integer field preserved")
    print("✓ String field preserved")
    print("✓ Datetime serialized to ISO format")

    print("\n✅ _row_to_dict helper works correctly")


@pytest.mark.asyncio
async def test_check_riddor_required_fatality():
    """Test RIDDOR detection for fatality incidents."""
    from src.domain.services.compliance_automation_service import ComplianceAutomationService

    service = ComplianceAutomationService()

    result = await service.check_riddor_required({"fatality": True})

    assert result["is_riddor"] is True
    assert "death" in result["riddor_types"]
    assert result["deadline"] is not None
    assert result["submission_url"] == "https://www.hse.gov.uk/riddor/report.htm"
    print("✓ Fatality correctly identified as RIDDOR reportable")
    print(f"  Types: {result['riddor_types']}")
    print(f"  Deadline: {result['deadline']}")

    print("\n✅ RIDDOR fatality detection correct")


@pytest.mark.asyncio
async def test_check_riddor_required_specified_injuries():
    """Test RIDDOR detection for specified injuries."""
    from src.domain.services.compliance_automation_service import ComplianceAutomationService

    service = ComplianceAutomationService()

    specified_injuries = ["fracture", "amputation", "dislocation", "loss_of_sight"]

    for injury in specified_injuries:
        result = await service.check_riddor_required({"injury_type": injury})
        assert result["is_riddor"] is True
        assert "specified_injury" in result["riddor_types"]
        print(f"✓ {injury} → RIDDOR specified_injury")

    print("\n✅ All specified injuries correctly detected")


@pytest.mark.asyncio
async def test_check_riddor_required_over_7_day_incapacitation():
    """Test RIDDOR detection for over 7 day incapacitation."""
    from src.domain.services.compliance_automation_service import ComplianceAutomationService

    service = ComplianceAutomationService()

    result = await service.check_riddor_required({"days_off_work": 8})
    assert result["is_riddor"] is True
    assert "over_7_day_incapacitation" in result["riddor_types"]
    print("✓ 8 days off work → RIDDOR (over 7 day incapacitation)")

    result = await service.check_riddor_required({"days_off_work": 7})
    assert result["is_riddor"] is False
    assert "over_7_day_incapacitation" not in result["riddor_types"]
    print("✓ 7 days off work → NOT RIDDOR (boundary: must be > 7)")

    result = await service.check_riddor_required({"days_off_work": 0})
    assert result["is_riddor"] is False
    print("✓ 0 days off work → NOT RIDDOR")

    print("\n✅ Over 7 day incapacitation logic correct")


@pytest.mark.asyncio
async def test_check_riddor_required_dangerous_occurrence():
    """Test RIDDOR detection for dangerous occurrences."""
    from src.domain.services.compliance_automation_service import ComplianceAutomationService

    service = ComplianceAutomationService()

    result = await service.check_riddor_required({"dangerous_occurrence": True})
    assert result["is_riddor"] is True
    assert "dangerous_occurrence" in result["riddor_types"]
    print("✓ Dangerous occurrence correctly identified")

    result = await service.check_riddor_required({"dangerous_occurrence": False})
    assert result["is_riddor"] is False
    print("✓ Non-dangerous occurrence correctly excluded")

    print("\n✅ Dangerous occurrence detection correct")


@pytest.mark.asyncio
async def test_check_riddor_required_occupational_disease():
    """Test RIDDOR detection for occupational disease."""
    from src.domain.services.compliance_automation_service import ComplianceAutomationService

    service = ComplianceAutomationService()

    result = await service.check_riddor_required({"occupational_disease": True})
    assert result["is_riddor"] is True
    assert "occupational_disease" in result["riddor_types"]
    print("✓ Occupational disease correctly identified")

    print("\n✅ Occupational disease detection correct")


@pytest.mark.asyncio
async def test_check_riddor_not_required():
    """Test RIDDOR returns false for non-reportable incidents."""
    from src.domain.services.compliance_automation_service import ComplianceAutomationService

    service = ComplianceAutomationService()

    result = await service.check_riddor_required({})
    assert result["is_riddor"] is False
    assert result["riddor_types"] == []
    assert result["deadline"] is None
    assert result["submission_url"] is None
    print("✓ Empty incident data → NOT RIDDOR")

    result = await service.check_riddor_required(
        {
            "injury_type": "bruise",
            "days_off_work": 3,
            "fatality": False,
        }
    )
    assert result["is_riddor"] is False
    print("✓ Minor injury (bruise, 3 days) → NOT RIDDOR")

    print("\n✅ Non-reportable incidents correctly excluded")


@pytest.mark.asyncio
async def test_check_riddor_deadline_calculation():
    """Test RIDDOR deadline calculation: death/specified=10 days, others=15 days."""
    from src.domain.services.compliance_automation_service import ComplianceAutomationService

    service = ComplianceAutomationService()

    before = datetime.utcnow()
    result_death = await service.check_riddor_required({"fatality": True})
    deadline_death = datetime.fromisoformat(result_death["deadline"])
    days_death = (deadline_death - before).days
    assert 9 <= days_death <= 10, f"Death deadline should be ~10 days, got {days_death}"
    print(f"✓ Death deadline: {days_death} days (~10 expected)")

    before = datetime.utcnow()
    result_fracture = await service.check_riddor_required({"injury_type": "fracture"})
    deadline_fracture = datetime.fromisoformat(result_fracture["deadline"])
    days_fracture = (deadline_fracture - before).days
    assert 9 <= days_fracture <= 10, f"Specified injury deadline should be ~10 days, got {days_fracture}"
    print(f"✓ Specified injury deadline: {days_fracture} days (~10 expected)")

    before = datetime.utcnow()
    result_7day = await service.check_riddor_required({"days_off_work": 10})
    deadline_7day = datetime.fromisoformat(result_7day["deadline"])
    days_7day = (deadline_7day - before).days
    assert 14 <= days_7day <= 15, f"Over 7 day deadline should be ~15 days, got {days_7day}"
    print(f"✓ Over 7 day incapacitation deadline: {days_7day} days (~15 expected)")

    print("\n✅ RIDDOR deadline calculation correct")


@pytest.mark.asyncio
async def test_check_riddor_multiple_types():
    """Test RIDDOR with multiple reportable conditions in one incident."""
    from src.domain.services.compliance_automation_service import ComplianceAutomationService

    service = ComplianceAutomationService()

    result = await service.check_riddor_required(
        {
            "fatality": True,
            "injury_type": "fracture",
            "days_off_work": 14,
            "dangerous_occurrence": True,
        }
    )

    assert result["is_riddor"] is True
    assert "death" in result["riddor_types"]
    assert "specified_injury" in result["riddor_types"]
    assert "over_7_day_incapacitation" in result["riddor_types"]
    assert "dangerous_occurrence" in result["riddor_types"]
    assert len(result["riddor_types"]) == 4
    print(f"✓ Multiple RIDDOR types detected: {result['riddor_types']}")

    deadline = datetime.fromisoformat(result["deadline"])
    days = (deadline - datetime.utcnow()).days
    assert days <= 10, "Deadline should be 10 days (death takes precedence)"
    print(f"✓ Deadline uses most urgent category ({days} days)")

    print("\n✅ Multiple RIDDOR type handling correct")


if __name__ == "__main__":
    import asyncio

    print("=" * 60)
    print("COMPLIANCE AUTOMATION SERVICE TESTS")
    print("=" * 60)
    print()

    test_compliance_automation_service_instantiation()
    print()
    test_row_to_dict_helper()
    print()
    asyncio.run(test_check_riddor_required_fatality())
    print()
    asyncio.run(test_check_riddor_required_specified_injuries())
    print()
    asyncio.run(test_check_riddor_required_over_7_day_incapacitation())
    print()
    asyncio.run(test_check_riddor_required_dangerous_occurrence())
    print()
    asyncio.run(test_check_riddor_required_occupational_disease())
    print()
    asyncio.run(test_check_riddor_not_required())
    print()
    asyncio.run(test_check_riddor_deadline_calculation())
    print()
    asyncio.run(test_check_riddor_multiple_types())

    print()
    print("=" * 60)
    print("ALL COMPLIANCE AUTOMATION TESTS PASSED ✅")
    print("=" * 60)
