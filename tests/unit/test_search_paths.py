"""Unit tests for search result path mapping."""

from urllib.parse import unquote

from src.domain.services.search_paths import build_action_search_path, build_search_path


def test_build_search_path_known_types():
    assert build_search_path("incident", 12) == "/incidents/12"
    assert build_search_path("rta", 3) == "/rtas/3"
    assert build_search_path("complaint", 4) == "/complaints/4"
    assert build_search_path("near_miss", 5) == "/near-misses/5"
    assert build_search_path("risk", 6) == "/risk-register/6"
    assert build_search_path("audit", 7) == "/audits"
    assert build_search_path("document", 9) == "/documents/9"


def test_build_search_path_audit_run_deep_link():
    assert build_search_path("audit", 99, audit_run_id=41) == "/audits/41/execute"


def test_build_action_search_path_uses_unified_keys():
    path = build_action_search_path("capa", 9)
    assert unquote(path) == "/actions/capa:9"
    path2 = build_search_path("action", 3, action_key_kind="incident_action")
    assert unquote(path2 or "") == "/actions/incident_action:3"


def test_build_search_path_unknown_or_missing():
    assert build_search_path("unknown", 1) is None
    assert build_search_path("incident", None) is None
