"""Contract freeze tests for audit template scheduling and version integrity."""

import json
from pathlib import Path


def _openapi() -> dict:
    # Read the committed contract baseline to avoid runtime dependencies in local tooling.
    return json.loads(Path("docs/contracts/openapi.json").read_text(encoding="utf-8"))


def _schema_name_for_path(path: str, method: str, status_code: str = "200") -> str:
    operation = _openapi()["paths"][path][method]
    return operation["responses"][status_code]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]


def test_templates_endpoint_supports_is_published_filter():
    """Frozen contract: templates listing must support `is_published` query filter."""
    operation = _openapi()["paths"]["/api/v1/audits/templates"]["get"]
    param_names = {param["name"] for param in operation.get("parameters", [])}
    assert "is_published" in param_names


def test_audit_run_response_exposes_template_version():
    """Frozen contract: audit run response must expose template_version."""
    schema_name = _schema_name_for_path("/api/v1/audits/runs", "post", "201")
    run_schema = _openapi()["components"]["schemas"][schema_name]
    assert "template_version" in run_schema["properties"]


def test_template_response_exposes_version_and_publish_state():
    """Frozen contract: template response must include version + publication flag."""
    schema_name = _schema_name_for_path("/api/v1/audits/templates", "get", "200")
    list_schema = _openapi()["components"]["schemas"][schema_name]
    item_schema_name = list_schema["properties"]["items"]["items"]["$ref"].split("/")[-1]
    item_schema = _openapi()["components"]["schemas"][item_schema_name]
    assert "version" in item_schema["properties"]
    assert "is_published" in item_schema["properties"]


def test_frontend_scheduler_uses_published_filter_and_dropdown():
    """Frozen UX contract: scheduling uses published filter and dropdown selector."""
    audits_page = Path("frontend/src/pages/Audits.tsx").read_text(encoding="utf-8")
    assert "listTemplates(1, 100, { is_published: true })" in audits_page
    assert "<select" in audits_page
    assert "Select a published template (latest version)..." in audits_page


def test_frontend_shows_template_version_labels():
    """Frozen UX contract: audit runs display template version labels."""
    audits_page = Path("frontend/src/pages/Audits.tsx").read_text(encoding="utf-8")
    assert "v{audit.template_version}" in audits_page
