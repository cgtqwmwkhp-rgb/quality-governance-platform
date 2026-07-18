"""Unit tests for DocumentCampaignService.

Covers audience expansion, MCQ quiz grading, and campaign launch behaviour
(assignment creation, duplicate skipping, and notification counts).
"""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.document_campaign import AssignmentStatus, CampaignAssignment, CampaignStatus
from src.domain.models.governed_knowledge import QuizDraftStatus
from src.domain.services.document_campaign_service import (
    DocumentCampaignService,
    grade_quiz_answers,
    strip_quiz_answer_keys,
)


def _scalars_result(items):
    """Build a fake SQLAlchemy result whose .scalars().all() returns `items`."""
    result = MagicMock()
    result.scalars.return_value.all.return_value = items
    return result


def _scalar_one_result(item):
    """Build a fake SQLAlchemy result whose .scalar_one_or_none() returns `item`."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = item
    return result


# =============================================================================
# MCQ grading
# =============================================================================

MCQ_QUESTIONS = [
    {"type": "mcq", "question": "Q1", "options": ["A", "B", "C"], "correct_answer": "B"},
    {"type": "mcq", "question": "Q2", "options": ["A", "B", "C"], "correct_answer": "C"},
    {"type": "open", "question": "Explain the policy.", "correct_answer": "Free text reference."},
]


class TestGradeQuizAnswers:
    def test_all_mcq_correct_passes(self):
        answers = [
            {"question_index": 0, "selected_option": "B"},
            {"question_index": 1, "selected_option": "C"},
            {"question_index": 2, "text_answer": "My explanation"},
        ]
        result = grade_quiz_answers(MCQ_QUESTIONS, answers, pass_mark=70)

        assert result.score == 100
        assert result.passed is True
        assert result.review_needed is True  # open question always needs review

    def test_below_pass_mark_fails(self):
        answers = [
            {"question_index": 0, "selected_option": "A"},  # wrong
            {"question_index": 1, "selected_option": "C"},  # correct
        ]
        result = grade_quiz_answers(MCQ_QUESTIONS, answers, pass_mark=70)

        assert result.score == 50
        assert result.passed is False

    def test_missing_answer_counts_as_incorrect(self):
        answers = [{"question_index": 0, "selected_option": "B"}]
        result = grade_quiz_answers(MCQ_QUESTIONS, answers, pass_mark=70)

        assert result.score == 50
        assert result.passed is False

    def test_open_question_review_needed_does_not_block_pass(self):
        answers = [
            {"question_index": 0, "selected_option": "B"},
            {"question_index": 1, "selected_option": "C"},
        ]
        result = grade_quiz_answers(MCQ_QUESTIONS, answers, pass_mark=100)

        assert result.passed is True
        assert result.review_needed is True

    def test_no_mcq_questions_defaults_to_pass(self):
        questions = [{"type": "open", "question": "Reflect on the policy.", "correct_answer": "n/a"}]
        result = grade_quiz_answers(questions, [], pass_mark=70)

        assert result.score == 100
        assert result.passed is True
        assert result.review_needed is True

    def test_case_insensitive_matching(self):
        questions = [{"type": "mcq", "question": "Q1", "correct_answer": "Blue"}]
        answers = [{"question_index": 0, "selected_option": "blue"}]
        result = grade_quiz_answers(questions, answers, pass_mark=70)

        assert result.score == 100
        assert result.passed is True


class TestStripQuizAnswerKeys:
    def test_removes_correct_answer(self):
        stripped = strip_quiz_answer_keys(MCQ_QUESTIONS)
        assert all("correct_answer" not in q for q in stripped)
        assert stripped[0]["question"] == "Q1"


# =============================================================================
# Audience expansion
# =============================================================================


class TestExpandAudience:
    @pytest.mark.asyncio
    async def test_user_ids_only_issues_no_queries(self):
        db = SimpleNamespace(execute=AsyncMock())
        service = DocumentCampaignService(db)

        result = await service.expand_audience(tenant_id=1, audience={"user_ids": [3, 1, 2, 1]})

        assert result == [1, 2, 3]
        db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_group_ids_expand_via_membership(self):
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalars_result([5, 6])))
        service = DocumentCampaignService(db)

        result = await service.expand_audience(tenant_id=1, audience={"group_ids": [100]})

        assert result == [5, 6]
        assert db.execute.await_count == 1

    @pytest.mark.asyncio
    async def test_all_users_short_circuits_department_and_role(self):
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalars_result([1, 2, 3])))
        service = DocumentCampaignService(db)

        result = await service.expand_audience(
            tenant_id=1,
            audience={"all_users": True, "department": "Engineering", "role": "manager"},
        )

        assert result == [1, 2, 3]
        assert db.execute.await_count == 1  # only the all_users query — department/role skipped

    @pytest.mark.asyncio
    async def test_department_and_role_are_unioned(self):
        db = SimpleNamespace(
            execute=AsyncMock(side_effect=[_scalars_result([1, 2]), _scalars_result([2, 3])]),
        )
        service = DocumentCampaignService(db)

        result = await service.expand_audience(
            tenant_id=1,
            audience={"department": "Engineering", "role": "manager"},
        )

        assert result == [1, 2, 3]
        assert db.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_combines_group_and_explicit_user_ids(self):
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalars_result([5])))
        service = DocumentCampaignService(db)

        result = await service.expand_audience(
            tenant_id=1,
            audience={"group_ids": [1], "user_ids": [9]},
        )

        assert result == [5, 9]


# =============================================================================
# Campaign creation (quiz draft copy)
# =============================================================================


class TestCreateCampaign:
    @pytest.mark.asyncio
    async def test_copies_quiz_from_approved_draft_and_sets_require_quiz(self):
        draft = SimpleNamespace(
            id=42,
            tenant_id=1,
            status=QuizDraftStatus.APPROVED,
            questions=[{"type": "mcq", "question": "Q1", "correct_answer": "A"}],
            pass_mark=75,
        )
        db = SimpleNamespace(
            execute=AsyncMock(return_value=_scalar_one_result(draft)),
            add=MagicMock(),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )
        service = DocumentCampaignService(db)

        campaign = await service.create_campaign(
            tenant_id=1,
            created_by_id=7,
            document_id=99,
            quiz_draft_id=42,
            audience={"all_users": True},
        )

        assert campaign.quiz_questions == draft.questions
        assert campaign.quiz_pass_mark == 75
        assert campaign.require_quiz is True
        assert campaign.status == CampaignStatus.DRAFT
        db.add.assert_called_once()
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_rejects_unapproved_quiz_draft(self):
        draft = SimpleNamespace(id=42, tenant_id=1, status=QuizDraftStatus.DRAFT, questions=[], pass_mark=70)
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalar_one_result(draft)), add=MagicMock())
        service = DocumentCampaignService(db)

        with pytest.raises(BadRequestError):
            await service.create_campaign(
                tenant_id=1,
                created_by_id=7,
                document_id=99,
                quiz_draft_id=42,
                audience={"all_users": True},
            )

    @pytest.mark.asyncio
    async def test_rejects_missing_quiz_draft(self):
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalar_one_result(None)), add=MagicMock())
        service = DocumentCampaignService(db)

        with pytest.raises(BadRequestError):
            await service.create_campaign(
                tenant_id=1,
                created_by_id=7,
                document_id=99,
                quiz_draft_id=999,
                audience={"all_users": True},
            )

    @pytest.mark.asyncio
    async def test_no_quiz_defaults_require_quiz_false(self):
        db = SimpleNamespace(add=MagicMock(), commit=AsyncMock(), refresh=AsyncMock())
        service = DocumentCampaignService(db)

        campaign = await service.create_campaign(
            tenant_id=1,
            created_by_id=7,
            document_id=99,
            audience={"user_ids": [1, 2]},
        )

        assert campaign.require_quiz is False
        assert campaign.quiz_questions is None
        assert campaign.audience_user_ids == [1, 2]


# =============================================================================
# Launch
# =============================================================================


class TestLaunchCampaign:
    @pytest.mark.asyncio
    async def test_launch_creates_assignments_skips_duplicates_and_notifies(self):
        campaign = SimpleNamespace(
            id=1,
            tenant_id=1,
            status=CampaignStatus.DRAFT,
            document_id=99,
            due_within_days=14,
            require_quiz=False,
            audience_all_users=False,
            audience_department=None,
            audience_role=None,
            audience_group_ids=None,
            audience_user_ids=[10, 20, 30],
            launched_at=None,
            launched_by_id=None,
        )

        db = SimpleNamespace(
            execute=AsyncMock(return_value=_scalars_result([20])),  # user 20 already assigned
            add=MagicMock(),
            commit=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)
        service._document_title = AsyncMock(return_value="Fire Safety Policy")
        service._user_email = AsyncMock(return_value=None)

        result = await service.launch_campaign(tenant_id=1, campaign_id=1, launched_by_id=5)

        assert result["campaign_id"] == 1 and result["assigned_count"] == 2 and result["notified_count"] == 2
        assert result.get("status") == "active"
        assert campaign.status == CampaignStatus.ACTIVE
        assert campaign.launched_by_id == 5
        assert campaign.launched_at is not None

        added_assignments = [c.args[0] for c in db.add.call_args_list if isinstance(c.args[0], CampaignAssignment)]
        assert {a.user_id for a in added_assignments} == {10, 30}
        assert all(a.status == AssignmentStatus.PENDING for a in added_assignments)

    @pytest.mark.asyncio
    async def test_launch_rejects_non_draft_campaign(self):
        campaign = SimpleNamespace(id=1, status=CampaignStatus.ACTIVE)
        db = SimpleNamespace(execute=AsyncMock())
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)

        with pytest.raises(BadRequestError):
            await service.launch_campaign(tenant_id=1, campaign_id=1, launched_by_id=5)

    @pytest.mark.asyncio
    async def test_launch_with_no_new_users_assigns_zero(self):
        campaign = SimpleNamespace(
            id=1,
            tenant_id=1,
            status=CampaignStatus.DRAFT,
            document_id=99,
            due_within_days=14,
            require_quiz=False,
            audience_all_users=False,
            audience_department=None,
            audience_role=None,
            audience_group_ids=None,
            audience_user_ids=[10],
            launched_at=None,
            launched_by_id=None,
        )
        db = SimpleNamespace(
            execute=AsyncMock(return_value=_scalars_result([10])),
            add=MagicMock(),
            commit=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)

        result = await service.launch_campaign(tenant_id=1, campaign_id=1, launched_by_id=5)

        assert result["campaign_id"] == 1 and result["assigned_count"] == 0 and result["notified_count"] == 0
        assert campaign.status == CampaignStatus.ACTIVE


# =============================================================================
# Assignment quiz + completion
# =============================================================================


class TestAssignmentQuizAndCompletion:
    @pytest.mark.asyncio
    async def test_get_assignment_quiz_strips_answers_and_checks_ownership(self):
        assignment = SimpleNamespace(id=1, user_id=7, tenant_id=1, campaign_id=1)
        campaign = SimpleNamespace(
            id=1,
            tenant_id=1,
            quiz_questions=[{"type": "mcq", "question": "Q1", "correct_answer": "A", "options": ["A", "B"]}],
            quiz_pass_mark=80,
        )
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalar_one_result(assignment)))
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)

        quiz = await service.get_assignment_quiz(user_id=7, assignment_id=1)

        assert quiz["pass_mark"] == 80
        assert "correct_answer" not in quiz["questions"][0]

    @pytest.mark.asyncio
    async def test_get_assignment_quiz_rejects_other_users_assignment(self):
        assignment = SimpleNamespace(id=1, user_id=7, tenant_id=1, campaign_id=1)
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalar_one_result(assignment)))
        service = DocumentCampaignService(db)

        with pytest.raises(NotFoundError):
            await service.get_assignment_quiz(user_id=999, assignment_id=1)

    @pytest.mark.asyncio
    async def test_submit_quiz_stores_score_and_increments_attempts(self):
        assignment = SimpleNamespace(
            id=1,
            user_id=7,
            tenant_id=1,
            campaign_id=1,
            quiz_score=None,
            quiz_passed=None,
            quiz_attempts=0,
            quiz_review_needed=False,
            last_quiz_answers=None,
        )
        campaign = SimpleNamespace(
            id=1,
            tenant_id=1,
            quiz_questions=[{"type": "mcq", "question": "Q1", "correct_answer": "A"}],
            quiz_pass_mark=70,
        )
        db = SimpleNamespace(
            execute=AsyncMock(return_value=_scalar_one_result(assignment)),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)

        result = await service.submit_assignment_quiz(
            user_id=7,
            assignment_id=1,
            answers=[{"question_index": 0, "selected_option": "A"}],
        )

        assert result.score == 100
        assert result.passed is True
        assert assignment.quiz_attempts == 1
        assert assignment.quiz_passed is True

    @pytest.mark.asyncio
    async def test_complete_assignment_blocked_without_quiz_pass(self):
        assignment = SimpleNamespace(
            id=1, user_id=7, tenant_id=1, campaign_id=1, quiz_passed=False, status=AssignmentStatus.PENDING
        )
        campaign = SimpleNamespace(id=1, tenant_id=1, require_quiz=True)
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalar_one_result(assignment)))
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)

        with pytest.raises(BadRequestError):
            await service.complete_assignment(
                user_id=7,
                assignment_id=1,
                acceptance_statement="I have read and understood this document.",
            )

    @pytest.mark.asyncio
    async def test_complete_assignment_succeeds_when_quiz_passed_or_not_required(self):
        assignment = SimpleNamespace(
            id=1,
            user_id=7,
            tenant_id=1,
            campaign_id=1,
            quiz_passed=None,
            status=AssignmentStatus.PENDING,
            completed_at=None,
            acceptance_statement=None,
            signature_data=None,
            ip_address=None,
            user_agent=None,
        )
        campaign = SimpleNamespace(id=1, tenant_id=1, require_quiz=False)
        db = SimpleNamespace(
            execute=AsyncMock(return_value=_scalar_one_result(assignment)),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)

        result = await service.complete_assignment(
            user_id=7,
            assignment_id=1,
            acceptance_statement="I have read and understood this document.",
            signature_data="data:image/png;base64,abc",
            ip_address="10.0.0.1",
            user_agent="pytest-agent",
        )

        assert result.status == AssignmentStatus.COMPLETED
        assert result.completed_at is not None
        assert result.signature_data == "data:image/png;base64,abc"
