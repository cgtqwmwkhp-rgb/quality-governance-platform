"""WI-1 / L-26–28: CEL harden + standards scheme converge.

Covers ORM index declarations, migration ↔ ORM DDL lockstep, SQLite
soft-delete → re-link, covers+evidences coexistence, ALL_CLAUSES catalogue
coverage planning, and the D15 rule that AI auto-confirm cannot stamp
confirmed_by.
"""

from __future__ import annotations

import importlib.util
import re
import sqlite3
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.schema import CreateIndex

from src.domain.models.compliance_evidence import (
    ComplianceEvidenceLink,
    EvidenceCoverKind,
    EvidenceLinkMethod,
    EvidenceLinkStatus,
)
from src.domain.models.standard import StandardKind
from src.domain.models.standard import Clause
from src.domain.services.clause_catalogue_seed import (
    SCHEME_STANDARD_SPECS,
    build_clause_catalogue_rows,
    build_iso_standard_upserts,
    build_scheme_standard_upserts,
    catalogue_keys,
    match_iso_standard_row,
)
from src.domain.services.governed_knowledge_service import GovernedKnowledgeService, resolve_link_status
from src.domain.services.iso_compliance_service import ALL_CLAUSES, ISOStandard

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION_PATH = REPO_ROOT / "alembic" / "versions" / "20261030_lib_wi1_cel_harden_scheme.py"
REVISION = "20261030_lib_wi1_cel"
CEL_INDEX = "ux_cel_tenant_entity_clause_cover_live"
CEL_PREDICATE = "deleted_at IS NULL"
CLAUSE_INDEX = "ux_clauses_catalogue_key"
CLAUSE_PREDICATE = "catalogue_key IS NOT NULL"


