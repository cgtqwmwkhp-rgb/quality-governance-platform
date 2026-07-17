"""Unit tests for case_risk_links junction helpers."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic/versions/20260719_case_risk_jn.py"


def test_migration_file_exists():
    assert MIGRATION_PATH.is_file()


def test_migration_revision_id_within_32_chars():
    body = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'revision: str = "20260719_case_risk_jn"' in body
    assert len("20260719_case_risk_jn") <= 32


def test_migration_chains_from_rls_gt_exp():
    body = MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'down_revision: Union[str, Sequence[str], None] = "20260719_rls_gt_exp"' in body


def test_migration_defines_case_risk_links_table():
    body = MIGRATION_PATH.read_text(encoding="utf-8")
    assert '"case_risk_links"' in body or "'case_risk_links'" in body
    assert "uq_case_risk_links_tenant_case_risk" in body
    assert "case_type" in body
    assert "tenant_id" in body


def test_case_risk_link_model_registered():
    from src.domain.models.risk_register import CaseRiskLink

    assert CaseRiskLink.__tablename__ == "case_risk_links"


def test_parse_linked_risk_ids_in_case_risk_links_module():
    from src.domain.services.case_risk_links import parse_linked_risk_ids, sync_case_risk_links_from_csv

    assert parse_linked_risk_ids("1, 2,2,x,3") == [1, 2, 3]
    assert sync_case_risk_links_from_csv is not None


def test_case_type_href_and_list_helper_exported():
    from src.domain.services.case_risk_links import case_type_href, list_case_links_for_risk

    assert case_type_href("incident", 1) == "/incidents/1"
    assert list_case_links_for_risk is not None
