"""Regression tests for tenant-safe Near Miss contract migrations."""

from __future__ import annotations

import ast
from pathlib import Path

from sqlalchemy import create_engine

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKFILL_MIGRATION = REPO_ROOT / "alembic/versions/20260816_nm_contract_fk.py"
REPAIR_MIGRATION = REPO_ROOT / "alembic/versions/20260826_nm_contract_tenant.py"


def _migration_value(path: Path, name: str) -> str:
    module = ast.parse(path.read_text(encoding="utf-8"))
    for node in module.body:
        if isinstance(node, ast.Assign):
            if any(isinstance(target, ast.Name) and target.id == name for target in node.targets):
                return ast.literal_eval(node.value)
    raise AssertionError(f"{name} not found in {path}")


def _connection():
    engine = create_engine("sqlite://")
    connection = engine.connect()
    connection.exec_driver_sql("""
        CREATE TABLE contracts (
            id INTEGER PRIMARY KEY,
            tenant_id INTEGER,
            code TEXT NOT NULL,
            name TEXT NOT NULL
        )
        """)
    connection.exec_driver_sql("""
        CREATE TABLE near_misses (
            id INTEGER PRIMARY KEY,
            tenant_id INTEGER,
            contract TEXT,
            contract_id INTEGER
        )
        """)
    return connection


def test_backfill_only_links_contracts_owned_by_near_miss_tenant():
    sql = _migration_value(BACKFILL_MIGRATION, "TENANT_BACKFILL_SQL")

    with _connection() as connection:
        connection.exec_driver_sql("""
            INSERT INTO contracts (id, tenant_id, code, name) VALUES
                (1, NULL, 'global-code', 'Global Contract'),
                (2, 2, 'other-code', 'Other Tenant Contract'),
                (3, 1, 'owned-code', 'Owned Contract'),
                (4, 1, 'named-code', 'Owned By Name')
            """)
        connection.exec_driver_sql("""
            INSERT INTO near_misses (id, tenant_id, contract, contract_id) VALUES
                (1, 1, 'global-code', NULL),
                (2, 1, 'other-code', NULL),
                (3, 1, 'owned-code', NULL),
                (4, 1, 'Owned By Name', NULL)
            """)

        connection.exec_driver_sql(sql)
        rows = {
            row.id: row.contract_id
            for row in connection.exec_driver_sql("SELECT id, contract_id FROM near_misses")
        }

    assert rows == {1: None, 2: None, 3: 3, 4: 4}


def test_repair_clears_existing_global_and_cross_tenant_links():
    sql = _migration_value(REPAIR_MIGRATION, "CLEAR_INVALID_CONTRACTS_SQL")

    with _connection() as connection:
        connection.exec_driver_sql("""
            INSERT INTO contracts (id, tenant_id, code, name) VALUES
                (1, NULL, 'global-code', 'Global Contract'),
                (2, 2, 'other-code', 'Other Tenant Contract'),
                (3, 1, 'owned-code', 'Owned Contract')
            """)
        connection.exec_driver_sql("""
            INSERT INTO near_misses (id, tenant_id, contract, contract_id) VALUES
                (1, 1, 'global-code', 1),
                (2, 1, 'other-code', 2),
                (3, 1, 'owned-code', 3)
            """)

        connection.exec_driver_sql(sql)
        rows = {
            row.id: row.contract_id
            for row in connection.exec_driver_sql("SELECT id, contract_id FROM near_misses")
        }

    assert rows == {1: None, 2: None, 3: 3}


def test_repair_migration_follows_current_merge_head():
    migration = REPAIR_MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20260826_nm_contract_tenant"' in migration
    assert 'down_revision: Union[str, Sequence[str], None] = "20260825_merge_chal_wit"' in migration
    assert len("20260826_nm_contract_tenant") <= 32
