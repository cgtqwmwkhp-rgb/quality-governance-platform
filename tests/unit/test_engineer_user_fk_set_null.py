"""EMP-FK: Engineer.user_id ON DELETE SET NULL (model + migration surface)."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy.schema import ForeignKey

from src.domain.models.engineer import Engineer

MIGRATION = Path("alembic/versions/20260726_engineer_user_fk_set_null.py")


def test_engineer_user_id_fk_ondelete_set_null():
    user_col = Engineer.__table__.c.user_id
    assert user_col.nullable is True
    fks = list(user_col.foreign_keys)
    assert any(fk.column.table.name == "users" for fk in fks)
    assert any(fk.ondelete and fk.ondelete.upper() == "SET NULL" for fk in fks)


def test_engineer_user_id_fk_targets_users():
    user_fk: ForeignKey = next(iter(Engineer.__table__.c.user_id.foreign_keys))
    assert user_fk.column.table.name == "users"
    assert user_fk.column.name == "id"


def test_emp_fk_harden_migration_scaffold():
    assert MIGRATION.is_file()
    text = MIGRATION.read_text()
    assert 'revision: str = "20260726_emp_user_fk"' in text
    assert "20260725_eng_qgp_ov" in text
    assert 'ondelete="SET NULL"' in text or "ondelete='SET NULL'" in text
    assert 'ondelete="CASCADE"' in text or "ondelete='CASCADE'" in text
    assert "fk_engineers_user_id" in text
    assert "drop_constraint" in text
    assert "create_foreign_key" in text
