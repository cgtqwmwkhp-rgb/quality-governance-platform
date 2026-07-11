"""Guardrails: write routes use require_permission (AST contract)."""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]


def _permission_depends(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Name) and func.id == "require_permission":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                found.add(node.args[0].value)
        if isinstance(func, ast.Attribute) and func.attr == "require_permission":
            if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
                found.add(node.args[0].value)
    return found


def test_near_miss_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/near_miss.py")
    assert "near_miss:create" in perms
    assert "near_miss:update" in perms


def test_policies_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/policies.py")
    assert "policy:create" in perms
    assert "policy:update" in perms
    assert "policy:delete" in perms


def test_incident_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/incidents.py")
    assert "incident:create" in perms
    assert "incident:update" in perms
    assert "incident:delete" in perms


def test_risk_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/risks.py")
    assert "risk:create" in perms
    assert "risk:update" in perms


def test_audit_primary_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/audits.py")
    assert "audit:create" in perms
    assert "audit:update" in perms


def test_complaint_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/complaints.py")
    assert "complaint:create" in perms
    assert "complaint:update" in perms


def test_rta_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/rtas.py")
    assert "rta:create" in perms
    assert "rta:update" in perms
    assert "rta:delete" in perms


def test_investigation_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/investigations.py")
    assert "investigation:create" in perms
    assert "investigation:update" in perms


def test_document_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/documents.py")
    assert "document:create" in perms
    assert "document:update" in perms


def test_engineer_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/engineers.py")
    assert "engineer:create" in perms
    assert "engineer:update" in perms


def test_assessment_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/assessments.py")
    assert "assessment:create" in perms
    assert "assessment:update" in perms


def test_action_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/actions.py")
    assert "action:create" in perms
    assert "action:update" in perms


def test_risk_register_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/risk_register.py")
    assert "risk:create" in perms
    assert "risk:update" in perms


def test_audit_templates_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/audit_templates.py")
    assert "audit:create" in perms
    assert "audit:update" in perms
    assert "audit:delete" in perms


def test_document_control_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/document_control.py")
    assert "document:create" in perms
    assert "document:update" in perms


def test_evidence_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/evidence_assets.py")
    assert "evidence:create" in perms
    assert "evidence:update" in perms


def test_workflow_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/workflows.py")
    assert "workflow:create" in perms
    assert "workflow:update" in perms


def test_vehicle_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/vehicles.py")
    assert "vehicle:update" in perms
    assert "vehicle:allocate" in perms
    assert "capa:create" in perms


def test_driver_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/drivers.py")
    assert "driver:create" in perms
    assert "driver:update" in perms


def test_induction_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/inductions.py")
    assert "induction:create" in perms
    assert "induction:update" in perms


def test_asset_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/assets.py")
    assert "asset:create" in perms
    assert "asset:update" in perms
    assert "asset:delete" in perms


def test_form_config_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/form_config.py")
    assert "form:create" in perms
    assert "form:update" in perms


def test_investigation_templates_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/investigation_templates.py")
    assert "investigation:create" in perms
    assert "investigation:update" in perms
    assert "investigation:delete" in perms


def test_auditor_competence_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/auditor_competence.py")
    assert "audit:update" in perms


def test_signature_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/signatures.py")
    assert "signature:create" in perms
    assert "signature:update" in perms


def test_kri_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/kri.py")
    assert "kri:create" in perms
    assert "kri:update" in perms
    assert "kri:delete" in perms


def test_standards_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/standards.py")
    assert "standard:create" in perms
    assert "standard:update" in perms


def test_workflow_legacy_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/workflow.py")
    assert "workflow:create" in perms
    assert "workflow:update" in perms
    assert "workflow:delete" in perms


def test_policy_acknowledgment_admin_writes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/policy_acknowledgment.py")
    assert "policy:create" in perms
    assert "policy:update" in perms


def test_rca_tools_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/rca_tools.py")
    assert "rca:create" in perms
    assert "rca:update" in perms


def test_cross_standard_mapping_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/cross_standard_mappings.py")
    assert "standard:create" in perms
    assert "standard:update" in perms


def test_compliance_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/compliance.py")
    assert "audit:create" in perms
    assert "audit:update" in perms


def test_vehicle_checklist_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/vehicle_checklists.py")
    assert "vehicle:update" in perms


def test_iso27001_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/iso27001.py")
    assert "audit:create" in perms
    assert "audit:update" in perms


def test_uvdb_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/uvdb.py")
    assert "audit:create" in perms
    assert "audit:update" in perms


def test_xml_import_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/xml_import.py")
    assert "audit:create" in perms


def test_compliance_automation_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/compliance_automation.py")
    assert "audit:create" in perms
    assert "audit:update" in perms


def test_ai_templates_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/ai_templates.py")
    assert "audit:create" in perms


def test_planet_mark_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/planet_mark.py")
    assert "audit:create" in perms
    assert "audit:update" in perms


def test_ai_intelligence_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/ai_intelligence.py")
    assert "audit:create" in perms


def test_analytics_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/analytics.py")
    assert "analytics:create" in perms
    assert "analytics:update" in perms
    assert "analytics:delete" in perms


def test_audit_trail_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/audit_trail.py")
    assert "audit:read" in perms


def test_push_notifications_write_routes_require_permission():
    perms = _permission_depends(REPO / "src/api/routes/push_notifications.py")
    assert "notifications:send" in perms


def test_notifications_write_routes_require_permission():
    """User writes use update/delete; test-notification keeps notifications:send (#735)."""
    perms = _permission_depends(REPO / "src/api/routes/notifications.py")
    assert "notifications:update" in perms
    assert "notifications:delete" in perms
    assert "notifications:send" in perms
