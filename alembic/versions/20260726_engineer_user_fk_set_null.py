"""EMP-FK: engineers.user_id ON DELETE SET NULL (preserve PAMS person).

Revision ID: 20260726_emp_user_fk
Revises: 20260725_eng_qgp_ov
Create Date: 2026-07-26

Deleting a User login must not cascade-delete the Engineer/PAMS person row.
user the FK so user_id is SET NULL instead of CASCADE.
"""

from __future__ import annotations

from typing import Sequence, Union

from alembic import op
from sqlalchemy import inspect

revision: str = "20260726_emp_user_fk"
down_revision: Union[str, Sequence[str], None] = "20260725_eng_qgp_ov"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FK_NAME = "fk_engineers_user_id"
TABLE = "engineers"
COLUMN = "user_id"
REFERRED_TABLE = "users"


def _user_id_fk_names() -> list[str]:
    inspector = inspect(op.get_bind())
    if TABLE not in inspector.get_table_names():
        return []
    names: list[str] = []
    for fk in inspector.get_foreign_keys(TABLE):
        if fk.get("constrained_columns") == [COLUMN] and fk.get("referred_table") == REFERRED_TABLE:
            name = fk.get("name")
            if name:
                names.append(name)
    return names


def _recreate_user_fk(*, ondelete: str) -> None:
    for name in _user_id_fk_names():
        op.drop_constraint(name, TABLE, type_="foreignkey")
    op.create_foreign_key(
        FK_NAME,
        TABLE,
        REFERRED_TABLE,
        [COLUMN],
        ["id"],
        ondelete=ondelete,
    )


def upgrade() -> None:
    _recreate_user_fk(ondelete="SET NULL")


def downgrade() -> None:
    _recreate_user_fk(ondelete="CASCADE")
