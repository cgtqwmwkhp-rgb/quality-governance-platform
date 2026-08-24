"""Unit tests for Library F-3 / L-49 anti-dupe CI gate."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
GATE_PATH = REPO_ROOT / "scripts" / "governance" / "library" / "anti_dupe_gate.py"
BASELINE_PATH = REPO_ROOT / "docs/governance/library_anti_dupe_baseline.json"


def _load_gate():
    spec = importlib.util.spec_from_file_location("qgp_library_anti_dupe_gate_test", GATE_PATH)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


gate = _load_gate()


def test_anti_dupe_gate_passes_on_current_orm() -> None:
    critical, _advisory, stats = gate.audit()
    assert critical == [], critical
    assert stats["models"] > 0
    assert stats["file_home_tables_observed"] >= 5


def test_baseline_file_exists_and_lists_known_homes() -> None:
    assert BASELINE_PATH.is_file()
    payload = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))
    homes = payload["file_home_tables"]
    assert "documents" in homes
    assert "document_versions" in homes
    assert "evidence_assets" in homes
    assert "src/domain/services/href_registry.py" in payload["document_url_builder_allowlist"]


def test_new_file_home_table_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    real_collect = gate._collect_models

    class _FakeCol:
        pass

    class _FakeTable:
        c = {"id": _FakeCol(), "file_path": _FakeCol(), "storage_key": _FakeCol()}
        columns = []

    class FakeFileHome:
        __name__ = "FakeFileHome"
        __tablename__ = "zzz_f3_parallel_document_store"
        __table__ = _FakeTable()

    monkeypatch.setattr(gate, "_collect_models", lambda: [*real_collect(), FakeFileHome])
    critical, _advisory, _stats = gate.audit()
    assert any("zzz_f3_parallel_document_store" in msg for msg in critical)
    assert any("file_path" in msg or "storage_key" in msg for msg in critical)


def test_new_coverage_twin_table_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    real_collect = gate._collect_models

    class _FakeTable:
        c = {"id": object()}
        columns = []

    class FakeCoverageClaims:
        __name__ = "FakeCoverageClaims"
        __tablename__ = "document_coverage_claims"
        __table__ = _FakeTable()

    monkeypatch.setattr(gate, "_collect_models", lambda: [*real_collect(), FakeCoverageClaims])
    critical, _advisory, _stats = gate.audit()
    assert any("document_coverage_claims" in msg for msg in critical)
    assert any("coverage" in msg.lower() for msg in critical)


def test_new_framework_table_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    real_collect = gate._collect_models

    class _FakeTable:
        c = {"id": object()}
        columns = []

    class FakeFrameworks:
        __name__ = "FakeFrameworks"
        __tablename__ = "frameworks"
        __table__ = _FakeTable()

    monkeypatch.setattr(gate, "_collect_models", lambda: [*real_collect(), FakeFrameworks])
    critical, _advisory, _stats = gate.audit()
    assert any("__tablename__='frameworks'" in msg or "frameworks" in msg for msg in critical)


def test_documents_like_freetext_column_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    from sqlalchemy import Column, Integer, MetaData, String, Table

    real_collect = gate._collect_models
    metadata = MetaData()
    fake_table = Table(
        "documents",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("iso_clause", String(50)),
    )

    class FakeDocumentsWithIso:
        __name__ = "FakeDocumentsWithIso"
        __tablename__ = "documents"
        __table__ = fake_table

    # Replace real Document with a poisoned twin so we observe the column check.
    def _collect() -> list[type]:
        models = [m for m in real_collect() if m.__tablename__ != "documents"]
        return [*models, FakeDocumentsWithIso]

    monkeypatch.setattr(gate, "_collect_models", _collect)
    critical, _advisory, _stats = gate.audit()
    assert any("iso_clause" in msg for msg in critical)
    assert any("documents-like" in msg.lower() or "free-text" in msg.lower() for msg in critical)


def test_spa_document_url_outside_allowlist_fails(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    offender = tmp_path / "src" / "domain" / "services" / "rogue_doc_links.py"
    offender.parent.mkdir(parents=True)
    offender.write_text(
        'def link(doc_id: int) -> str:\n    return f"/documents/{doc_id}"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(gate, "REPO_ROOT", tmp_path)
    # Point baseline load at the real baseline (audit still needs models).
    # Only exercise the URL scanner in isolation:
    findings = gate._scan_document_url_builders(
        {"src/domain/services/href_registry.py"},
    )
    assert any("rogue_doc_links.py" in msg for msg in findings)


def test_href_registry_url_builder_is_allowed() -> None:
    findings = gate._scan_document_url_builders(
        {"src/domain/services/href_registry.py"},
    )
    assert not any("href_registry.py" in msg for msg in findings)


def test_cli_main_exits_zero_on_current_tree() -> None:
    assert gate.main() == 0
