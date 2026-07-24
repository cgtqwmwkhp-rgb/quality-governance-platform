"""Unit tests for Safety Insights Analyst pure logic."""

from __future__ import annotations

from datetime import datetime, timezone

from src.domain.services.safety_insights_analyst import SafetyInsightsAnalystService


def _case(module: str, cid: int, **kwargs):
    base = {
        "module": module,
        "id": cid,
        "reference_number": f"{module.upper()}-{cid}",
        "event_date": datetime(2026, 1, 15, tzinfo=timezone.utc),
        "title": "",
        "description": "reversing into stationary object",
        "location": "Depot A",
        "department": "",
        "contract": "Contract X",
        "person": "Alex Driver",
        "people": "",
        "vehicle": "AB12CDE",
        "asset_id": 9,
        "root_cause": "",
        "severity": "medium",
        "is_hipo": False,
    }
    base.update(kwargs)
    return base


def test_dimension_rollups_require_repeat_and_cite_cases():
    corpus = [
        _case("rta", 1),
        _case("rta", 2),
        _case("rta", 3, location="Depot B", vehicle="ZZ99ZZZ", person="Other"),
    ]
    svc = object.__new__(SafetyInsightsAnalystService)
    dims = svc.dimension_rollups(corpus)
    by_type = {(d["dimension_type"], d["dimension_key"]): d for d in dims}
    assert ("location", "Depot A") in by_type
    assert by_type[("location", "Depot A")]["case_count"] == 2
    assert ("vehicle", "AB12CDE") in by_type
    # singleton Depot B should be excluded
    assert ("location", "Depot B") not in by_type


def test_validate_citations_strips_hallucinated_ids():
    svc = object.__new__(SafetyInsightsAnalystService)
    corpus = [_case("rta", 10), _case("rta", 11), _case("incident", 5)]
    themes = [
        {
            "label": "reversing into stationary object",
            "rationale": "clear pattern",
            "module_scope": "rta",
            "case_refs": [
                {"module": "rta", "id": 10, "reference_number": "RTA-10"},
                {"module": "rta", "id": 11, "reference_number": "RTA-11"},
                {"module": "rta", "id": 999, "reference_number": "FAKE"},
            ],
        },
        {
            "label": "singleton noise",
            "case_refs": [{"module": "incident", "id": 5, "reference_number": "INCIDENT-5"}],
        },
    ]
    validated = svc.validate_citations(themes, corpus, min_cluster_size=2)
    assert len(validated) == 1
    assert validated[0]["label"] == "reversing into stationary object"
    assert validated[0]["case_count"] == 2
    ids = {r["id"] for r in validated[0]["case_refs"]}
    assert ids == {10, 11}


def test_quality_scorecard_reports_missing_fields():
    svc = object.__new__(SafetyInsightsAnalystService)
    corpus = [
        _case("rta", 1, root_cause="", vehicle=""),
        _case("rta", 2, root_cause="speed", vehicle="AB12CDE", location=""),
    ]
    score = svc.compute_quality_scorecard(corpus)
    assert score["total"] == 2
    assert score["fields"]["rta_missing_vehicle_pct"] == 50.0
    assert score["fields"]["missing_location_pct"] == 50.0


def test_module_normalisation():
    assert SafetyInsightsAnalystService._normalise_modules(["incidents", "RTAs", "near_miss"]) == [
        "incident",
        "rta",
        "near_miss",
    ]
