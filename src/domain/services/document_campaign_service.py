"""Document Campaign Service.

Manages engineer groups, document campaigns (read/quiz/sign-off), audience
expansion, launch notifications, and per-user assignment progress.
"""

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.document import Document
from src.domain.models.document_campaign import (
    DEFAULT_REMINDER_OFFSETS_HOURS,
    AssignmentStatus,
    CampaignAssignment,
    CampaignStatus,
    DocumentCampaign,
    EngineerGroup,
    EngineerGroupMember,
)
from src.domain.models.form_config import SystemSetting
from src.domain.models.governed_knowledge import (
    DiscussionThreadStatus,
    DocumentDiscussionMessage,
    DocumentDiscussionThread,
    DocumentQuizDraft,
    QuizDraftStatus,
)
from src.domain.models.notification import Notification, NotificationPriority, NotificationType
from src.domain.models.user import Role, User, user_roles

logger = logging.getLogger(__name__)

CAMPAIGN_DEFAULT_REMINDER_SETTING_KEY = "campaign.default_reminder_hours"
CAMPAIGN_DEFAULT_REMINDER_CATEGORY = "campaigns"


@dataclass(frozen=True)
class QuizGradeResult:
    """Outcome of grading a submitted quiz attempt."""

    score: int
    passed: bool
    pass_mark: int
    review_needed: bool


def grade_quiz_answers(
    questions: List[Dict[str, Any]],
    answers: List[Dict[str, Any]],
    pass_mark: int,
) -> QuizGradeResult:
    """Server-side grading of a quiz attempt.

    Only MCQ questions contribute to the score. Open-ended questions are
    flagged as needing human review but never block a pass once the MCQ
    pass mark is met.
    """
    answers_by_index = {a["question_index"]: a for a in answers if "question_index" in a}

    mcq_total = 0
    mcq_correct = 0
    review_needed = False

    for index, question in enumerate(questions):
        question_type = str(question.get("type") or "mcq").strip().lower()
        answer = answers_by_index.get(index)

        if question_type == "open":
            review_needed = True
            continue

        mcq_total += 1
        correct_answer = str(question.get("correct_answer") or "").strip().lower()
        selected_option = str((answer or {}).get("selected_option") or "").strip().lower()
        if selected_option and correct_answer and selected_option == correct_answer:
            mcq_correct += 1

    if mcq_total == 0:
        # Nothing gradeable — don't block on a quiz that has no MCQ content.
        score = 100
        passed = True
    else:
        score = round((mcq_correct / mcq_total) * 100)
        passed = score >= pass_mark

    return QuizGradeResult(score=score, passed=passed, pass_mark=pass_mark, review_needed=review_needed)


