"""Deduplicate workforce responses and add per-question uniqueness.

Revision ID: 20260322_workforce_resp_uniques
Revises: 20260321_case_snapshots
Create Date: 2026-03-22
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "20260322_workforce_resp_uniques"
down_revision: Union[str, None] = "20260321_case_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _has_unique_constraint(table_name: str, constraint_name: str) -> bool:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table_name):
        return False
    return any(
        constraint.get("name") == constraint_name
        for constraint in inspector.get_unique_constraints(table_name)
    )


def _deduplicate_responses(table_name: str) -> None:
    op.execute(
        sa.text(
            f"""
            WITH ranked_responses AS (
                SELECT
                    id,
                    ROW_NUMBER() OVER (
                        PARTITION BY run_id, question_id
                        ORDER BY
                            CASE WHEN updated_at IS NULL THEN 1 ELSE 0 END,
                            updated_at DESC,
                            CASE WHEN created_at IS NULL THEN 1 ELSE 0 END,
                            created_at DESC,
                            id DESC
                    ) AS row_num
                FROM {table_name}
            )
            DELETE FROM {table_name}
            WHERE id IN (
                SELECT id
                FROM ranked_responses
                WHERE row_num > 1
            )
            """
        )
    )


def upgrade() -> None:
    if _has_table("assessment_responses"):
        _deduplicate_responses("assessment_responses")
        if not _has_unique_constraint("assessment_responses", "uq_assessment_responses_run_question"):
            if op.get_bind().dialect.name == "sqlite":
                with op.batch_alter_table("assessment_responses") as batch_op:
                    batch_op.create_unique_constraint(
                        "uq_assessment_responses_run_question",
                        ["run_id", "question_id"],
                    )
            else:
                op.create_unique_constraint(
                    "uq_assessment_responses_run_question",
                    "assessment_responses",
                    ["run_id", "question_id"],
                )

    if _has_table("induction_responses"):
        _deduplicate_responses("induction_responses")
        if not _has_unique_constraint("induction_responses", "uq_induction_responses_run_question"):
            if op.get_bind().dialect.name == "sqlite":
                with op.batch_alter_table("induction_responses") as batch_op:
                    batch_op.create_unique_constraint(
                        "uq_induction_responses_run_question",
                        ["run_id", "question_id"],
                    )
            else:
                op.create_unique_constraint(
                    "uq_induction_responses_run_question",
                    "induction_responses",
                    ["run_id", "question_id"],
                )


def downgrade() -> None:
    if _has_unique_constraint("assessment_responses", "uq_assessment_responses_run_question"):
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table("assessment_responses") as batch_op:
                batch_op.drop_constraint("uq_assessment_responses_run_question", type_="unique")
        else:
            op.drop_constraint(
                "uq_assessment_responses_run_question",
                "assessment_responses",
                type_="unique",
            )
    if _has_unique_constraint("induction_responses", "uq_induction_responses_run_question"):
        if op.get_bind().dialect.name == "sqlite":
            with op.batch_alter_table("induction_responses") as batch_op:
                batch_op.drop_constraint("uq_induction_responses_run_question", type_="unique")
        else:
            op.drop_constraint(
                "uq_induction_responses_run_question",
                "induction_responses",
                type_="unique",
            )
