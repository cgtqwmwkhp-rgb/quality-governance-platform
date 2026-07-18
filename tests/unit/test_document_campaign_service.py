"""Unit tests for DocumentCampaignService.

Covers audience expansion, MCQ quiz grading, and campaign launch behaviour
(assignment creation, duplicate skipping, and notification counts).
"""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.document_campaign import AssignmentStatus, CampaignAssignment, CampaignStatus
from src.domain.models.governed_knowledge import QuizDraftStatus
from src.domain.services.document_campaign_service import (
    DocumentCampaignService,
    MAX_QUIZ_ATTEMPTS,
    grade_quiz_answers,
    strip_quiz_answer_keys,
)
from src.domain.services.document_campaign_notifications import portal_assignment_action_url


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

    def test_open_text_treated_as_open_not_mcq(self):
        questions = [
            {"type": "open_text", "question": "Describe the control.", "correct_answer": "n/a"},
            {"type": "text", "question": "Any concerns?", "correct_answer": "n/a"},
        ]
        answers = [
            {"question_index": 0, "text_answer": "We log incidents."},
            {"question_index": 1, "text_answer": "None."},
        ]
        result = grade_quiz_answers(questions, answers, pass_mark=70)

        assert result.score == 100
        assert result.passed is True
        assert result.review_needed is True


class TestPortalAssignmentActionUrl:
    def test_uses_portal_reading_path_with_assignment_id(self):
        assert portal_assignment_action_url(42) == "/portal/reading?assignment=42"


class TestStripQuizAnswerKeys:
    def test_removes_correct_answer(self):
        stripped = strip_quiz_answer_keys(MCQ_QUESTIONS)
        assert all("correct_answer" not in q for q in stripped)
        assert stripped[0]["question"] == "Q1"

    def test_coerces_mcq_without_options_to_open(self):
        questions = [{"type": "mcq", "question": "Explain.", "options": [], "correct_answer": "n/a"}]
        stripped = strip_quiz_answer_keys(questions)
        assert stripped[0]["type"] == "open"


# =============================================================================
# Audience expansion
# =============================================================================


