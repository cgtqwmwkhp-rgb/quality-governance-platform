"""Unit tests for search result path mapping."""

from src.domain.services.search_paths import build_search_path


def test_build_search_path_known_types():
    assert build_search_path("incident", 12) == "/incidents/12"
    assert build_search_path("rta", 3) == "/rtas/3"
    assert build_search_path("complaint", 4) == "/complaints/4"
    assert build_search_path("near_miss", 5) == "/near-misses/5"
    assert build_search_path("risk", 6) == "/risk-register/6"
    assert build_search_path("audit", 7) == "/audits"
    assert build_search_path("action", 8) == "/actions/8"
    assert build_search_path("document", 9) == "/documents/9"


def test_build_search_path_unknown_or_missing():
    assert build_search_path("unknown", 1) is None
    assert build_search_path("incident", None) is None
