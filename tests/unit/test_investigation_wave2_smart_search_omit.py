"""Unit tests for INV360 Wave 2 smart search + customer-pack omit helpers."""

from __future__ import annotations

from types import SimpleNamespace

from src.domain.services.investigation_service import InvestigationService


def test_pending_and_approved_customer_omits():
    investigation = SimpleNamespace(
        data={
            "customer_pack_visibility": {
                "root-cause": {
                    "omit_requested": True,
                    "omit_approved": False,
                    "omit_reason": "incomplete",
                },
                "fishbone": {
                    "omit_requested": True,
                    "omit_approved": True,
                    "omit_reason": "sensitive",
                },
            }
        }
    )
    assert InvestigationService.pending_customer_omits(investigation) == ["root-cause"]
    assert InvestigationService.approved_customer_omits(investigation) == ["fishbone"]


def test_generate_customer_pack_skips_approved_omitted_sections():
    from src.domain.models.investigation import CustomerPackAudience

    investigation = SimpleNamespace(
        reference_number="REF-1",
        title="T",
        status=SimpleNamespace(value="in_progress"),
        level=SimpleNamespace(value="high"),
        data={
            "sections": {
                "root-cause": {"statement": "bad procedure"},
                "findings": {"text": "ok"},
            },
            "customer_pack_visibility": {
                "root-cause": {"omit_requested": True, "omit_approved": True},
            },
        },
    )
    content, redaction_log, _assets = InvestigationService.generate_customer_pack(
        investigation=investigation,
        audience=CustomerPackAudience.EXTERNAL_CUSTOMER,
        evidence_assets=[],
        generated_by_id=1,
    )
    assert "root-cause" not in content["sections"]
    assert "findings" in content["sections"]
    assert "root-cause" in content.get("omitted_sections", [])
    assert any(r.get("redaction_type") == "SECTION_OMIT_APPROVED" for r in redaction_log)


def test_apply_smart_search_filter_is_noop_for_blank_q():
    sentinel = object()
    assert InvestigationService.apply_smart_search_filter(sentinel, "   ") is sentinel


def test_list_investigations_route_accepts_q_param():
    import ast
    from pathlib import Path

    src = Path("src/api/routes/investigations.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    found = False
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == "list_investigations":
            arg_names = [a.arg for a in node.args.args]
            # FastAPI params may appear as keyword-only
            kwonly = [a.arg for a in node.args.kwonlyargs]
            found = "q" in arg_names or "q" in kwonly
    assert found, "list_investigations must accept additive q parameter"


def test_approve_customer_omit_permission_on_route():
    from pathlib import Path

    src = Path("src/api/routes/investigations.py").read_text(encoding="utf-8")
    assert "investigation:approve_customer_omit" in src
    assert "customer-pack-omit/approve" in src
    assert "MANUAL_ENTRY" in src