def _load_migration() -> ModuleType:
    import alembic

    if not hasattr(alembic, "op"):
        alembic.op = SimpleNamespace(get_bind=lambda: None)  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location("qgp_lib_wi1_cel_migration", MIGRATION_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


migration = _load_migration()


def _normalise(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def _cel_index() -> sa.Index:
    for index in ComplianceEvidenceLink.__table__.indexes:
        if index.name == CEL_INDEX:
            return index
    raise AssertionError(f"{CEL_INDEX} is not declared on ComplianceEvidenceLink")


def _clause_index() -> sa.Index:
    for index in Clause.__table__.indexes:
        if index.name == CLAUSE_INDEX:
            return index
    raise AssertionError(f"{CLAUSE_INDEX} is not declared on Clause")


def test_cover_kind_and_standard_kind_enums() -> None:
    assert {m.value for m in EvidenceCoverKind} == {"covers", "evidences"}
    assert {m.value for m in StandardKind} == {"iso", "scheme"}


def test_cel_partial_unique_declared_with_cover_kind() -> None:
    idx = _cel_index()
    assert idx.unique is True
    cols = [c.name for c in idx.columns]
    assert cols == ["tenant_id", "entity_type", "entity_id", "clause_id", "cover_kind"]
    assert idx.dialect_options["postgresql"]["where"].text == CEL_PREDICATE
    assert idx.dialect_options["sqlite"]["where"].text == CEL_PREDICATE


def test_old_cel_unique_index_removed_from_model() -> None:
    names = {idx.name for idx in ComplianceEvidenceLink.__table__.indexes}
    assert "ix_cel_tenant_entity_clause" not in names
    assert CEL_INDEX in names


def test_clause_catalogue_key_partial_unique_declared() -> None:
    idx = _clause_index()
    assert idx.unique is True
    assert [c.name for c in idx.columns] == ["catalogue_key"]
    assert idx.dialect_options["postgresql"]["where"].text == CLAUSE_PREDICATE
    assert idx.dialect_options["sqlite"]["where"].text == CLAUSE_PREDICATE


def test_migration_chains_from_ns_wf_review_cycle_head() -> None:
    assert migration.revision == REVISION
    assert len(REVISION) <= 32
    assert migration.down_revision == "20261029_lib_ns_wf_review_cycle"
    assert migration.NEW_CEL_UNIQUE == CEL_INDEX
    assert migration.CEL_UNIQUE_PREDICATE == CEL_PREDICATE
    assert migration.CLAUSE_CATALOGUE_UNIQUE == CLAUSE_INDEX


def test_migration_cel_ddl_matches_orm_declaration() -> None:
    compiled = _normalise(str(CreateIndex(_cel_index()).compile(dialect=postgresql.dialect())))
    assert _normalise(migration.CEL_UNIQUE_DDL) == compiled, (
        "migration CEL_UNIQUE_DDL and the ORM declaration have diverged:\n"
        f"  migration: {_normalise(migration.CEL_UNIQUE_DDL)}\n"
        f"  model:     {compiled}"
    )


def test_migration_clause_catalogue_ddl_matches_orm_declaration() -> None:
    compiled = _normalise(str(CreateIndex(_clause_index()).compile(dialect=postgresql.dialect())))
    assert _normalise(migration.CLAUSE_CATALOGUE_DDL) == compiled


@pytest.mark.parametrize("dialect_name", ["postgresql", "sqlite"])
def test_cel_partial_predicate_on_both_dialects(dialect_name: str) -> None:
    dialect = postgresql.dialect() if dialect_name == "postgresql" else sqlite.dialect()
    ddl = _normalise(str(CreateIndex(_cel_index()).compile(dialect=dialect)))
    assert "WHERE" in ddl
    assert "deleted_at IS NULL" in ddl
    assert "cover_kind" in ddl


def test_sqlite_soft_delete_frees_unique_slot_for_relink() -> None:
    ddl = str(CreateIndex(_cel_index()).compile(dialect=sqlite.dialect()))
    connection = sqlite3.connect(":memory:")
    connection.executescript("""
        CREATE TABLE compliance_evidence_links (
            id INTEGER PRIMARY KEY,
            tenant_id INT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT NOT NULL,
            clause_id TEXT NOT NULL,
            cover_kind TEXT NOT NULL,
            deleted_at TEXT
        );
        """)
    connection.execute(ddl)

    insert = (
        "INSERT INTO compliance_evidence_links "
        "(id, tenant_id, entity_type, entity_id, clause_id, cover_kind, deleted_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)"
    )
    connection.execute(insert, (1, 1, "document", "42", "9001-7.2", "evidences", None))

    with pytest.raises(sqlite3.IntegrityError):
        connection.execute(insert, (2, 1, "document", "42", "9001-7.2", "evidences", None))

    connection.execute("UPDATE compliance_evidence_links SET deleted_at = '2026-08-09T00:00:00Z' WHERE id = 1")
    connection.execute(insert, (3, 1, "document", "42", "9001-7.2", "evidences", None))
    connection.execute(insert, (4, 1, "document", "42", "9001-7.2", "covers", None))

    total = connection.execute("SELECT count(*) FROM compliance_evidence_links").fetchone()[0]
    live = connection.execute("SELECT count(*) FROM compliance_evidence_links WHERE deleted_at IS NULL").fetchone()[0]
    assert total == 3
    assert live == 2


def test_all_clauses_catalogue_keys_are_unique_and_non_empty() -> None:
    keys = catalogue_keys()
    assert len(keys) == len(ALL_CLAUSES)
    assert len(keys) == len(set(keys))
    assert all(keys)


def test_iso_and_scheme_standard_upsert_plans() -> None:
    inserts, found = build_iso_standard_upserts([])
    assert found == {}
    assert {row["code"] for row in inserts} == {"ISO9001", "ISO14001", "ISO45001", "ISO27001"}
    assert all(row["kind"] == "iso" for row in inserts)

    schemes = build_scheme_standard_upserts([])
    assert {row["code"] for row in schemes} == {s["code"] for s in SCHEME_STANDARD_SPECS}
    assert all(row["kind"] == "scheme" for row in schemes)

    existing = [{"id": 9, "code": "ISO 9001:2015", "name": "QMS", "full_name": "ISO 9001"}]
    inserts2, found2 = build_iso_standard_upserts(existing)
    assert found2[ISOStandard.ISO_9001] == 9
    assert all(row["code"] != "ISO9001" for row in inserts2)


def test_build_clause_catalogue_rows_cover_every_all_clauses_id() -> None:
    iso_to_id = {
        ISOStandard.ISO_9001: 1,
        ISOStandard.ISO_14001: 2,
        ISOStandard.ISO_45001: 3,
        ISOStandard.ISO_27001: 4,
    }
    rows = build_clause_catalogue_rows(iso_to_id)
    assert {row["catalogue_key"] for row in rows} == set(catalogue_keys())
    assert all(row["standard_id"] in {1, 2, 3, 4} for row in rows)


def test_match_iso_standard_row_ignores_scheme_shells() -> None:
    assert match_iso_standard_row({"code": "UVDB_B2", "name": "UVDB", "full_name": "Verify B2"}) is None
    assert match_iso_standard_row({"code": "ISO45001", "name": "OH&S", "full_name": ""}) == ISOStandard.ISO_45001


def test_resolve_link_status_auto_confirm_does_not_imply_human_confirmer() -> None:
    status, auto_applied = resolve_link_status(0.99, "policy")
    assert status == EvidenceLinkStatus.CONFIRMED
    assert auto_applied is True


@pytest.mark.asyncio
async def test_ai_persist_mapping_clears_confirmer_on_auto_apply(monkeypatch: pytest.MonkeyPatch) -> None:
    db = AsyncMock()
    result = SimpleNamespace(scalar_one_or_none=lambda: None)
    db.execute = AsyncMock(return_value=result)
    db.add = AsyncMock()

    async def _no_pin(*_args, **_kwargs):
        return None

    monkeypatch.setattr(
        "src.domain.services.cel_version_pin.pin_evidence_link_document_version",
        _no_pin,
    )

    service = GovernedKnowledgeService()
    service._log_ai_decision = AsyncMock()  # type: ignore[method-assign]

    mapping = SimpleNamespace(
        clause_id="9001-7.2",
        scheme="iso9001",
        confidence=0.99,
        rationale="auto",
        title="Policy",
    )
    user = SimpleNamespace(id=7, email="ai-caller@example.com")

    link = await service._persist_mapping(
        db,
        tenant_id=1,
        entity_type="document",
        entity_id="55",
        mapping=mapping,
        doc_type="policy",
        user=user,
    )
    assert link.auto_applied is True
    assert link.status == EvidenceLinkStatus.CONFIRMED
    assert link.confirmed_by_id is None
    assert link.confirmed_at is None
    assert link.cover_kind == EvidenceCoverKind.EVIDENCES


def test_standard_and_cel_defaults() -> None:
    assert StandardKind.ISO.value == "iso"
    assert EvidenceCoverKind.EVIDENCES.value == "evidences"
    assert EvidenceLinkMethod.MANUAL.value == "manual"
