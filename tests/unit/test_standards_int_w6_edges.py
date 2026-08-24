"""Int-W6: CE↔CE+ NEAR edges, no invented EXACT, payload + isolation pins."""

from __future__ import annotations

from pathlib import Path

from src.domain.models.standards_alignment import AlignmentVerdict
from src.domain.services.standards_alignment_import_service import DEFAULT_PAYLOAD_PATH, build_edges, load_payload
from src.domain.services.standards_trap_guard import clause_key

FORBIDDEN_EXACT_FRAMEWORKS = frozenset({"ce", "cep", "chas", "ssip", "pm", "uvdb"})
CE_CONTROLS = (
    "firewalls",
    "secure_configuration",
    "user_access_control",
    "malware_protection",
    "patch_management",
)
REPO = Path(__file__).resolve().parents[2]


def test_default_payload_is_v11_and_same_source_ref() -> None:
    assert DEFAULT_PAYLOAD_PATH.name == "pel-hseq-5064-alignment-v1.1.json"
    payload = load_payload()
    assert payload["source_ref"] == "PEL-HSEQ-5064"
    assert payload["version_label"] == "1.1"
    assert (REPO / DEFAULT_PAYLOAD_PATH).is_file()


def test_v10_payload_remains_checked_in() -> None:
    assert (REPO / "specs/standards/pel-hseq-5064-alignment-v1.0.json").is_file()


def test_zero_exact_edges_name_scheme_frameworks() -> None:
    edges, warnings = build_edges(load_payload())
    assert warnings == []
    for edge in edges:
        if edge.verdict is not AlignmentVerdict.EXACT:
            continue
        for fw in (edge.key.src_framework, edge.key.dst_framework):
            assert fw not in FORBIDDEN_EXACT_FRAMEWORKS, edge.key.as_token()


def test_five_ce_cep_near_pairs_and_no_more() -> None:
    edges, _ = build_edges(load_payload())
    ce_near = [
        edge
        for edge in edges
        if edge.verdict is AlignmentVerdict.NEAR and {edge.key.src_framework, edge.key.dst_framework} == {"ce", "cep"}
    ]
    assert len(ce_near) == 5
    refs = {edge.clause_ref for edge in ce_near}
    assert refs == set(CE_CONTROLS)
    for edge in ce_near:
        assert edge.source_authority == "ncsc_cyber_essentials"
        assert edge.addition_text
        assert "independent" in edge.addition_text.lower()


def test_coverage_declarations_mark_chas_ssip_pm_uvdb_absent() -> None:
    payload = load_payload()
    declared = payload["coverage_declarations"]
    for fw in ("chas", "ssip", "pm", "uvdb"):
        assert declared[fw]["status"] == "declared_absent"


def test_catalogue_clause_key_still_preserves_iip_case() -> None:
    assert clause_key("iip", "IIP 3") == "iip-IIP 3"
    assert clause_key("iip", "IIP 7") == "iip-IIP 7"


def test_w6_alembic_sits_on_w5_head() -> None:
    text = (REPO / "alembic/versions/20261113_standards_w6_alignment_edges.py").read_text(encoding="utf-8")
    assert 'revision: str = "20261113_standards_w6_edges"' in text
    assert "20261112_standards_w5_axes" in text
