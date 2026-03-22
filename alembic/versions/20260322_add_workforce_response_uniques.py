"""Deduplicate workforce responses and add per-question uniqueness.

Revision ID: 20260322_workforce_resp_uniques
Revises: 20260321_case_snapshots
Create Date: 2026-03-22
"""

from typing import Sequence, Union

from alembic import op

revision: str = "20260322_workforce_resp_uniques"
down_revision: Union[str, None] = "20260321_case_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        DELETE FROM assessment_responses ar
        USING (
            SELECT ctid
            FROM (
                SELECT
                    ctid,
                    ROW_NUMBER() OVER (
                        PARTITION BY run_id, question_id
                        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
                    ) AS row_num
                FROM assessment_responses
            ) ranked
            WHERE ranked.row_num > 1
        ) duplicates
        WHERE ar.ctid = duplicates.ctid
        """
    )
    op.execute(
        """
        DELETE FROM induction_responses ir
        USING (
            SELECT ctid
            FROM (
                SELECT
                    ctid,
                    ROW_NUMBER() OVER (
                        PARTITION BY run_id, question_id
                        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST, id DESC
                    ) AS row_num
                FROM induction_responses
            ) ranked
            WHERE ranked.row_num > 1
        ) duplicates
        WHERE ir.ctid = duplicates.ctid
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_assessment_responses_run_question'
            ) THEN
                ALTER TABLE assessment_responses
                ADD CONSTRAINT uq_assessment_responses_run_question UNIQUE (run_id, question_id);
            END IF;
        END
        $$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint
                WHERE conname = 'uq_induction_responses_run_question'
            ) THEN
                ALTER TABLE induction_responses
                ADD CONSTRAINT uq_induction_responses_run_question UNIQUE (run_id, question_id);
            END IF;
        END
        $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        ALTER TABLE assessment_responses
        DROP CONSTRAINT IF EXISTS uq_assessment_responses_run_question
        """
    )
    op.execute(
        """
        ALTER TABLE induction_responses
        DROP CONSTRAINT IF EXISTS uq_induction_responses_run_question
        """
    )
