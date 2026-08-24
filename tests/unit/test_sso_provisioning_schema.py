"""Unit tests for SSO provisioning-request schema (model + migrations).

Schema/model only — no service, no API. Negative cases pin the load-bearing
constraints that later PRs will rely on: ``tenant_id`` NOT NULL, partial unique
indexes with both dialect predicates, RLS hardening registry membership, and
status / match_basis check constraints.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateIndex, CreateTable

from src.domain.models.sso_provisioning import SSOProvisioningMatchBasis, SSOProvisioningRequest, SSOProvisioningStatus
from src.infrastructure.middleware.tenant_context import RLS_TABLES, TENANT_ISOLATION_PREDICATE

REPO_ROOT = Path(__file__).resolve().parents[2]
CREATE_MIGRATION_PATH = REPO_ROOT / "alembic" / "versions" / "20261012_sso_provisioning_requests.py"
RLS_MIGRATION_PATH = REPO_ROOT / "alembic" / "versions" / "20261012_rls_sso_provisioning.py"


def _load_migration(path: Path, module_name: str) -> ModuleType:
    """Load a migration by path; ``alembic/versions`` is not an importable package.

    ``alembic.op`` is stubbed because the repo ships an empty ``alembic/__init__.py``
    that shadows the installed distribution once the repo root is on ``sys.path``.
    """
    import alembic

    if not hasattr(alembic, "op"):
        alembic.op = SimpleNamespace(get_bind=lambda: None)  # type: ignore[attr-defined]

    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


create_migration = _load_migration(CREATE_MIGRATION_PATH, "qgp_sso_prov_create_migration")
rls_migration = _load_migration(RLS_MIGRATION_PATH, "qgp_sso_prov_rls_migration")


def _normalise(sql: str) -> str:
    return re.sub(r"\s+", " ", sql).strip()


def _index_by_name(name: str) -> sa.Index:
    for index in SSOProvisioningRequest.__table__.indexes:
        if index.name == name:
            return index
    raise AssertionError(f"{name} is not declared on SSOProvisioningRequest")


# ---------------------------------------------------------------------------
# Model surface
# ---------------------------------------------------------------------------


def test_tablename_and_classification() -> None:
    assert SSOProvisioningRequest.__tablename__ == "sso_provisioning_requests"
    assert SSOProvisioningRequest.__data_classification__ == "C3_CONFIDENTIAL"


def test_tenant_id_is_not_null() -> None:
    """A nullable tenant_id would fail validate_tenant_id_not_null and break RLS."""
    column = SSOProvisioningRequest.__table__.c.tenant_id
    assert column.nullable is False
    assert any(str(fk.target_fullname).startswith("tenants") for fk in column.foreign_keys)


def test_status_enum_values() -> None:
    assert {m.value for m in SSOProvisioningStatus} == {
        "pending",
        "approved",
        "rejected",
        "expired",
        "superseded",
    }


def test_match_basis_enum_values() -> None:
    assert {m.value for m in SSOProvisioningMatchBasis} == {
        "deployment_default",
        "email_domain_allowlist",
    }


def test_check_constraints_cover_status_and_match_basis() -> None:
    names = {c.name for c in SSOProvisioningRequest.__table__.constraints if isinstance(c, sa.CheckConstraint)}
    assert "ck_sso_provisioning_requests_status" in names
    assert "ck_sso_provisioning_requests_match_basis" in names
    assert "ck_sso_provisioning_requests_attempt_count" in names


def test_required_columns_are_not_null() -> None:
    table = SSOProvisioningRequest.__table__
    for name in (
        "email",
        "first_name",
        "last_name",
        "reference",
        "status",
        "match_basis",
        "attempt_count",
        "first_attempt_at",
        "last_attempt_at",
        "expires_at",
    ):
        assert table.c[name].nullable is False, name


def test_optional_decision_columns_are_nullable() -> None:
    table = SSOProvisioningRequest.__table__
    for name in (
        "azure_oid",
        "job_title",
        "department",
        "decided_at",
        "decided_by_id",
        "decision_reason",
        "created_user_id",
    ):
        assert table.c[name].nullable is True, name


def test_reference_is_globally_unique() -> None:
    column = SSOProvisioningRequest.__table__.c.reference
    # unique=True on the column yields a unique Index, not necessarily UniqueConstraint
    unique_indexes = [
        idx
        for idx in SSOProvisioningRequest.__table__.indexes
        if idx.unique and list(idx.columns.keys()) == ["reference"]
    ]
    assert column.unique or unique_indexes, "reference must be uniquely indexed"


# ---------------------------------------------------------------------------
# Partial unique indexes (model ↔ migration parity)
# ---------------------------------------------------------------------------


def test_pending_email_index_has_both_dialect_predicates() -> None:
    index = _index_by_name("ux_sso_prov_pending_email")
    assert index.unique is True
    assert index.dialect_options["postgresql"]["where"].text == "status = 'pending'"
    assert index.dialect_options["sqlite"]["where"].text == "status = 'pending'"


def test_pending_oid_index_has_both_dialect_predicates() -> None:
    index = _index_by_name("ux_sso_prov_pending_oid")
    assert index.unique is True
    where_pg = index.dialect_options["postgresql"]["where"].text
    where_sqlite = index.dialect_options["sqlite"]["where"].text
    assert "status = 'pending'" in where_pg
    assert "azure_oid IS NOT NULL" in where_pg
    assert where_pg == where_sqlite


def test_pending_email_index_ddl_matches_migration_literal() -> None:
    compiled = _normalise(
        str(CreateIndex(_index_by_name("ux_sso_prov_pending_email")).compile(dialect=postgresql.dialect()))
    )
    assert _normalise(create_migration.PENDING_EMAIL_INDEX_DDL) == compiled


def test_pending_oid_index_ddl_matches_migration_literal() -> None:
    compiled = _normalise(
        str(CreateIndex(_index_by_name("ux_sso_prov_pending_oid")).compile(dialect=postgresql.dialect()))
    )
    assert _normalise(create_migration.PENDING_OID_INDEX_DDL) == compiled


def test_tenant_status_index_is_non_unique() -> None:
    index = _index_by_name("ix_sso_prov_tenant_status")
    assert index.unique is False
    assert list(index.columns.keys()) == ["tenant_id", "status"]


# ---------------------------------------------------------------------------
# Migration chain + RLS hardening
# ---------------------------------------------------------------------------


def test_create_migration_chains_from_notif_dedupe() -> None:
    assert create_migration.revision == "20261012_sso_prov_req"
    assert create_migration.down_revision == "20260914_cs_notif_dedupe"


def test_rls_migration_chains_from_create() -> None:
    assert rls_migration.revision == "20261012_rls_sso_prov"
    assert rls_migration.down_revision == "20261012_sso_prov_req"


def test_rls_adopt_tables_and_predicate() -> None:
    assert rls_migration.ADOPT_TABLES == ("sso_provisioning_requests",)
    assert rls_migration.HARDENED_PREDICATE == TENANT_ISOLATION_PREDICATE


def test_table_is_registered_in_rls_tables() -> None:
    assert "sso_provisioning_requests" in RLS_TABLES


def test_create_migration_forces_tenant_id_not_null_in_ddl() -> None:
    """Negative: a CREATE TABLE that left tenant_id nullable would be a CRITICAL lint fail."""
    source = CREATE_MIGRATION_PATH.read_text(encoding="utf-8")
    assert 'sa.Column("tenant_id", sa.Integer(), nullable=False)' in source
    assert "nullable=True)" not in source.split("tenant_id", 1)[1].split("\n", 1)[0]


def test_create_migration_has_no_users_status_column() -> None:
    """Guardrail: this PR must not touch users.provisioning_status / similar."""
    source = CREATE_MIGRATION_PATH.read_text(encoding="utf-8")
    assert "users" not in source.lower() or 'ForeignKeyConstraint(["decided_by_id"], ["users.id"])' in source
    assert "alter table users" not in source.lower()
    assert "provisioning_status" not in source.lower()


def test_orm_create_table_emits_tenant_id_not_null() -> None:
    ddl = str(CreateTable(SSOProvisioningRequest.__table__).compile(dialect=postgresql.dialect()))
    assert re.search(r"tenant_id\s+INTEGER\s+NOT\s+NULL", ddl, re.IGNORECASE)


def test_validate_tenant_id_not_null_passes_with_model() -> None:
    from scripts.validate_tenant_id_not_null import audit

    critical, _advisory, stats = audit()
    assert critical == []
    assert stats["models"] > 0
    # And the new table is among the owned NOT NULL set
    tables = {
        m.__tablename__
        for m in __import__("scripts.validate_tenant_id_not_null", fromlist=["_collect_models"])._collect_models()
    }
    assert "sso_provisioning_requests" in tables


def test_nullable_tenant_id_on_this_model_would_be_critical(monkeypatch: pytest.MonkeyPatch) -> None:
    """Negative: if tenant_id were nullable, the C-01 lint must CRITICAL it."""
    import scripts.validate_tenant_id_not_null as mod

    real_collect = mod._collect_models

    class _FakeCol:
        nullable = True

    class _FakeTable:
        c = {"tenant_id": _FakeCol()}

    class FakeNullableSSO:
        __name__ = "FakeNullableSSO"
        __tablename__ = "sso_provisioning_requests_nullable_fake"
        __table__ = _FakeTable()

    def _collect_with_fake() -> list[type]:
        return [*real_collect(), FakeNullableSSO]

    monkeypatch.setattr(mod, "_collect_models", _collect_with_fake)
    critical, _advisory, _stats = mod.audit()
    assert any("sso_provisioning_requests_nullable_fake" in msg for msg in critical)


def test_exported_from_models_all() -> None:
    import src.domain.models as models_pkg

    assert "SSOProvisioningRequest" in models_pkg.__all__
    assert models_pkg.SSOProvisioningRequest is SSOProvisioningRequest
