"""WI-2 / L-32: file-homes inventory + migrate dry-run.

Pins the read-only prep lane. WI-1 is now LIVE and WI-2's schema has been
promoted, so the assertions that held the prep phase open — "no live WI-2
alembic", "carbon_evidence still needs a document_id FK" — are inverted here to
pin the *post*-promotion state instead. They are not relaxed: each one now
asserts the stronger fact that the link landed.
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
DRAFTS_DIR = REPO_ROOT / "docs/governance/drafts"
WI1_HEAD = "20261030_lib_wi1_cel"
WI2_HEAD = "20261031_lib_wi2_homes"
MIGRATION = REPO_ROOT / "alembic/versions/20261031_lib_wi2_file_homes_documents_id.py"
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


def test_design_note_and_live_migration_exist() -> None:
    assert DESIGN.is_file()
    assert MIGRATION.is_file(), "WI-2 schema must be a live revision now WI-1 is LIVE"
    text = MIGRATION.read_text(encoding="utf-8")
    assert f'revision: str = "{WI2_HEAD}"' in text
    assert f'down_revision: Union[str, Sequence[str], None] = "{WI1_HEAD}"' in text
    assert "carbon_evidence" in text
    assert "evidence_assets" in text


def test_exactly_one_wi2_revision_under_versions() -> None:
    """The draft was promoted, not copied: one file may declare this revision."""
    offenders = [
        p for p in VERSIONS.rglob("*.py") if p.is_file() and "wi2" in p.name.lower() and "__pycache__" not in p.parts
    ]
    assert offenders == [MIGRATION], f"expected exactly the promoted WI-2 revision, found {offenders}"


def test_prep_draft_retired_after_promotion() -> None:
    """A ``.py.draft`` twin of a live revision is a second source of truth.

    While WI-1 owned alembic the draft was the whole point. Now that the real
    revision exists, keeping a file that also declares ``revision =
    "20261031_lib_wi2_homes"`` invites the two to drift, and drift in a migration
    id is not a cosmetic problem.
    """
    if not DRAFTS_DIR.is_dir():
        return
    strays = [p for p in DRAFTS_DIR.rglob("*") if p.is_file() and WI2_HEAD in p.read_text(encoding="utf-8")]
    assert strays == [], f"retire the promoted WI-2 draft: {strays}"


def test_inventory_reports_three_homes() -> None:
    report = inventory.inventory_report()
    tables = {h["table"] for h in report["homes"]}
    assert tables == {"carbon_evidence", "uvdb_audit_response", "evidence_assets"}
    assert report["summary"]["missing"] == []
    # Post-promotion: both blob homes carry the link, so nothing still needs it.
    assert report["summary"]["needs_document_fk"] == []
    assert set(report["summary"]["already_linked"]) == {"carbon_evidence", "evidence_assets"}
    assert "uvdb_audit_response" in report["summary"]["needs_presented_normalise"]
    assert report["alembic_head"] == WI2_HEAD


def test_inventory_cli_json_exit_zero() -> None:
    assert inventory.main(["--json"]) == 0


def test_inventory_sees_file_columns_on_carbon_and_ea() -> None:
    homes = {h.table: h for h in inventory.inventory_homes()}
    # The occurrence blobs stay put — WI-2 links, it does not move or drop files.
    assert "storage_key" in homes["carbon_evidence"].file_home_columns
    assert "file_path" in homes["carbon_evidence"].file_home_columns
    assert "storage_key" in homes["evidence_assets"].file_home_columns
    assert "documents_presented" in homes["uvdb_audit_response"].presented_columns
    assert homes["carbon_evidence"].existing_document_fks == ["document_id"]
    assert homes["evidence_assets"].existing_document_fks == ["document_id"]
    assert homes["uvdb_audit_response"].existing_document_fks == []


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
    # The schema and the ORM columns are no longer deferred; the honest remainder
    # is the backfill and the F-3 shrink, which WI-2 deliberately did not do.
    assert not any(WI1_HEAD in item for item in report.deferred)
    assert any("F-3 allowlist shrink" in item for item in report.deferred)
    assert any("Backfill" in item for item in report.deferred)


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


def test_design_records_the_live_head_and_all_three_homes() -> None:
    text = DESIGN.read_text(encoding="utf-8")
    assert WI1_HEAD in text
    assert WI2_HEAD in text
    assert "carbon_evidence" in text
    assert "documents_presented" in text
    assert "evidence_assets" in text


def test_from_json_roundtrip(tmp_path: Path) -> None:
    payload = prep.demo_payload()
    path = tmp_path / "export.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert prep.main(["--from-json", str(path), "--json"]) == 0
