"""Training matrix compliance tables (Atlas export + QGP frequency rules).

Revision ID: 20260731_train_mtx
Revises: 20260730_api_idem
Create Date: 2026-07-31
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "20260731_train_mtx"
down_revision: Union[str, Sequence[str], None] = "20260730_api_idem"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "training_matrix_imports",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("person_count", sa.Integer(), nullable=False),
        sa.Column("course_count", sa.Integer(), nullable=False),
        sa.Column("cell_count", sa.Integer(), nullable=False),
        sa.Column("nonempty_cell_count", sa.Integer(), nullable=False),
        sa.Column("expiry_without_passed_count", sa.Integer(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_training_matrix_imports_tenant_id", "training_matrix_imports", ["tenant_id"])

    op.create_table(
        "training_matrix_courses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("course_key", sa.String(length=255), nullable=False),
        sa.Column("display_name", sa.String(length=500), nullable=False),
        sa.Column("last_seen_import_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["last_seen_import_id"], ["training_matrix_imports.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "course_key", name="uq_training_matrix_course_tenant_key"),
    )
    op.create_index("ix_training_matrix_courses_tenant_id", "training_matrix_courses", ["tenant_id"])

    op.create_table(
        "training_matrix_people",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("atlas_name", sa.String(length=200), nullable=False),
        sa.Column("department", sa.String(length=200), nullable=True),
        sa.Column("engineer_id", sa.Integer(), nullable=True),
        sa.Column("last_seen_import_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["engineer_id"], ["engineers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["last_seen_import_id"], ["training_matrix_imports.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "atlas_name", name="uq_training_matrix_person_tenant_name"),
    )
    op.create_index("ix_training_matrix_people_tenant_id", "training_matrix_people", ["tenant_id"])
    op.create_index("ix_training_matrix_people_engineer_id", "training_matrix_people", ["engineer_id"])

    op.create_table(
        "training_matrix_cells",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("person_id", sa.Integer(), nullable=False),
        sa.Column("course_id", sa.Integer(), nullable=False),
        sa.Column("atlas_status", sa.String(length=40), nullable=True),
        sa.Column("passed_on", sa.Date(), nullable=True),
        sa.Column("expires_on", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["import_id"], ["training_matrix_imports.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["person_id"], ["training_matrix_people.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["course_id"], ["training_matrix_courses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "import_id",
            "person_id",
            "course_id",
            name="uq_training_matrix_cell_import_person_course",
        ),
    )
    op.create_index("ix_training_matrix_cells_tenant_id", "training_matrix_cells", ["tenant_id"])
    op.create_index("ix_training_matrix_cells_import_id", "training_matrix_cells", ["import_id"])
    op.create_index("ix_training_matrix_cells_person_id", "training_matrix_cells", ["person_id"])
    op.create_index("ix_training_matrix_cells_course_id", "training_matrix_cells", ["course_id"])

    op.create_table(
        "training_matrix_name_maps",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("atlas_name", sa.String(length=200), nullable=False),
        sa.Column("engineer_id", sa.Integer(), nullable=False),
        sa.Column("mapped_by_user_id", sa.Integer(), nullable=True),
        sa.Column("mapped_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["engineer_id"], ["engineers.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["mapped_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "atlas_name", name="uq_training_matrix_name_map_tenant_name"),
    )
    op.create_index("ix_training_matrix_name_maps_tenant_id", "training_matrix_name_maps", ["tenant_id"])
    op.create_index("ix_training_matrix_name_maps_engineer_id", "training_matrix_name_maps", ["engineer_id"])

    op.create_table(
        "training_matrix_requirements",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("match_department", sa.String(length=200), nullable=True),
        sa.Column("match_role_key", sa.String(length=100), nullable=True),
        sa.Column("course_key", sa.String(length=255), nullable=False),
        sa.Column("course_display_name", sa.String(length=500), nullable=False),
        sa.Column("frequency_years", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "match_department",
            "match_role_key",
            "course_key",
            name="uq_training_matrix_req_tenant_dept_role_course",
        ),
    )
    op.create_index("ix_training_matrix_requirements_tenant_id", "training_matrix_requirements", ["tenant_id"])


def downgrade() -> None:
    op.drop_index("ix_training_matrix_requirements_tenant_id", table_name="training_matrix_requirements")
    op.drop_table("training_matrix_requirements")
    op.drop_index("ix_training_matrix_name_maps_engineer_id", table_name="training_matrix_name_maps")
    op.drop_index("ix_training_matrix_name_maps_tenant_id", table_name="training_matrix_name_maps")
    op.drop_table("training_matrix_name_maps")
    op.drop_index("ix_training_matrix_cells_course_id", table_name="training_matrix_cells")
    op.drop_index("ix_training_matrix_cells_person_id", table_name="training_matrix_cells")
    op.drop_index("ix_training_matrix_cells_import_id", table_name="training_matrix_cells")
    op.drop_index("ix_training_matrix_cells_tenant_id", table_name="training_matrix_cells")
    op.drop_table("training_matrix_cells")
    op.drop_index("ix_training_matrix_people_engineer_id", table_name="training_matrix_people")
    op.drop_index("ix_training_matrix_people_tenant_id", table_name="training_matrix_people")
    op.drop_table("training_matrix_people")
    op.drop_index("ix_training_matrix_courses_tenant_id", table_name="training_matrix_courses")
    op.drop_table("training_matrix_courses")
    op.drop_index("ix_training_matrix_imports_tenant_id", table_name="training_matrix_imports")
    op.drop_table("training_matrix_imports")
