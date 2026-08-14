"""SG-D-05 export appendix — framework filter honesty (no cell-aggregate fork)."""

from src.domain.services.standards_export_appendix import (
    PROGRAMME_FRAMEWORKS,
    action_tokens,
    cap_rows,
    cert_framework_for_item,
    first_matching_cell,
    normalize_framework_ids,
    partition_by_frameworks,
    partition_certs,
)


def test_empty_request_is_full_programme_without_constructionline():
    ids = normalize_framework_ids(None)
    assert ids == list(PROGRAMME_FRAMEWORKS)
    assert "constructionline" not in ids
    assert "9001" in ids and "uvdb" in ids and "chas" in ids


def test_unknown_framework_ids_are_dropped():
    assert normalize_framework_ids(["9001", "constructionline", "nope"]) == ["9001"]


def test_bare_clause_is_unattributed_not_iso9001():
    framework, clause, fate = first_matching_cell(["7.5"], {"9001"})
    assert fate == "unattributed"
    assert framework is None
    assert clause == ""


def test_14001_token_does_not_paint_9001_filter():
    rows = [
        {"id": 1, "tokens": ["9001-7.5"], "title": "QMS"},
        {"id": 2, "tokens": ["14001-6.1.2"], "title": "Env"},
        {"id": 3, "tokens": ["7.5"], "title": "Bare"},
    ]
    matched, unattributed, other = partition_by_frameworks(rows, {"9001"})
    assert [row["id"] for row in matched] == [1]
    assert matched[0]["framework"] == "9001"
    assert matched[0]["clause_number"] == "7.5"
    assert unattributed == 1
    assert other == 1


def test_action_iso_standard_plus_ref_attributes_to_9001():
    tokens = action_tokens(clause_reference="7.5", iso_standard="iso9001")
    framework, clause, fate = first_matching_cell(tokens, {"9001"})
    assert fate == "match"
    assert framework == "9001"
    assert clause == "7.5"


def test_pat_register_cert_is_unmatched_not_9001():
    item = {
        "shelf_key": "register:9",
        "name": "PAT test — van 12",
        "scheme": "register",
        "readiness_status": "valid",
        "metadata": {"certificate_type": "PAT"},
        "detail_path": "/compliance-automation",
    }
    assert cert_framework_for_item(item) is None
    matched, unmatched, other = partition_certs([item], {"9001"}, include_unmatched=False)
    assert matched == []
    assert unmatched == []
    assert other == 0
    _, unmatched_all, _ = partition_certs([item], set(PROGRAMME_FRAMEWORKS), include_unmatched=True)
    assert unmatched_all[0]["proof_scope"] == "unmatched"
    assert unmatched_all[0]["framework"] is None


def test_iso9001_register_cert_lands_only_on_9001():
    item = {
        "shelf_key": "register:1",
        "name": "ISO 9001:2015",
        "scheme": "register",
        "readiness_status": "due_soon",
        "expiry_date": "2026-09-01T00:00:00+00:00",
        "metadata": {"certificate_type": "ISO 9001"},
        "detail_path": "/compliance-automation",
    }
    matched, unmatched, other = partition_certs([item], {"9001"}, include_unmatched=False)
    assert len(matched) == 1
    assert matched[0]["framework"] == "9001"
    assert matched[0]["proof_scope"] == "framework"
    assert unmatched == []
    assert other == 0
    skipped, _, other_iso = partition_certs([item], {"14001"}, include_unmatched=False)
    assert skipped == []
    assert other_iso == 1


def test_cap_rows_flags_truncation():
    rows, truncated = cap_rows([{"id": i} for i in range(5)], limit=3)
    assert [row["id"] for row in rows] == [0, 1, 2]
    assert truncated is True
