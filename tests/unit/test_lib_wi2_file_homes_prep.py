"""WI-2 / L-32 prep: file-homes inventory + migrate dry-run (no alembic head).

Pins the read-only prep lane that may land while WI-1 (#1687) still owns
alembic. These tests must **not** import a live
``alembic/versions/*wi2*`` revision.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY = REPO_ROOT / "scripts/governance/library/file_homes_inventory.py"
PREP = REPO_ROOT / "scripts/governance/library/file_homes_migrate_prep.py"
DESIGN = REPO_ROOT / "docs/governance/library-file-homes-l32.md"
DRAFT = (
    REPO_ROOT
    / "docs/governance/drafts"
    / "alembic_DRAFT_after_wi1_20261031_lib_wi2_file_homes_documents_id.py.draft"
)
WI1_HEAD = "20261030_lib_wi1_cel"
VERSIONS = REPO_ROOT / "alembic" / "versions"


def _load(path: Path, name: str):
    import importlib.util
    import sys

    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    # Dataclass evaluation needs the module registered before exec_module.
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


inventory = _load(INVENTORY, "qgp_lib_wi2_file_homes_inventory")
prep = _load(PREP, "qgp_lib_wi2_file_homes_migrate_prep")


def test_design_note_and_draft_exist() -> None:
    assert DESIGN.is_file()
    assert DRAFT.is_file()
    text = DRAFT.read_text(encoding="utf-8")
    assert WI1_HEAD in text
    assert 'down_revision' in text
    assert "20261030_lib_wi1_cel" in text
    assert "carbon_evidence" in text
    assert "evidence_assets" in text
    assert "NOT AN ACTIVE ALEMBIC" in text or "DRAFT" in text


def test_no_live_wi2_alembic_under_versions() -> None:
    """Conflict avoidance: WI-1 owns alembic until LIVE — no competing head."""
    offenders = [
        p
        for p in VERSIONS.rglob("*")
        if p.is_file()
        and "wi2" in p.name.lower()
        and (p.suffix == ".py" or "file_home" in p.name.lower())
    ]
    assert offenders == [], f"live WI-2 alembic must stay draft-only: {offenders}"


def test_draft_is_not_python_module_under_versions() -> None:
    assert DRAFT.suffixes[-2:] == [".py", ".draft"] or DRAFT.name.endswith(".py.draft")
    assert "alembic/versions" not in str(DRAFT.relative_to(REPO_ROOT))


def test_inventory_reports_three_homes() -> None:
    report = inventory.inventory_report()
    tables = {h["table"] for h in report["homes"]}
    assert tables == {"carbon_evidence", "uvdb_audit_response", "evidence_assets"}
    assert report["summary"]["missing"] == []
    assert "carbon_evidence" in report["summary"]["needs_document_fk"]
    assert "evidence_assets" in report["summary"]["needs_document_fk"]
    assert "uvdb_audit_response" in report["summary"]["needs_presented_normalise"]


def test_inventory_cli_json_exit_zero() -> None:
    assert inventory.main(["--json"]) == 0


def test_inventory_sees_file_columns_on_carbon_and_ea() -> None:
    homes = {h.table: h for h in inventory.inventory_homes()}
    assert "storage_key" in homes["carbon_evidence"].file_home_columns
    assert "file_path" in homes["carbon_evidence"].file_home_columns
    assert "storage_key" in homes["evidence_assets"].file_home_columns
    assert "documents_presented" in homes["uvdb_audit_response"].presented_columns
    assert homes["carbon_evidence"].existing_document_fks == []
    assert homes["evidence_assets"].existing_document_fks == []


def test_migrate_prep_rejects_apply() -> None:
    assert prep.main(["--apply", "--demo"]) == 2


def test_migrate_prep_requires_input() -> None:
    assert prep.main([]) == 2


def test_migrate_prep_demo_matches_expected() -> None:
    report = prep.build_report(prep.demo_payload())
    report.summarise()
    assert report.counters["carbon_matched"] == 1
    assert report.counters["carbon_unmatched"] == 1
    assert report.counters["uvdb_matched"] >= 2
    assert report.counters["uvdb_already_shaped"] == 1
    assert report.counters["uvdb_unmatched"] >= 1
    assert report.counters["ea_matched"] == 1
    assert report.counters["ea_unmatched"] == 1
    assert any("20261030_lib_wi1_cel" in item for item in report.deferred)


def test_uvdb_projection_shape() -> None:
    indexes = prep.index_documents(
        [{"id": 50, "tenant_id": 1, "file_name": "Site Induction.pdf", "checksum_sha256": "x"}]
    )
    plan = prep.normalise_presented_element(
        "Site Induction.pdf",
        tenant_id=1,
        indexes=indexes,
        response_id=7,
    )
    assert plan.status == "matched"
    assert plan.projected == {"document_id": 50, "label": "Site Induction.pdf"}


def test_uvdb_unmatched_keeps_null_document_id() -> None:
    indexes = prep.index_documents([])
    plan = prep.normalise_presented_element(
        "Unknown.pdf",
        tenant_id=1,
        indexes=indexes,
        response_id=7,
    )
    assert plan.status == "unmatched"
    assert plan.projected == {"document_id": None, "label": "Unknown.pdf"}


def test_prep_scripts_contain_no_mutating_sql_literals() -> None:
    """Same contract as tenant-scope inventories — planning only."""
    for path in (INVENTORY, PREP):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        literals = [
            node.value.upper()
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant) and isinstance(node.value, str)
        ]
        for literal in literals:
            # Allow the guard-token tuple itself and human deferred notes.
            if literal.strip() in {
                "UPDATE",
                "INSERT INTO",
                "DELETE FROM",
                "ALTER TABLE",
                "DROP TABLE",
                "TRUNCATE TABLE",
            }:
                continue
            for statement in (
                "UPDATE ",
                "INSERT INTO",
                "DELETE FROM",
                "ALTER TABLE",
                "DROP TABLE",
                "TRUNCATE TABLE",
            ):
                assert statement not in literal, f"{path.name} embeds {statement!r}"


def test_prep_cli_demo_json() -> None:
    assert prep.main(["--demo", "--json"]) == 0


def test_design_mentions_conflict_hold() -> None:
    text = DESIGN.read_text(encoding="utf-8")
    assert "20261030_lib_wi1_cel" in text
    assert "dual-head" in text.lower() or "Do not dual-head" in text
    assert "carbon_evidence" in text
    assert "documents_presented" in text
    assert "evidence_assets" in text


def test_from_json_roundtrip(tmp_path: Path) -> None:
    payload = prep.demo_payload()
    path = tmp_path / "export.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert prep.main(["--from-json", str(path), "--json"]) == 0