class TestExpandAudience:
    @pytest.mark.asyncio
    async def test_user_ids_filtered_to_valid_active_tenant_users(self):
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalars_result([1, 2])))
        service = DocumentCampaignService(db)

        result = await service.expand_audience(tenant_id=1, audience={"user_ids": [3, 1, 2, 1, 900]})

        assert result == [1, 2]
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_user_ids_only_returns_empty_when_none_valid(self):
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalars_result([])))
        service = DocumentCampaignService(db)

        result = await service.expand_audience(tenant_id=1, audience={"user_ids": [900, 999]})

        assert result == []
        db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_group_ids_expand_via_membership_and_filter_invalid(self):
        db = SimpleNamespace(
            execute=AsyncMock(
                side_effect=[
                    _scalars_result([5, 6, 900]),
                    _scalars_result([5, 6]),
                ]
            )
        )
        service = DocumentCampaignService(db)

        result = await service.expand_audience(tenant_id=1, audience={"group_ids": [100]})

        assert result == [5, 6]
        assert db.execute.await_count == 2

    @pytest.mark.asyncio
    async def test_all_users_short_circuits_department_and_role(self):
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalars_result([1, 2, 3])))
        service = DocumentCampaignService(db)

        result = await service.expand_audience(
            tenant_id=1,
            audience={"all_users": True, "department": "Engineering", "role": "manager"},
        )

        assert result == [1, 2, 3]
        assert db.execute.await_count == 2  # all_users query + final validation filter

    @pytest.mark.asyncio
    async def test_department_and_role_are_unioned(self):
        db = SimpleNamespace(
            execute=AsyncMock(
                side_effect=[
                    _scalars_result([1, 2]),
                    _scalars_result([2, 3]),
                    _scalars_result([1, 2, 3]),
                ]
            ),
        )
        service = DocumentCampaignService(db)

        result = await service.expand_audience(
            tenant_id=1,
            audience={"department": "Engineering", "role": "manager"},
        )

        assert result == [1, 2, 3]
        assert db.execute.await_count == 3

    @pytest.mark.asyncio
    async def test_combines_group_and_explicit_user_ids(self):
        db = SimpleNamespace(
            execute=AsyncMock(
                side_effect=[
                    _scalars_result([5]),
                    _scalars_result([5, 9]),
                ]
            )
        )
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
            execute=AsyncMock(
                side_effect=[
                    _scalars_result([10, 20, 30]),  # expand_audience validation
                    _scalars_result([20]),  # existing assignments
                ]
            ),
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
    async def test_launch_rejects_empty_valid_audience(self):
        campaign = SimpleNamespace(
            id=1,
            tenant_id=1,
            status=CampaignStatus.DRAFT,
            audience_all_users=False,
            audience_department=None,
            audience_role=None,
            audience_group_ids=None,
            audience_user_ids=[900],
        )
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalars_result([])))
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)

        with pytest.raises(BadRequestError, match="No valid active users"):
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
            execute=AsyncMock(
                side_effect=[
                    _scalars_result([10]),  # expand_audience validation
                    _scalars_result([10]),  # user 10 already assigned
                ]
            ),
            add=MagicMock(),
            commit=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)

        result = await service.launch_campaign(tenant_id=1, campaign_id=1, launched_by_id=5)

        assert result["campaign_id"] == 1 and result["assigned_count"] == 0 and result["notified_count"] == 0
        assert campaign.status == CampaignStatus.ACTIVE

    @pytest.mark.asyncio
    async def test_launch_succeeds_when_notifications_fail(self):
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
            execute=AsyncMock(
                side_effect=[
                    _scalars_result([10]),
                    _scalars_result([]),
                ]
            ),
            add=MagicMock(),
            commit=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)
        service._notify_and_email_assignments = AsyncMock(side_effect=RuntimeError("notify boom"))

        result = await service.launch_campaign(tenant_id=1, campaign_id=1, launched_by_id=5)

        assert result["campaign_id"] == 1 and result["assigned_count"] == 1 and result["notified_count"] == 0
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
        assert result.quiz_attempts == 1
        assert result.attempts_remaining == MAX_QUIZ_ATTEMPTS - 1

    @pytest.mark.asyncio
    async def test_submit_quiz_rejects_when_max_attempts_reached(self):
        assignment = SimpleNamespace(
            id=1,
            user_id=7,
            tenant_id=1,
            campaign_id=1,
            quiz_attempts=MAX_QUIZ_ATTEMPTS,
        )
        campaign = SimpleNamespace(
            id=1,
            tenant_id=1,
            quiz_questions=[{"type": "mcq", "question": "Q1", "correct_answer": "A"}],
            quiz_pass_mark=70,
        )
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalar_one_result(assignment)))
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)

        with pytest.raises(BadRequestError, match="Maximum quiz attempts"):
            await service.submit_assignment_quiz(
                user_id=7,
                assignment_id=1,
                answers=[{"question_index": 0, "selected_option": "A"}],
            )

    @pytest.mark.asyncio
    async def test_submit_quiz_allows_third_attempt(self):
        assignment = SimpleNamespace(
            id=1,
            user_id=7,
            tenant_id=1,
            campaign_id=1,
            quiz_score=None,
            quiz_passed=None,
            quiz_attempts=2,
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

        assert assignment.quiz_attempts == 3
        assert result.attempts_remaining == 0

    @pytest.mark.asyncio
    async def test_complete_assignment_blocked_without_quiz_pass(self):
        assignment = SimpleNamespace(
            id=1, user_id=7, tenant_id=1, campaign_id=1, quiz_passed=False, status=AssignmentStatus.PENDING
        )
        campaign = SimpleNamespace(id=1, tenant_id=1, require_quiz=True)
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalar_one_result(assignment)))
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)
        service._has_open_assignee_question = AsyncMock(return_value=False)

        with pytest.raises(BadRequestError):
            await service.complete_assignment(
                user_id=7,
                assignment_id=1,
                acceptance_statement="I have read and understood this document.",
            )

    @pytest.mark.asyncio
    async def test_complete_assignment_requires_signature_without_open_question(self):
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
            signature_disposition=None,
            ip_address=None,
            user_agent=None,
        )
        campaign = SimpleNamespace(id=1, tenant_id=1, require_quiz=False, document_id=99)
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalar_one_result(assignment)))
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)
        service._has_open_assignee_question = AsyncMock(return_value=False)

        with pytest.raises(BadRequestError, match="Signature is required"):
            await service.complete_assignment(
                user_id=7,
                assignment_id=1,
                acceptance_statement="I have read and understood this document.",
            )

    @pytest.mark.asyncio
    async def test_complete_assignment_allows_deferred_signature_with_open_question(self):
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
            signature_disposition=None,
            ip_address=None,
            user_agent=None,
        )
        campaign = SimpleNamespace(id=1, tenant_id=1, require_quiz=False, document_id=99)
        db = SimpleNamespace(
            execute=AsyncMock(return_value=_scalar_one_result(assignment)),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)
        service._has_open_assignee_question = AsyncMock(return_value=True)

        result = await service.complete_assignment(
            user_id=7,
            assignment_id=1,
            acceptance_statement="I have read and understood this document.",
        )

        assert result.status == AssignmentStatus.COMPLETED
        assert result.signature_data is None
        assert result.signature_disposition == "signature_deferred_pending_answer"

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
            signature_disposition=None,
            ip_address=None,
            user_agent=None,
        )
        campaign = SimpleNamespace(id=1, tenant_id=1, require_quiz=False, document_id=99)
        db = SimpleNamespace(
            execute=AsyncMock(return_value=_scalar_one_result(assignment)),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)
        service._has_open_assignee_question = AsyncMock(return_value=False)

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
        assert result.signature_disposition == "signed"


