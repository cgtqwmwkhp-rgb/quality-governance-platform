"""Add positive_answer column to audit_questions.

Revision ID: 20260303_pos_ans
Revises: 20260306_doc_inv_idx
Create Date: 2026-03-03

"""

from alembic import op
import sqlalchemy as sa

revision = "20260303_pos_ans"
down_revision = "20260306_doc_inv_idx"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "audit_questions",
        sa.Column("positive_answer", sa.String(10), nullable=False, server_default="yes"),
    )
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("audit_questions") as batch_op:
            batch_op.create_check_constraint(
                "ck_audit_questions_positive_answer",
                "positive_answer IN ('yes', 'no')",
            )
    else:
        op.create_check_constraint(
            "ck_audit_questions_positive_answer",
            "audit_questions",
            "positive_answer IN ('yes', 'no')",
        )


def downgrade() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("audit_questions") as batch_op:
            batch_op.drop_constraint("ck_audit_questions_positive_answer", type_="check")
    else:
        op.drop_constraint("ck_audit_questions_positive_answer", "audit_questions", type_="check")
    op.drop_column("audit_questions", "positive_answer")
