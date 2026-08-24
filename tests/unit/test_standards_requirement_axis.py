"""Int-W5 requirement axis — catalogues without alignment bleed."""

from __future__ import annotations

from src.domain.services.standards_requirement_axis import (
    all_requirement_axes,
    has_requirement_axis,
    requirement_axes_payload,
    requirement_catalogue_key,
)
from src.domain.services.standards_trap_guard import TrapGuard, clause_key


def test_keys_match_trap_guard_formula() -> None:
    assert requirement_catalogue_key("chas", "CHAS 1") == clause_key("chas", "CHAS 1")
    assert requirement_catalogue_key("iip", "IIP 3") == "iip-IIP 3"
    assert requirement_catalogue_key("ce", "user_access_control") == "ce-user_access_control"


def test_iip_keys_match_5064_edge_shape() -> None:
    keys = {row["catalogue_key"] for row in all_requirement_axes()["iip"]["rows"]}
    assert "iip-IIP 3" in keys
    assert "iip-IIP 7" in keys


def test_no_constructionline_axis() -> None:
    assert "constructionline" not in all_requirement_axes()
    assert has_requirement_axis("constructionline") is False


def test_uvdb_pending_sections_honest() -> None:
    rows = all_requirement_axes()["uvdb"]["rows"]
    pending = [r for r in rows if r["content_status"] == "pending_protocol_pdf"]
    loaded = [r for r in rows if r["content_status"] == "loaded"]
    assert pending, "sections 3-11 must remain pending_protocol_pdf"
    assert loaded, "loaded sections must still appear"
    assert all(r.get("title") for r in pending)


def test_covers_framework_stays_false_for_chas_without_edges() -> None:
    guard = TrapGuard()
    assert has_requirement_axis("chas") is True
    assert guard.covers_framework("chas") is False


def test_requirement_axes_payload_dedupes_alignment_keys() -> None:
    payload = requirement_axes_payload(alignment_clause_keys={"iip-IIP 3"})
    iip_keys = {r["catalogue_key"] for r in payload["axes"]["iip"]["rows"]}
    assert "iip-IIP 3" not in iip_keys
    assert "iip-IIP 7" in iip_keys
    assert payload["axes"]["iip"]["deduped_against_alignment"] >= 1


def test_every_axis_row_has_provenance() -> None:
    for fw, axis in all_requirement_axes().items():
        assert axis.get("source_ref"), fw
        assert axis.get("content_status"), fw
        for row in axis["rows"]:
            assert row["catalogue_key"].startswith(f"{fw}-")
            assert row.get("content_status")