# =============================================================================
# Snooze
# =============================================================================


class TestSnoozeAssignment:
    @pytest.mark.asyncio
    async def test_snooze_sets_snooze_until_for_own_pending_assignment(self):
        assignment = SimpleNamespace(
            id=1,
            user_id=7,
            tenant_id=1,
            campaign_id=1,
            status=AssignmentStatus.PENDING,
            snooze_until=None,
        )
        db = SimpleNamespace(
            execute=AsyncMock(return_value=_scalar_one_result(assignment)),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )
        service = DocumentCampaignService(db)

        result = await service.snooze_assignment(user_id=7, assignment_id=1, hours=24)

        assert result.snooze_until is not None
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_snooze_rejects_completed_assignment(self):
        assignment = SimpleNamespace(
            id=1,
            user_id=7,
            tenant_id=1,
            campaign_id=1,
            status=AssignmentStatus.COMPLETED,
            snooze_until=None,
        )
        db = SimpleNamespace(execute=AsyncMock(return_value=_scalar_one_result(assignment)))
        service = DocumentCampaignService(db)

        with pytest.raises(BadRequestError):
            await service.snooze_assignment(user_id=7, assignment_id=1, hours=24)

    @pytest.mark.asyncio
    async def test_snooze_rejects_invalid_hours(self):
        db = SimpleNamespace(execute=AsyncMock())
        service = DocumentCampaignService(db)

        with pytest.raises(BadRequestError):
            await service.snooze_assignment(user_id=7, assignment_id=1, hours=200)


# =============================================================================
# Reminder processing
# =============================================================================


class TestProcessDueReminders:
    @pytest.mark.asyncio
    async def test_skips_reminder_when_snoozed_but_still_marks_overdue(self):
        now = datetime.now(timezone.utc)
        assignment = SimpleNamespace(
            id=10,
            campaign_id=1,
            user_id=5,
            status=AssignmentStatus.PENDING,
            due_at=now - timedelta(hours=1),
            reminders_sent=0,
            last_reminder_at=None,
            snooze_until=now + timedelta(hours=12),
        )
        campaign = SimpleNamespace(
            id=1,
            tenant_id=1,
            document_id=99,
            status=CampaignStatus.ACTIVE,
            reminder_offsets_hours=[24],
            created_by_id=5,
            launched_by_id=6,
        )

        pending_result = MagicMock()
        pending_result.all.return_value = [(assignment, campaign)]
        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = []

        db = SimpleNamespace(
            execute=AsyncMock(side_effect=[pending_result, users_result]),
            add=MagicMock(),
            commit=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service._document_title = AsyncMock(return_value="Policy")

        counts = await service.process_due_reminders(now=now)

        assert assignment.status == AssignmentStatus.OVERDUE
        assert counts["overdue_escalated"] == 1
        assert counts["reminders_sent"] == 0
        assert assignment.reminders_sent == 0


# =============================================================================
# Compliance by group
# =============================================================================


class TestComplianceByGroup:
    @pytest.mark.asyncio
    async def test_returns_empty_when_no_audience_groups(self):
        campaign = SimpleNamespace(
            id=1,
            tenant_id=1,
            audience_group_ids=None,
        )
        db = SimpleNamespace(execute=AsyncMock())
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)

        rows = await service.compliance_by_group(tenant_id=1, campaign_id=1)

        assert rows == []

    @pytest.mark.asyncio
    async def test_builds_group_and_ungrouped_rows(self):
        campaign = SimpleNamespace(id=1, tenant_id=1, audience_group_ids=[10])
        group = SimpleNamespace(id=10, tenant_id=1, name="Field Engineers")
        assignment_in_group = SimpleNamespace(
            id=1,
            user_id=100,
            status=AssignmentStatus.COMPLETED,
            quiz_passed=True,
        )
        assignment_ungrouped = SimpleNamespace(
            id=2,
            user_id=200,
            status=AssignmentStatus.PENDING,
            quiz_passed=False,
        )

        db = SimpleNamespace(
            execute=AsyncMock(
                side_effect=[
                    _scalars_result([assignment_in_group, assignment_ungrouped]),
                    _scalars_result([group]),
                    MagicMock(all=MagicMock(return_value=[(10, 100)])),
                ]
            )
        )
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)

        rows = await service.compliance_by_group(tenant_id=1, campaign_id=1)

        assert len(rows) == 2
        assert rows[0]["group_name"] == "Field Engineers"
        assert rows[0]["assigned"] == 1
        assert rows[0]["completed"] == 1
        assert rows[1]["group_name"] == "Ungrouped"
        assert rows[1]["pending"] == 1