def strip_quiz_answer_keys(questions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Return quiz questions with correct-answer keys removed for MCQ delivery to engineers."""
    stripped = []
    for question in questions:
        clean = {k: v for k, v in question.items() if k != "correct_answer"}
        stripped.append(clean)
    return stripped


class DocumentCampaignService:
    """Service for document campaigns, groups, and engineer assignments."""

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Engineer Groups ====================

    async def create_group(
        self,
        *,
        tenant_id: int,
        created_by_id: int,
        name: str,
        description: Optional[str] = None,
        member_user_ids: Optional[List[int]] = None,
    ) -> EngineerGroup:
        group = EngineerGroup(
            tenant_id=tenant_id,
            name=name,
            description=description,
            created_by_id=created_by_id,
        )
        self.db.add(group)
        await self.db.flush()

        for user_id in dict.fromkeys(member_user_ids or []):
            self.db.add(
                EngineerGroupMember(
                    tenant_id=tenant_id,
                    group_id=group.id,
                    user_id=user_id,
                    added_by_id=created_by_id,
                )
            )

        await self.db.commit()
        await self.db.refresh(group)
        return group

    async def list_groups(self, *, tenant_id: int) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            select(EngineerGroup, func.count(EngineerGroupMember.id))
            .outerjoin(EngineerGroupMember, EngineerGroupMember.group_id == EngineerGroup.id)
            .where(EngineerGroup.tenant_id == tenant_id)
            .group_by(EngineerGroup.id)
            .order_by(EngineerGroup.name)
        )
        return [{"group": group, "member_count": count} for group, count in result.all()]

    async def add_group_members(
        self,
        *,
        tenant_id: int,
        group_id: int,
        user_ids: List[int],
        added_by_id: int,
    ) -> EngineerGroup:
        group = await self._get_group(tenant_id=tenant_id, group_id=group_id)

        existing_result = await self.db.execute(
            select(EngineerGroupMember.user_id).where(EngineerGroupMember.group_id == group_id)
        )
        existing_user_ids = set(existing_result.scalars().all())

        for user_id in dict.fromkeys(user_ids):
            if user_id in existing_user_ids:
                continue
            self.db.add(
                EngineerGroupMember(
                    tenant_id=tenant_id,
                    group_id=group_id,
                    user_id=user_id,
                    added_by_id=added_by_id,
                )
            )

        await self.db.commit()
        await self.db.refresh(group)
        return group

    async def remove_group_member(self, *, tenant_id: int, group_id: int, user_id: int) -> None:
        await self._get_group(tenant_id=tenant_id, group_id=group_id)

        result = await self.db.execute(
            select(EngineerGroupMember).where(
                EngineerGroupMember.group_id == group_id,
                EngineerGroupMember.user_id == user_id,
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            raise NotFoundError("Group member not found")

        await self.db.delete(member)
        await self.db.commit()

    async def _get_group(self, *, tenant_id: int, group_id: int) -> EngineerGroup:
        result = await self.db.execute(
            select(EngineerGroup).where(EngineerGroup.id == group_id, EngineerGroup.tenant_id == tenant_id)
        )
        group = result.scalar_one_or_none()
        if group is None:
            raise NotFoundError("Engineer group not found")
        return group

    # ==================== Campaigns ====================

    async def create_campaign(
        self,
        *,
        tenant_id: int,
        created_by_id: int,
        document_id: int,
        quiz_draft_id: Optional[int] = None,
        title: Optional[str] = None,
        due_within_days: int = 14,
        require_quiz: Optional[bool] = None,
        require_sign: bool = True,
        reminder_offsets_hours: Optional[List[int]] = None,
        audience: Optional[Dict[str, Any]] = None,
    ) -> DocumentCampaign:
        audience = audience or {}

        quiz_questions: Optional[List[Dict[str, Any]]] = None
        quiz_pass_mark: Optional[int] = None

        if quiz_draft_id is None and require_quiz is True:
            # FE Launch panel may omit quiz_draft_id — attach latest approved draft for document
            latest = await self.db.execute(
                select(DocumentQuizDraft)
                .where(
                    DocumentQuizDraft.document_id == document_id,
                    DocumentQuizDraft.tenant_id == tenant_id,
                    DocumentQuizDraft.status == QuizDraftStatus.APPROVED,
                )
                .order_by(DocumentQuizDraft.id.desc())
                .limit(1)
            )
            auto_draft = latest.scalar_one_or_none()
            if auto_draft is not None:
                quiz_draft_id = auto_draft.id

        if quiz_draft_id is not None:
            draft = await self._get_approved_quiz_draft(tenant_id=tenant_id, quiz_draft_id=quiz_draft_id)
            quiz_questions = draft.questions
            quiz_pass_mark = draft.pass_mark
            if require_quiz is None:
                require_quiz = True
        elif require_quiz is None:
            require_quiz = False

        if require_quiz and not quiz_questions:
            raise BadRequestError("require_quiz=true but no approved quiz draft found for this document")

        campaign = DocumentCampaign(
            tenant_id=tenant_id,
            document_id=document_id,
            quiz_draft_id=quiz_draft_id,
            title=title,
            status=CampaignStatus.DRAFT,
            due_within_days=due_within_days,
            require_quiz=require_quiz,
            require_sign=require_sign,
            reminder_offsets_hours=list(reminder_offsets_hours or DEFAULT_REMINDER_OFFSETS_HOURS),
            audience_all_users=bool(audience.get("all_users")),
            audience_department=audience.get("department"),
            audience_role=audience.get("role"),
            audience_group_ids=list(audience["group_ids"]) if audience.get("group_ids") else None,
            audience_user_ids=list(audience["user_ids"]) if audience.get("user_ids") else None,
            quiz_questions=quiz_questions,
            quiz_pass_mark=quiz_pass_mark,
            created_by_id=created_by_id,
        )
        self.db.add(campaign)
        await self.db.commit()
        await self.db.refresh(campaign)
        return campaign

    async def _get_approved_quiz_draft(self, *, tenant_id: int, quiz_draft_id: int) -> DocumentQuizDraft:
        result = await self.db.execute(
            select(DocumentQuizDraft).where(
                DocumentQuizDraft.id == quiz_draft_id,
                DocumentQuizDraft.tenant_id == tenant_id,
            )
        )
        draft = result.scalar_one_or_none()
        if draft is None or draft.status != QuizDraftStatus.APPROVED:
            raise BadRequestError("Quiz draft not found or not approved")
        return draft

    async def get_campaign(self, *, tenant_id: int, campaign_id: int) -> DocumentCampaign:
        result = await self.db.execute(
            select(DocumentCampaign).where(
                DocumentCampaign.id == campaign_id,
                DocumentCampaign.tenant_id == tenant_id,
            )
        )
        campaign = result.scalar_one_or_none()
        if campaign is None:
            raise NotFoundError("Campaign not found")
        return campaign

    async def get_campaign_with_summary(self, *, tenant_id: int, campaign_id: int) -> Dict[str, Any]:
        campaign = await self.get_campaign(tenant_id=tenant_id, campaign_id=campaign_id)
        summary = await self._compliance_summary(campaign_id)
        return {"campaign": campaign, **summary}

    async def list_campaigns_for_document(self, *, tenant_id: int, document_id: int) -> List[DocumentCampaign]:
        result = await self.db.execute(
            select(DocumentCampaign)
            .where(
                DocumentCampaign.document_id == document_id,
                DocumentCampaign.tenant_id == tenant_id,
            )
            .order_by(DocumentCampaign.created_at.desc())
        )
        return list(result.scalars().all())

    async def _compliance_summary(self, campaign_id: int) -> Dict[str, Any]:
        result = await self.db.execute(
            select(CampaignAssignment.status, func.count(CampaignAssignment.id))
            .where(CampaignAssignment.campaign_id == campaign_id)
            .group_by(CampaignAssignment.status)
        )
        counts: Dict[str, int] = {row[0].value if hasattr(row[0], "value") else row[0]: row[1] for row in result.all()}

        total = sum(counts.values())
        completed = counts.get(AssignmentStatus.COMPLETED.value, 0)
        pending = counts.get(AssignmentStatus.PENDING.value, 0)
        overdue = counts.get(AssignmentStatus.OVERDUE.value, 0)
        expired = counts.get(AssignmentStatus.EXPIRED.value, 0)

        return {
            "total_assigned": total,
            "completed": completed,
            "pending": pending,
            "overdue": overdue,
            "expired": expired,
            "completion_rate": round((completed / total * 100), 1) if total > 0 else 0.0,
        }

    # ==================== Audience Expansion ====================

    async def expand_audience(self, *, tenant_id: int, audience: Dict[str, Any]) -> List[int]:
        """Expand an audience spec into a de-duplicated, sorted list of user IDs."""
        user_ids: set = {int(u) for u in (audience.get("user_ids") or [])}

        group_ids = audience.get("group_ids") or []
        if group_ids:
            result = await self.db.execute(
                select(EngineerGroupMember.user_id).where(EngineerGroupMember.group_id.in_(group_ids))
            )
            user_ids.update(result.scalars().all())

        if audience.get("all_users"):
            result = await self.db.execute(
                select(User.id).where(User.tenant_id == tenant_id, User.is_active == True)  # noqa: E712
            )
            user_ids.update(result.scalars().all())
        else:
            department = audience.get("department")
            if department:
                result = await self.db.execute(
                    select(User.id).where(
                        User.tenant_id == tenant_id,
                        User.is_active == True,  # noqa: E712
                        User.department == department,
                    )
                )
                user_ids.update(result.scalars().all())

            role = audience.get("role")
            if role:
                result = await self.db.execute(
                    select(User.id)
                    .join(user_roles, user_roles.c.user_id == User.id)
                    .join(Role, Role.id == user_roles.c.role_id)
                    .where(
                        User.tenant_id == tenant_id,
                        User.is_active == True,  # noqa: E712
                        Role.name == role,
                    )
                )
                user_ids.update(result.scalars().all())

        return sorted(user_ids)

    # ==================== Launch ====================

    async def launch_campaign(
        self,
        *,
        tenant_id: int,
        campaign_id: int,
        launched_by_id: int,
    ) -> Dict[str, Any]:
        campaign = await self.get_campaign(tenant_id=tenant_id, campaign_id=campaign_id)
        if campaign.status != CampaignStatus.DRAFT:
            raise BadRequestError("Only draft campaigns can be launched")

        audience = {
            "all_users": campaign.audience_all_users,
            "department": campaign.audience_department,
            "role": campaign.audience_role,
            "group_ids": campaign.audience_group_ids,
            "user_ids": campaign.audience_user_ids,
        }
        user_ids = await self.expand_audience(tenant_id=tenant_id, audience=audience)

        existing_result = await self.db.execute(
            select(CampaignAssignment.user_id).where(CampaignAssignment.campaign_id == campaign_id)
        )
        existing_user_ids = set(existing_result.scalars().all())

        now = datetime.now(timezone.utc)
        due_at = now + timedelta(days=campaign.due_within_days)

        new_assignments: List[CampaignAssignment] = []
        for user_id in user_ids:
            if user_id in existing_user_ids:
                continue
            assignment = CampaignAssignment(
                tenant_id=tenant_id,
                campaign_id=campaign.id,
                user_id=user_id,
                status=AssignmentStatus.PENDING,
                assigned_at=now,
                due_at=due_at,
            )
            self.db.add(assignment)
            new_assignments.append(assignment)

        campaign.status = CampaignStatus.ACTIVE
        campaign.launched_at = now
        campaign.launched_by_id = launched_by_id

        await self.db.commit()

        notified_count = await self._notify_and_email_assignments(
            campaign=campaign,
            assignments=new_assignments,
            launched_by_id=launched_by_id,
        )

        return {
            "campaign_id": campaign.id,
            "assigned_count": len(new_assignments),
            "notified_count": notified_count,
            "status": campaign.status.value if hasattr(campaign.status, "value") else str(campaign.status),
            "launched_at": campaign.launched_at,
        }

    async def _notify_and_email_assignments(
        self,
        *,
        campaign: DocumentCampaign,
        assignments: List[CampaignAssignment],
        launched_by_id: int,
    ) -> int:
        if not assignments:
            return 0

        doc_title = await self._document_title(tenant_id=campaign.tenant_id, document_id=campaign.document_id)
        action_url = f"/documents/{campaign.document_id}"
        message = (
            f"You have been assigned to read{' and complete a quiz for' if campaign.require_quiz else ''} "
            f"'{doc_title}'."
        )

        notified_count = 0
        for assignment in assignments:
            try:
                self.db.add(
                    Notification(
                        tenant_id=campaign.tenant_id,
                        user_id=assignment.user_id,
                        type=NotificationType.ASSIGNMENT,
                        priority=NotificationPriority.MEDIUM,
                        title="New document campaign assigned",
                        message=message,
                        entity_type="document_campaign",
                        entity_id=str(campaign.id),
                        action_url=action_url,
                        sender_id=launched_by_id,
                    )
                )
                notified_count += 1
            except Exception:  # noqa: BLE001 - best-effort, must not fail launch
                logger.warning(
                    "Failed to create in-app notification for user %s campaign %s",
                    assignment.user_id,
                    campaign.id,
                    exc_info=True,
                )

        await self.db.commit()

        await self._send_launch_emails(
            assignments=assignments,
            subject="New document campaign assigned",
            html_content=f"<p>{message}</p>",
        )

        return notified_count

    async def _send_launch_emails(
        self,
        *,
        assignments: List[CampaignAssignment],
        subject: str,
        html_content: str,
    ) -> None:
        """Best-effort email delivery. Never raises — launch must not fail on email issues."""
        try:
            from src.domain.services.email_service import EmailService

            email_service = EmailService()
        except Exception:  # noqa: BLE001
            logger.warning("EmailService unavailable; skipping campaign launch emails", exc_info=True)
            return

        for assignment in assignments:
            try:
                recipient = await self._user_email(assignment.user_id)
                if not recipient:
                    continue
                await email_service.send_email(to=[recipient], subject=subject, html_content=html_content)
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Best-effort campaign launch email failed for user %s",
                    assignment.user_id,
                    exc_info=True,
                )

    async def _document_title(self, *, tenant_id: int, document_id: int) -> str:
        result = await self.db.execute(select(Document.title).where(Document.id == document_id))
        title = result.scalar_one_or_none()
        return title or "the document"

    async def _user_email(self, user_id: int) -> Optional[str]:
        result = await self.db.execute(select(User.email).where(User.id == user_id))
        return result.scalar_one_or_none()

    # ==================== Engineer-facing Assignment APIs ====================

    async def get_my_assignments(self, *, tenant_id: int, user_id: int) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            select(CampaignAssignment, DocumentCampaign, Document)
            .join(DocumentCampaign, DocumentCampaign.id == CampaignAssignment.campaign_id)
            .join(Document, Document.id == DocumentCampaign.document_id)
            .where(
                CampaignAssignment.user_id == user_id,
                CampaignAssignment.tenant_id == tenant_id,
                CampaignAssignment.status.in_(
                    [AssignmentStatus.PENDING, AssignmentStatus.OVERDUE, AssignmentStatus.COMPLETED]
                ),
            )
            .order_by(CampaignAssignment.due_at)
        )
        return [
            {"assignment": assignment, "campaign": campaign, "document": document}
            for assignment, campaign, document in result.all()
        ]

    async def _get_own_assignment(self, *, user_id: int, assignment_id: int) -> CampaignAssignment:
        result = await self.db.execute(select(CampaignAssignment).where(CampaignAssignment.id == assignment_id))
        assignment = result.scalar_one_or_none()
        if assignment is None or assignment.user_id != user_id:
            raise NotFoundError("Assignment not found")
        return assignment

    async def record_assignment_opened(self, *, user_id: int, assignment_id: int) -> CampaignAssignment:
        assignment = await self._get_own_assignment(user_id=user_id, assignment_id=assignment_id)
        if assignment.first_opened_at is None:
            assignment.first_opened_at = datetime.now(timezone.utc)
            await self.db.commit()
            await self.db.refresh(assignment)
        return assignment

    async def get_assignment_quiz(self, *, user_id: int, assignment_id: int) -> Dict[str, Any]:
        assignment = await self._get_own_assignment(user_id=user_id, assignment_id=assignment_id)
        campaign = await self.get_campaign(tenant_id=assignment.tenant_id, campaign_id=assignment.campaign_id)

        if not campaign.quiz_questions:
            raise NotFoundError("No quiz for this assignment")

        return {
            "questions": strip_quiz_answer_keys(campaign.quiz_questions),
            "pass_mark": campaign.quiz_pass_mark or 70,
        }

    async def submit_assignment_quiz(
        self,
        *,
        user_id: int,
        assignment_id: int,
        answers: List[Dict[str, Any]],
    ) -> QuizGradeResult:
        assignment = await self._get_own_assignment(user_id=user_id, assignment_id=assignment_id)
        campaign = await self.get_campaign(tenant_id=assignment.tenant_id, campaign_id=assignment.campaign_id)

        if not campaign.quiz_questions:
            raise NotFoundError("No quiz for this assignment")

        result = grade_quiz_answers(campaign.quiz_questions, answers, campaign.quiz_pass_mark or 70)

        assignment.quiz_score = result.score
        assignment.quiz_passed = result.passed
        assignment.quiz_attempts += 1
        assignment.quiz_review_needed = result.review_needed
        assignment.last_quiz_answers = answers

        await self.db.commit()
        await self.db.refresh(assignment)
        return result

    async def complete_assignment(
        self,
        *,
        user_id: int,
        assignment_id: int,
        acceptance_statement: str,
        signature_data: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CampaignAssignment:
        assignment = await self._get_own_assignment(user_id=user_id, assignment_id=assignment_id)
        campaign = await self.get_campaign(tenant_id=assignment.tenant_id, campaign_id=assignment.campaign_id)

        if campaign.require_quiz and not assignment.quiz_passed:
            raise BadRequestError("Quiz must be passed before completing this assignment")

        assignment.status = AssignmentStatus.COMPLETED
        assignment.completed_at = datetime.now(timezone.utc)
        assignment.acceptance_statement = acceptance_statement
        assignment.signature_data = signature_data
        assignment.ip_address = ip_address
        assignment.user_agent = user_agent

        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    # ==================== Reminder defaults (SystemSetting) ====================

    async def get_reminder_defaults(self, *, tenant_id: int) -> List[int]:
        result = await self.db.execute(
            select(SystemSetting).where(
                SystemSetting.tenant_id == tenant_id,
                SystemSetting.key == CAMPAIGN_DEFAULT_REMINDER_SETTING_KEY,
            )
        )
        setting = result.scalar_one_or_none()
        if setting is None:
            return list(DEFAULT_REMINDER_OFFSETS_HOURS)
        try:
            parsed = json.loads(setting.value)
            if isinstance(parsed, list) and all(isinstance(h, int) for h in parsed):
                return sorted(parsed)
        except (json.JSONDecodeError, TypeError):
            logger.warning("Invalid %s setting for tenant %s", CAMPAIGN_DEFAULT_REMINDER_SETTING_KEY, tenant_id)
        return list(DEFAULT_REMINDER_OFFSETS_HOURS)

    async def set_reminder_defaults(
        self,
        *,
        tenant_id: int,
        hours: List[int],
        user_id: int,
    ) -> List[int]:
        if not hours or any(h < 0 for h in hours):
            raise BadRequestError("reminder_hours must be a non-empty list of non-negative integers")

        normalized = sorted(dict.fromkeys(int(h) for h in hours))
        result = await self.db.execute(
            select(SystemSetting).where(
                SystemSetting.tenant_id == tenant_id,
                SystemSetting.key == CAMPAIGN_DEFAULT_REMINDER_SETTING_KEY,
            )
        )
        setting = result.scalar_one_or_none()
        if setting is None:
            setting = SystemSetting(
                tenant_id=tenant_id,
                key=CAMPAIGN_DEFAULT_REMINDER_SETTING_KEY,
                value=json.dumps(normalized),
                category=CAMPAIGN_DEFAULT_REMINDER_CATEGORY,
                value_type="json",
                description="Default reminder offsets (hours after launch) for new document campaigns",
                created_by_id=user_id,
            )
            self.db.add(setting)
        else:
            setting.value = json.dumps(normalized)
            setting.updated_by_id = user_id

        await self.db.commit()
        return normalized

    # ==================== Scheduled reminders (Celery) ====================

    async def process_due_reminders(self) -> Dict[str, int]:
        """Process overdue marking and due reminder sends across all tenants."""
        now = datetime.now(timezone.utc)
        counts = {"reminders_sent": 0, "overdue_marked": 0, "campaigns_scanned": 0}

        result = await self.db.execute(
            select(DocumentCampaign).where(
                DocumentCampaign.status == CampaignStatus.ACTIVE,
                DocumentCampaign.launched_at.isnot(None),
            )
        )
        campaigns = list(result.scalars().all())
        counts["campaigns_scanned"] = len(campaigns)

        for campaign in campaigns:
            launched_at = campaign.launched_at
            if launched_at is None:
                continue
            if launched_at.tzinfo is None:
                launched_at = launched_at.replace(tzinfo=timezone.utc)

            hours_since_launch = (now - launched_at).total_seconds() / 3600
            sorted_offsets = sorted(campaign.reminder_offsets_hours or [])

            assignments_result = await self.db.execute(
                select(CampaignAssignment).where(
                    CampaignAssignment.campaign_id == campaign.id,
                    CampaignAssignment.status.in_([AssignmentStatus.PENDING, AssignmentStatus.OVERDUE]),
                )
            )
            assignments = list(assignments_result.scalars().all())
            reminders_to_send: List[CampaignAssignment] = []

            for assignment in assignments:
                due_at = assignment.due_at
                if due_at is not None and due_at.tzinfo is None:
                    due_at = due_at.replace(tzinfo=timezone.utc)

                if assignment.status == AssignmentStatus.PENDING and due_at is not None and due_at < now:
                    assignment.status = AssignmentStatus.OVERDUE
                    counts["overdue_marked"] += 1

                if assignment.reminders_sent < len(sorted_offsets):
                    threshold = sorted_offsets[assignment.reminders_sent]
                    if hours_since_launch >= threshold:
                        assignment.reminders_sent += 1
                        assignment.last_reminder_at = now
                        counts["reminders_sent"] += 1
                        reminders_to_send.append(assignment)

            if reminders_to_send:
                await self._notify_and_email_reminders(campaign=campaign, assignments=reminders_to_send)

        await self.db.commit()
        return counts

    async def _notify_and_email_reminders(
        self,
        *,
        campaign: DocumentCampaign,
        assignments: List[CampaignAssignment],
    ) -> None:
        if not assignments:
            return

        doc_title = await self._document_title(tenant_id=campaign.tenant_id, document_id=campaign.document_id)
        action_url = f"/documents/{campaign.document_id}"
        message = f"Reminder: please complete your read/sign-off for '{doc_title}'."

        for assignment in assignments:
            try:
                self.db.add(
                    Notification(
                        tenant_id=campaign.tenant_id,
                        user_id=assignment.user_id,
                        type=NotificationType.ASSIGNMENT,
                        priority=NotificationPriority.MEDIUM,
                        title="Document campaign reminder",
                        message=message,
                        entity_type="document_campaign",
                        entity_id=str(campaign.id),
                        action_url=action_url,
                    )
                )
            except Exception:  # noqa: BLE001
                logger.warning(
                    "Failed to create reminder notification for user %s campaign %s",
                    assignment.user_id,
                    campaign.id,
                    exc_info=True,
                )

        await self.db.commit()

        await self._send_launch_emails(
            assignments=assignments,
            subject="Document campaign reminder",
            html_content=f"<p>{message}</p>",
        )

    # ==================== Compliance summary & evidence ====================

    async def list_compliance_summary(self, *, tenant_id: int) -> List[Dict[str, Any]]:
        result = await self.db.execute(
            select(DocumentCampaign, Document.title)
            .join(Document, Document.id == DocumentCampaign.document_id)
            .where(DocumentCampaign.tenant_id == tenant_id)
            .order_by(DocumentCampaign.created_at.desc())
        )

        items: List[Dict[str, Any]] = []
        for campaign, document_title in result.all():
            summary = await self._compliance_summary(campaign.id)
            quiz_pass_result = await self.db.execute(
                select(func.count(CampaignAssignment.id)).where(
                    CampaignAssignment.campaign_id == campaign.id,
                    CampaignAssignment.quiz_passed == True,  # noqa: E712
                )
            )
            quiz_pass_count = quiz_pass_result.scalar_one() or 0
            status_value = campaign.status.value if hasattr(campaign.status, "value") else str(campaign.status)

            items.append(
                {
                    "campaign_id": campaign.id,
                    "document_id": campaign.document_id,
                    "document_title": document_title,
                    "title": campaign.title,
                    "status": status_value,
                    "assigned": summary["total_assigned"],
                    "completed": summary["completed"],
                    "pending": summary["pending"],
                    "overdue": summary["overdue"],
                    "completion_rate": summary["completion_rate"],
                    "quiz_pass_count": quiz_pass_count,
                    "reminder_offsets_hours": list(campaign.reminder_offsets_hours or []),
                    "launched_at": campaign.launched_at,
                    "due_within_days": campaign.due_within_days,
                }
            )
        return items

    async def build_evidence_pack(self, *, tenant_id: int, campaign_id: int) -> Dict[str, Any]:
        campaign = await self.get_campaign(tenant_id=tenant_id, campaign_id=campaign_id)

        doc_result = await self.db.execute(
            select(Document).where(Document.id == campaign.document_id, Document.tenant_id == tenant_id)
        )
        document = doc_result.scalar_one_or_none()
        if document is None:
            raise NotFoundError("Document not found")

        assignments_result = await self.db.execute(
            select(CampaignAssignment, User)
            .join(User, User.id == CampaignAssignment.user_id)
            .where(CampaignAssignment.campaign_id == campaign_id)
            .order_by(User.last_name, User.first_name)
        )

        assignment_rows = []
        for assignment, user in assignments_result.all():
            status_value = assignment.status.value if hasattr(assignment.status, "value") else str(assignment.status)
            assignment_rows.append(
                {
                    "assignment_id": assignment.id,
                    "user_id": user.id,
                    "user_email": user.email,
                    "user_name": user.full_name,
                    "status": status_value,
                    "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
                    "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
                    "first_opened_at": assignment.first_opened_at.isoformat() if assignment.first_opened_at else None,
                    "completed_at": assignment.completed_at.isoformat() if assignment.completed_at else None,
                    "quiz_score": assignment.quiz_score,
                    "quiz_passed": assignment.quiz_passed,
                    "quiz_attempts": assignment.quiz_attempts,
                    "acceptance_statement_present": bool(assignment.acceptance_statement),
                    "signature_present": bool(assignment.signature_data),
                    "ip_address": assignment.ip_address,
                    "reminders_sent": assignment.reminders_sent,
                    "last_reminder_at": assignment.last_reminder_at.isoformat() if assignment.last_reminder_at else None,
                }
            )

        status_value = campaign.status.value if hasattr(campaign.status, "value") else str(campaign.status)
        return {
            "campaign": {
                "id": campaign.id,
                "title": campaign.title,
                "status": status_value,
                "due_within_days": campaign.due_within_days,
                "require_quiz": campaign.require_quiz,
                "require_sign": campaign.require_sign,
                "reminder_offsets_hours": list(campaign.reminder_offsets_hours or []),
                "launched_at": campaign.launched_at.isoformat() if campaign.launched_at else None,
                "closed_at": campaign.closed_at.isoformat() if campaign.closed_at else None,
            },
            "document": {
                "id": document.id,
                "title": document.title,
                "version": document.version,
            },
            "assignments": assignment_rows,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

    # ==================== Question inbox (HSEC) ====================

    async def list_question_inbox(self, *, tenant_id: int) -> List[Dict[str, Any]]:
        campaign_doc_ids = (
            select(DocumentCampaign.document_id)
            .where(DocumentCampaign.tenant_id == tenant_id)
            .distinct()
            .scalar_subquery()
        )

        result = await self.db.execute(
            select(DocumentDiscussionThread, Document.title)
            .join(Document, Document.id == DocumentDiscussionThread.document_id)
            .where(
                DocumentDiscussionThread.tenant_id == tenant_id,
                DocumentDiscussionThread.status == DiscussionThreadStatus.OPEN,
                DocumentDiscussionThread.document_id.in_(campaign_doc_ids),
            )
            .order_by(DocumentDiscussionThread.created_at.desc())
        )

        items: List[Dict[str, Any]] = []
        for thread, document_title in result.all():
            latest_result = await self.db.execute(
                select(DocumentDiscussionMessage.body)
                .where(DocumentDiscussionMessage.thread_id == thread.id)
                .order_by(DocumentDiscussionMessage.created_at.desc())
                .limit(1)
            )
            latest_preview = latest_result.scalar_one_or_none()
            status_value = thread.status.value if hasattr(thread.status, "value") else str(thread.status)
            items.append(
                {
                    "document_id": thread.document_id,
                    "document_title": document_title,
                    "thread_id": thread.id,
                    "thread_title": thread.title,
                    "status": status_value,
                    "created_at": thread.created_at,
                    "created_by_id": thread.created_by_id,
                    "latest_message_preview": (latest_preview[:200] if latest_preview else None),
                }
            )
        return items

    async def ask_assignment_question(
        self,
        *,
        user_id: int,
        assignment_id: int,
        title: Optional[str],
        body: str,
    ) -> DocumentDiscussionThread:
        assignment = await self._get_own_assignment(user_id=user_id, assignment_id=assignment_id)
        campaign = await self.get_campaign(tenant_id=assignment.tenant_id, campaign_id=assignment.campaign_id)

        doc_result = await self.db.execute(
            select(Document).where(
                Document.id == campaign.document_id,
                Document.tenant_id == assignment.tenant_id,
            )
        )
        document = doc_result.scalar_one_or_none()
        if document is None:
            raise NotFoundError("Document not found")

        thread = DocumentDiscussionThread(
            tenant_id=assignment.tenant_id,
            document_id=campaign.document_id,
            version=document.version or "1.0",
            title=title or f"Question on campaign assignment #{assignment.id}",
            created_by_id=user_id,
        )
        self.db.add(thread)
        await self.db.flush()

        message = DocumentDiscussionMessage(
            tenant_id=assignment.tenant_id,
            thread_id=thread.id,
            author_id=user_id,
            body=body,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(thread)
        return thread

    async def _get_thread(self, *, tenant_id: int, thread_id: int) -> DocumentDiscussionThread:
        result = await self.db.execute(
            select(DocumentDiscussionThread).where(
                DocumentDiscussionThread.id == thread_id,
                DocumentDiscussionThread.tenant_id == tenant_id,
            )
        )
        thread = result.scalar_one_or_none()
        if thread is None:
            raise NotFoundError("Discussion thread not found")
        return thread

    async def resolve_question(self, *, tenant_id: int, thread_id: int, resolver_id: int) -> DocumentDiscussionThread:
        thread = await self._get_thread(tenant_id=tenant_id, thread_id=thread_id)
        thread.status = DiscussionThreadStatus.RESOLVED
        await self.db.commit()
        await self.db.refresh(thread)
        return thread

    async def reply_question(
        self,
        *,
        tenant_id: int,
        thread_id: int,
        author_id: int,
        body: str,
    ) -> DocumentDiscussionMessage:
        thread = await self._get_thread(tenant_id=tenant_id, thread_id=thread_id)
        message = DocumentDiscussionMessage(
            tenant_id=tenant_id,
            thread_id=thread.id,
            author_id=author_id,
            body=body,
        )
        self.db.add(message)
        await self.db.commit()
        await self.db.refresh(message)
        return message
