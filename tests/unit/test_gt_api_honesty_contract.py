"""Golden-thread API honesty contracts for partner/OpenAPI consumers."""

from __future__ import annotations

import json
from pathlib import Path

BASELINE = Path("openapi-baseline.json")
CONTRACT = Path("docs/contracts/openapi.json")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_action_detail_source_type_is_required_in_published_contract():
    operation = _load(BASELINE)["paths"]["/api/v1/actions/{action_id}"]["get"]
    source_type = next(param for param in operation["parameters"] if param["name"] == "source_type")
    assert source_type["in"] == "query"
    assert source_type["required"] is True


def test_operational_and_enterprise_risk_contracts_are_tagged_separately():
    spec = _load(BASELINE)
    assert spec["paths"]["/api/v1/risks/"]["get"]["tags"] == ["Operational Risk Register"]
    assert spec["paths"]["/api/v1/risk-register/"]["get"]["tags"] == ["Enterprise Risk Register"]


def test_paginated_assessment_history_is_published_without_breaking_legacy_array():
    spec = _load(BASELINE)
    paths = spec["paths"]
    legacy = paths["/api/v1/risks/{risk_id}/assessments"]["get"]
    paged = paths["/api/v1/risks/{risk_id}/assessments/paged"]["get"]

    assert legacy["responses"]["200"]["content"]["application/json"]["schema"]["type"] == "array"
    paged_schema = paged["responses"]["200"]["content"]["application/json"]["schema"]
    assert paged_schema["$ref"].endswith("/RiskAssessmentListResponse")
    assert {param["name"] for param in paged["parameters"]} >= {"risk_id", "page", "page_size"}
    assert _load(CONTRACT) == spec