# Compliance passport (O-07)
# =============================================================================


class TestGetMyPassport:
    @pytest.mark.asyncio
    async def test_splits_outstanding_completed_and_stats(self):
        now = datetime.now(timezone.utc)
        outstanding_assignment = SimpleNamespace(
            id=1,
            status=AssignmentStatus.PENDING,
            assigned_at=now,
            due_at=now,
            completed_at=None,
            quiz_score=80,
            quiz_passed=True,
        )
        completed_assignment = SimpleNamespace(
            id=2,
            status=AssignmentStatus.COMPLETED,
            assigned_at=now,
            due_at=now,
            completed_at=now,
            quiz_score=50,
            quiz_passed=False,
        )
        campaign = SimpleNamespace(id=10, title="Safety read")
        document = SimpleNamespace(id=5, title="Policy A")

        db = SimpleNamespace(
            execute=AsyncMock(
                return_value=SimpleNamespace(
                    all=lambda: [
                        (outstanding_assignment, campaign, document),
                        (completed_assignment, campaign, document),
                    ]
                )
            )
        )
        service = DocumentCampaignService(db)

        result = await service.get_my_passport(tenant_id=1, user_id=7)

        assert len(result["outstanding"]) == 1
        assert len(result["completed"]) == 1
        assert result["stats"]["total_assigned"] == 2
        assert result["stats"]["completion_rate"] == 50.0
        assert result["stats"]["quiz_pass_rate"] == 50.0


# =============================================================================
# Evidence CSV (O-09)
# =============================================================================


class TestBuildEvidencePackCsv:
    @pytest.mark.asyncio
    async def test_csv_includes_assignment_metadata(self):
        now = datetime.now(timezone.utc)
        assignment = SimpleNamespace(
            status=AssignmentStatus.COMPLETED,
            assigned_at=now,
            due_at=now,
            first_opened_at=now,
            completed_at=now,
            quiz_score=100,
            quiz_passed=True,
            signature_data="sig-data",
            signature_disposition="signed",
            ip_address="192.168.1.1",
        )
        campaign = SimpleNamespace(id=9, tenant_id=1, document_id=3)

        db = SimpleNamespace(
            execute=AsyncMock(return_value=SimpleNamespace(all=lambda: [(assignment, "engineer@example.com")]))
        )
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)

        csv_content, filename = await service.build_evidence_pack_csv(tenant_id=1, campaign_id=9)

        assert filename == "campaign-9-evidence-pack.csv"
        assert "user_email,status" in csv_content
        assert "engineer@example.com" in csv_content
        assert "192.168.1.1" in csv_content
        assert "signature_disposition" in csv_content
        assert ",signed," in csv_content
        assert ",True," in csv_content or ",true," in csv_content.lower()


# =============================================================================
# Re-ack campaign spawn (O-10)
# =============================================================================


class TestSpawnReackCampaign:
    @pytest.mark.asyncio
    async def test_no_active_campaigns_returns_false(self):
        db = SimpleNamespace(
            execute=AsyncMock(return_value=SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: None))),
            add=MagicMock(),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )
        service = DocumentCampaignService(db)

        result = await service.spawn_reack_campaign(document_id=5, tenant_id=1, actor_id=2)

        assert result["spawned"] is False
        assert result["reason"] == "no_active_campaigns"

    @pytest.mark.asyncio
    async def test_creates_draft_from_active_campaign(self):
        source = SimpleNamespace(
            id=11,
            title="Annual read",
            due_within_days=14,
            require_quiz=True,
            require_sign=True,
            reminder_offsets_hours=[24, 168],
            audience_all_users=True,
            audience_department=None,
            audience_role=None,
            audience_group_ids=None,
            audience_user_ids=None,
            quiz_draft_id=3,
            quiz_questions=[{"type": "mcq", "question": "Q1"}],
            quiz_pass_mark=80,
        )

        execute_results = [
            SimpleNamespace(scalars=lambda: SimpleNamespace(first=lambda: source)),
            SimpleNamespace(scalar_one_or_none=lambda: None),
        ]
        db = SimpleNamespace(
            execute=AsyncMock(side_effect=execute_results),
            add=MagicMock(),
            commit=AsyncMock(),
            refresh=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service._document_title = AsyncMock(return_value="Safety Policy")

        result = await service.spawn_reack_campaign(document_id=5, tenant_id=1, actor_id=2)

        assert result["spawned"] is True
        assert result["source_campaign_id"] == 11
        assert db.add.called
        added_campaign = db.add.call_args[0][0]
        assert added_campaign.status == CampaignStatus.DRAFT
        assert added_campaign.title == "Re-acknowledgment: Annual read"
