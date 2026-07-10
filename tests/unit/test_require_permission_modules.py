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

