"""RIDDOR prepare must never look production-ready."""

from src.domain.services.compliance_automation_service import ComplianceAutomationService


def test_prepare_riddor_uses_honest_stub_status():
    service = ComplianceAutomationService(db=None)  # type: ignore[arg-type]
    result = service.prepare_riddor_submission(incident_id=42, riddor_type="injury")
    assert result["status"] == "preparation_stub"
    assert result["persisted"] is False
    assert "HSE portal" in result["status_label"]
