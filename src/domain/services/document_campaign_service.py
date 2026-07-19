"""Document Campaign Service.

Manages engineer groups, document campaigns (read/quiz/sign-off), audience
expansion, launch notifications, and per-user assignment progress.
"""

import csv
import io
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
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
from src.domain.services.document_campaign_notifications import (
    build_assignment_notification_kwargs,
    build_overdue_notification_kwargs,
    build_reminder_notification_kwargs,
    overdue_escalation_recipients,
    overdue_recipient_role,
    portal_assignment_action_url,
    reminder_due_now,
    user_display_name,
)

logger = logging.getLogger(__name__)

MAX_QUIZ_ATTEMPTS = 3
OPEN_QUESTION_TYPES = frozenset({"open", "open_text", "text"})
SIGNATURE_DISPOSITION_SIGNED = "signed"
SIGNATURE_DISPOSITION_SIGNED_PENDING_HSEQ = "signed_pending_hseq_answer"
SIGNATURE_DISPOSITION_DEFERRED = "signature_deferred_pending_answer"
VALID_SIGNATURE_DISPOSITIONS = frozenset(
    {
        SIGNATURE_DISPOSITION_SIGNED,
        SIGNATURE_DISPOSITION_SIGNED_PENDING_HSEQ,
        SIGNATURE_DISPOSITION_DEFERRED,
    }
)

CAMPAIGN_DEFAULT_REMINDER_SETTING_KEY_PREFIX = "campaign.default_reminder_hours"
CAMPAIGN_DEFAULT_REMINDER_CATEGORY = "campaigns"


def _reminder_defaults_setting_key(tenant_id: int) -> str:
    """Tenant-scoped key — SystemSetting.key is globally unique."""
    return f"{CAMPAIGN_DEFAULT_REMINDER_SETTING_KEY_PREFIX}.tenant.{tenant_id}"


@dataclass(frozen=True)
class QuizGradeResult:
    """Outcome of grading a submitted quiz attempt."""

    score: int
    passed: bool
    pass_mark: int
    review_needed: bool
    quiz_attempts: int = 0
    attempts_remaining: int = 0


def _is_open_question_type(question_type: str) -> bool:
    return str(question_type or "").strip().lower() in OPEN_QUESTION_TYPES


def _normalize_quiz_question_for_delivery(question: Dict[str, Any]) -> Dict[str, Any]:
    """Coerce MCQ questions with missing/empty options to open-ended delivery."""
    normalized = dict(question)
    question_type = str(normalized.get("type") or "mcq").strip().lower()
    if question_type == "mcq":
        options = normalized.get("options")
        if not options:
            normalized["type"] = "open"
    return normalized


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

        if _is_open_question_type(question_type):
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
        normalized = _normalize_quiz_question_for_delivery(question)
        clean = {k: v for k, v in normalized.items() if k != "correct_answer"}
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

        if not user_ids:
            return []

        result = await self.db.execute(
            select(User.id).where(
                User.id.in_(user_ids),
                User.tenant_id == tenant_id,
                User.is_active == True,  # noqa: E712
            )
        )
        return sorted(result.scalars().all())

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
        if not user_ids:
            raise BadRequestError("No valid active users in campaign audience — check user IDs / groups")

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

        notified_count = 0
        try:
            notified_count = await self._notify_and_email_assignments(
                campaign=campaign,
                assignments=new_assignments,
                launched_by_id=launched_by_id,
            )
        except Exception:  # noqa: BLE001 - launch must succeed once assignments are committed
            logger.warning(
                "Campaign %s launched but notification/email delivery failed",
                campaign.id,
                exc_info=True,
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
        welcome_paragraph = await self._generate_campaign_welcome_paragraph(
            doc_title=doc_title,
            require_quiz=bool(campaign.require_quiz),
        )
        frontend_base = self._frontend_base_url()

        notified_count = 0
        for assignment in assignments:
            try:
                self.db.add(
                    Notification(
                        **build_assignment_notification_kwargs(
                            tenant_id=campaign.tenant_id,
                            user_id=assignment.user_id,
                            campaign_id=campaign.id,
                            assignment_id=assignment.id,
                            document_id=campaign.document_id,
                            doc_title=doc_title,
                            require_quiz=bool(campaign.require_quiz),
                            sender_id=launched_by_id,
                        )
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

        try:
            await self.db.commit()
        except Exception:  # noqa: BLE001 - best-effort, must not fail launch
            logger.warning(
                "Failed to commit in-app notifications for campaign %s",
                campaign.id,
                exc_info=True,
            )
            return 0

        await self._send_launch_emails(
            assignments=assignments,
            doc_title=doc_title,
            require_quiz=bool(campaign.require_quiz),
            welcome_paragraph=welcome_paragraph,
            frontend_base=frontend_base,
        )

        return notified_count

    @staticmethod
    def _frontend_base_url() -> str:
        return (getattr(settings, "frontend_url", None) or "http://localhost:5173").rstrip("/")

    async def _generate_campaign_welcome_paragraph(self, *, doc_title: str, require_quiz: bool) -> str:
        """Best-effort AI welcome line for launch emails; falls back to static copy."""
        static = (
            f"You have been assigned to read{' and complete a quiz for' if require_quiz else ''} " f"'{doc_title}'."
        )
        try:
            from src.domain.services.document_ai_service import DocumentAIService
            from src.domain.services.upstream_circuit_breaker import call_via_upstream_breaker

            ai_service = DocumentAIService()
            if not ai_service.api_key:
                return static

            import httpx

            prompt = (
                f"Write one short, friendly welcome sentence (max 35 words) for an employee "
                f"assigned to read the document '{doc_title}'"
                f"{' and pass a comprehension quiz' if require_quiz else ''}. "
                "Do not include links or bullet points."
            )

            async def _do_call() -> dict:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{ai_service.base_url}/messages",
                        headers={
                            "x-api-key": ai_service.api_key,
                            "anthropic-version": "2023-06-01",
                            "content-type": "application/json",
                        },
                        json={
                            "model": ai_service.model,
                            "max_tokens": 120,
                            "system": "You write concise, professional internal communications.",
                            "messages": [{"role": "user", "content": prompt}],
                        },
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    return response.json()

            data = await call_via_upstream_breaker("document_ai", _do_call)
            text = str(data.get("content", [{}])[0].get("text", "")).strip()
            return text or static
        except Exception:  # noqa: BLE001 - launch must not fail on AI issues
            logger.warning("Campaign launch welcome AI generation failed; using static copy", exc_info=True)
            return static

    @staticmethod
    def _build_launch_email_html(
        *,
        welcome_paragraph: str,
        doc_title: str,
        require_quiz: bool,
        assignment_id: int,
        frontend_base: str,
    ) -> str:
        reading_url = f"{frontend_base}/portal/reading?assignment={assignment_id}"
        work_url = f"{frontend_base}/portal/work"
        steps = (
            "read the document, complete the quiz, and sign your attestation"
            if require_quiz
            else ("read the document and sign your attestation")
        )
        return f"""<p>{welcome_paragraph}</p>
<p>Your assignment for <strong>{doc_title}</strong> is ready. Please {steps}.</p>
<p><a href="{reading_url}">Open your reading assignment</a></p>
<p><a href="{work_url}">View all portal work</a></p>"""

    @staticmethod
    def _build_reminder_email_html(
        *,
        doc_title: str,
        due_at,
        assignment_id: int,
        frontend_base: str,
    ) -> str:
        reading_url = f"{frontend_base}{portal_assignment_action_url(assignment_id)}"
        due_label = due_at.date().isoformat() if hasattr(due_at, "date") else str(due_at)
        return f"""<p>Reminder: your assignment for <strong>{doc_title}</strong> is due by {due_label}.</p>
<p><a href="{reading_url}">Open your reading assignment</a></p>"""

    @staticmethod
    def _build_overdue_email_html(
        *,
        doc_title: str,
        assignment_id: int,
        frontend_base: str,
    ) -> str:
        reading_url = f"{frontend_base}{portal_assignment_action_url(assignment_id)}"
        return f"""<p>Your assignment for <strong>{doc_title}</strong> is now overdue. Please complete it as soon as possible.</p>
<p><a href="{reading_url}">Open your reading assignment</a></p>"""

    async def _send_assignee_campaign_email(
        self,
        *,
        user_id: int,
        subject: str,
        html_content: str,
    ) -> None:
        """Best-effort email to a campaign assignee. Never raises."""
        try:
            from src.domain.services.email_service import EmailService

            recipient = await self._user_email(user_id)
            if not recipient:
                return
            email_service = EmailService()
            await email_service.send_email(to=[recipient], subject=subject, html_content=html_content)
        except Exception:  # noqa: BLE001
            logger.warning(
                "Best-effort campaign email failed for user %s",
                user_id,
                exc_info=True,
            )

    async def _send_launch_emails(
        self,
        *,
        assignments: List[CampaignAssignment],
        doc_title: str,
        require_quiz: bool,
        welcome_paragraph: str,
        frontend_base: str,
    ) -> None:
        """Best-effort email delivery. Never raises — launch must not fail on email issues."""
        try:
            from src.domain.services.email_service import EmailService

            email_service = EmailService()
        except Exception:  # noqa: BLE001
            logger.warning("EmailService unavailable; skipping campaign launch emails", exc_info=True)
            return

        subject = "New document campaign assigned"
        for assignment in assignments:
            try:
                recipient = await self._user_email(assignment.user_id)
                if not recipient:
                    continue
                html_content = self._build_launch_email_html(
                    welcome_paragraph=welcome_paragraph,
                    doc_title=doc_title,
                    require_quiz=require_quiz,
                    assignment_id=assignment.id,
                    frontend_base=frontend_base,
                )
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

    # ==================== Reminders + overdue escalation ====================

    async def process_due_reminders(self, *, now: Optional[datetime] = None) -> Dict[str, int]:
        """Send scheduled reminders and escalate overdue pending assignments.

        Best-effort throughout — notification failures are logged and never abort
        the sweep. Intended to be invoked from the Celery beat task.
        """
        current = now or datetime.now(timezone.utc)
        results = {
            "assignments_scanned": 0,
            "reminders_sent": 0,
            "overdue_escalated": 0,
            "notifications_created": 0,
        }
        # Queue outbound mail until after commit (matches launch): email cannot roll back,
        # so sending first risks duplicate CTAs if the sweep retries after a commit failure.
        pending_emails: List[Dict[str, Any]] = []

        pending_result = await self.db.execute(
            select(CampaignAssignment, DocumentCampaign)
            .join(DocumentCampaign, DocumentCampaign.id == CampaignAssignment.campaign_id)
            .where(
                DocumentCampaign.status == CampaignStatus.ACTIVE,
                CampaignAssignment.status == AssignmentStatus.PENDING,
            )
        )
        rows = pending_result.all()
        results["assignments_scanned"] = len(rows)
        if not rows:
            return results

        user_ids = {assignment.user_id for assignment, _campaign in rows}
        users_result = await self.db.execute(select(User).where(User.id.in_(user_ids)))
        users_by_id = {user.id: user for user in users_result.scalars().all()}

        doc_titles: Dict[int, str] = {}

        for assignment, campaign in rows:
            try:
                due_at = assignment.due_at
                if due_at.tzinfo is None:
                    due_at = due_at.replace(tzinfo=timezone.utc)

                if current > due_at:
                    assignment.status = AssignmentStatus.OVERDUE
                    results["overdue_escalated"] += 1

                    doc_title = await self._cached_document_title(
                        cache=doc_titles,
                        tenant_id=campaign.tenant_id,
                        document_id=campaign.document_id,
                    )
                    assignee = users_by_id.get(assignment.user_id)
                    assignee_name = user_display_name(assignee, assignment.user_id)

                    for recipient_id in overdue_escalation_recipients(
                        assignee_user_id=assignment.user_id,
                        assignee_user=assignee,
                        created_by_id=campaign.created_by_id,
                        launched_by_id=campaign.launched_by_id,
                    ):
                        role = overdue_recipient_role(
                            recipient_user_id=recipient_id,
                            assignee_user_id=assignment.user_id,
                            assignee_user=assignee,
                        )
                        if self._add_campaign_notification(
                            build_overdue_notification_kwargs(
                                tenant_id=campaign.tenant_id,
                                user_id=recipient_id,
                                campaign_id=campaign.id,
                                assignment_id=assignment.id,
                                document_id=campaign.document_id,
                                doc_title=doc_title,
                                assignee_user_id=assignment.user_id,
                                assignee_display_name=assignee_name,
                                recipient_role=role,
                            )
                        ):
                            results["notifications_created"] += 1
                            if recipient_id == assignment.user_id:
                                frontend_base = settings.frontend_url.rstrip("/")
                                pending_emails.append(
                                    {
                                        "user_id": recipient_id,
                                        "subject": "Document campaign overdue",
                                        "html_content": self._build_overdue_email_html(
                                            doc_title=doc_title,
                                            assignment_id=assignment.id,
                                            frontend_base=frontend_base,
                                        ),
                                    }
                                )
                    continue

                offsets = campaign.reminder_offsets_hours or DEFAULT_REMINDER_OFFSETS_HOURS
                if not reminder_due_now(
                    now=current,
                    due_at=due_at,
                    reminders_sent=assignment.reminders_sent,
                    reminder_offsets_hours=offsets,
                ):
                    continue

                if self._is_snoozed(assignment, current):
                    continue

                doc_title = await self._cached_document_title(
                    cache=doc_titles,
                    tenant_id=campaign.tenant_id,
                    document_id=campaign.document_id,
                )
                if self._add_campaign_notification(
                    build_reminder_notification_kwargs(
                        tenant_id=campaign.tenant_id,
                        user_id=assignment.user_id,
                        campaign_id=campaign.id,
                        assignment_id=assignment.id,
                        document_id=campaign.document_id,
                        doc_title=doc_title,
                        due_at=due_at,
                    )
                ):
                    results["notifications_created"] += 1
                    results["reminders_sent"] += 1
                    frontend_base = settings.frontend_url.rstrip("/")
                    pending_emails.append(
                        {
                            "user_id": assignment.user_id,
                            "subject": "Document campaign reminder",
                            "html_content": self._build_reminder_email_html(
                                doc_title=doc_title,
                                due_at=due_at,
                                assignment_id=assignment.id,
                                frontend_base=frontend_base,
                            ),
                        }
                    )

                assignment.reminders_sent += 1
                assignment.last_reminder_at = current
            except Exception:  # noqa: BLE001 - best-effort per assignment
                logger.warning(
                    "Campaign reminder/overdue processing failed for assignment %s",
                    assignment.id,
                    exc_info=True,
                )

        await self.db.commit()
        for email in pending_emails:
            await self._send_assignee_campaign_email(
                user_id=email["user_id"],
                subject=email["subject"],
                html_content=email["html_content"],
            )
        return results

    async def _cached_document_title(
        self,
        *,
        cache: Dict[int, str],
        tenant_id: int,
        document_id: int,
    ) -> str:
        if document_id not in cache:
            cache[document_id] = await self._document_title(tenant_id=tenant_id, document_id=document_id)
        return cache[document_id]

    def _add_campaign_notification(self, kwargs: Dict[str, Any]) -> bool:
        """Best-effort notification insert. Returns True when queued."""
        try:
            self.db.add(Notification(**kwargs))
            return True
        except Exception:  # noqa: BLE001
            logger.warning(
                "Failed to create campaign notification for user %s entity %s/%s",
                kwargs.get("user_id"),
                kwargs.get("entity_type"),
                kwargs.get("entity_id"),
                exc_info=True,
            )
            return False

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

    async def get_assignment_document_url(
        self,
        *,
        user_id: int,
        assignment_id: int,
        expires_in_seconds: int = 3600,
    ) -> Dict[str, Any]:
        """Return a signed document URL when the user owns an eligible campaign assignment."""
        from src.infrastructure.storage import storage_service

        assignment = await self._get_own_assignment(user_id=user_id, assignment_id=assignment_id)
        if assignment.status not in (
            AssignmentStatus.PENDING,
            AssignmentStatus.OVERDUE,
            AssignmentStatus.COMPLETED,
        ):
            raise BadRequestError("Document access is only available for owned campaign assignments")

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

        document.download_count += 1
        document.last_accessed_at = datetime.now(timezone.utc)
        await self.db.commit()

        filename = document.file_name or "download"
        signed_url = storage_service().get_signed_url(
            storage_key=document.file_path,
            expires_in_seconds=expires_in_seconds,
            content_disposition=None,
        )
        return {
            "assignment_id": assignment.id,
            "document_id": document.id,
            "signed_url": signed_url,
            "expires_in_seconds": expires_in_seconds,
            "filename": filename,
            "content_type": document.mime_type,
        }

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

        if assignment.quiz_attempts >= MAX_QUIZ_ATTEMPTS:
            raise BadRequestError(f"Maximum quiz attempts ({MAX_QUIZ_ATTEMPTS}) reached")

        result = grade_quiz_answers(campaign.quiz_questions, answers, campaign.quiz_pass_mark or 70)

        assignment.quiz_score = result.score
        assignment.quiz_passed = result.passed
        assignment.quiz_attempts += 1
        assignment.quiz_review_needed = result.review_needed
        assignment.last_quiz_answers = answers

        await self.db.commit()
        await self.db.refresh(assignment)
        attempts_remaining = max(0, MAX_QUIZ_ATTEMPTS - assignment.quiz_attempts)
        return QuizGradeResult(
            score=result.score,
            passed=result.passed,
            pass_mark=result.pass_mark,
            review_needed=result.review_needed,
            quiz_attempts=assignment.quiz_attempts,
            attempts_remaining=attempts_remaining,
        )

    async def _has_open_assignee_question(
        self,
        *,
        tenant_id: int,
        user_id: int,
        document_id: int,
    ) -> bool:
        result = await self.db.execute(
            select(func.count(DocumentDiscussionThread.id)).where(
                DocumentDiscussionThread.tenant_id == tenant_id,
                DocumentDiscussionThread.document_id == document_id,
                DocumentDiscussionThread.created_by_id == user_id,
                DocumentDiscussionThread.status == DiscussionThreadStatus.OPEN,
            )
        )
        return (result.scalar_one() or 0) > 0

    async def complete_assignment(
        self,
        *,
        user_id: int,
        assignment_id: int,
        acceptance_statement: str,
        signature_data: Optional[str] = None,
        signature_disposition: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> CampaignAssignment:
        assignment = await self._get_own_assignment(user_id=user_id, assignment_id=assignment_id)
        campaign = await self.get_campaign(tenant_id=assignment.tenant_id, campaign_id=assignment.campaign_id)

        # O-12 scaffold: when campaign_complete_competence_gate_enabled + feature flag are on,
        # call GovernanceService.check_competency_gate for the linked engineer before completion.
        # See settings.campaign_complete_competence_gate_* and MyCompliancePassport / workforce spine.

        if campaign.require_quiz and not assignment.quiz_passed:
            raise BadRequestError("Quiz must be passed before completing this assignment")

        if signature_disposition is not None and signature_disposition not in VALID_SIGNATURE_DISPOSITIONS:
            raise BadRequestError("Invalid signature_disposition")

        has_open_question = await self._has_open_assignee_question(
            tenant_id=assignment.tenant_id,
            user_id=user_id,
            document_id=campaign.document_id,
        )
        has_signature = bool(signature_data and signature_data.strip())

        if not has_open_question:
            if not has_signature:
                raise BadRequestError("Signature is required to complete this assignment")
            resolved_disposition = signature_disposition or SIGNATURE_DISPOSITION_SIGNED
            if resolved_disposition != SIGNATURE_DISPOSITION_SIGNED:
                raise BadRequestError("signature_disposition must be 'signed' when no open question exists")
        elif has_signature:
            resolved_disposition = signature_disposition or SIGNATURE_DISPOSITION_SIGNED_PENDING_HSEQ
            if resolved_disposition not in (
                SIGNATURE_DISPOSITION_SIGNED_PENDING_HSEQ,
                SIGNATURE_DISPOSITION_SIGNED,
            ):
                raise BadRequestError(
                    "signature_disposition must be signed or signed_pending_hseq_answer when signature is provided"
                )
        else:
            resolved_disposition = signature_disposition or SIGNATURE_DISPOSITION_DEFERRED
            if resolved_disposition != SIGNATURE_DISPOSITION_DEFERRED:
                raise BadRequestError(
                    "signature_disposition must be signature_deferred_pending_answer when completing without signature"
                )

        assignment.status = AssignmentStatus.COMPLETED
        assignment.completed_at = datetime.now(timezone.utc)
        assignment.acceptance_statement = acceptance_statement
        assignment.signature_data = signature_data if has_signature else None
        assignment.signature_disposition = resolved_disposition
        assignment.ip_address = ip_address
        assignment.user_agent = user_agent

        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    async def snooze_assignment(self, *, user_id: int, assignment_id: int, hours: int) -> CampaignAssignment:
        if hours < 1 or hours > 168:
            raise BadRequestError("hours must be between 1 and 168")

        assignment = await self._get_own_assignment(user_id=user_id, assignment_id=assignment_id)
        if assignment.status not in (AssignmentStatus.PENDING, AssignmentStatus.OVERDUE):
            raise BadRequestError("Only pending or overdue assignments can be snoozed")

        assignment.snooze_until = datetime.now(timezone.utc) + timedelta(hours=hours)
        await self.db.commit()
        await self.db.refresh(assignment)
        return assignment

    @staticmethod
    def _is_snoozed(assignment: CampaignAssignment, now: datetime) -> bool:
        snooze_until = getattr(assignment, "snooze_until", None)
        if snooze_until is None:
            return False
        if snooze_until.tzinfo is None:
            snooze_until = snooze_until.replace(tzinfo=timezone.utc)
        return snooze_until > now

    @staticmethod
    def _assignment_stats(assignments: List[CampaignAssignment]) -> Dict[str, Any]:
        assigned = len(assignments)
        completed = sum(1 for a in assignments if a.status == AssignmentStatus.COMPLETED)
        pending = sum(1 for a in assignments if a.status == AssignmentStatus.PENDING)
        overdue = sum(1 for a in assignments if a.status == AssignmentStatus.OVERDUE)
        quiz_pass_count = sum(1 for a in assignments if a.quiz_passed is True)
        completion_rate = round((completed / assigned * 100), 1) if assigned > 0 else 0.0
        return {
            "assigned": assigned,
            "completed": completed,
            "pending": pending,
            "overdue": overdue,
            "quiz_pass_count": quiz_pass_count,
            "completion_rate": completion_rate,
        }

    async def compliance_by_group(self, *, tenant_id: int, campaign_id: int) -> List[Dict[str, Any]]:
        campaign = await self.get_campaign(tenant_id=tenant_id, campaign_id=campaign_id)
        group_ids = [int(gid) for gid in (campaign.audience_group_ids or [])]
        if not group_ids:
            return []

        assignments_result = await self.db.execute(
            select(CampaignAssignment).where(CampaignAssignment.campaign_id == campaign_id)
        )
        assignments = list(assignments_result.scalars().all())

        groups_result = await self.db.execute(
            select(EngineerGroup).where(
                EngineerGroup.id.in_(group_ids),
                EngineerGroup.tenant_id == tenant_id,
            )
        )
        groups_by_id = {group.id: group for group in groups_result.scalars().all()}

        members_result = await self.db.execute(
            select(EngineerGroupMember.group_id, EngineerGroupMember.user_id).where(
                EngineerGroupMember.group_id.in_(group_ids)
            )
        )
        members_by_group: Dict[int, set[int]] = {gid: set() for gid in group_ids}
        for group_id, user_id in members_result.all():
            members_by_group.setdefault(group_id, set()).add(user_id)

        rows: List[Dict[str, Any]] = []
        grouped_user_ids: set[int] = set()
        for group_id in group_ids:
            user_ids = members_by_group.get(group_id, set())
            grouped_user_ids.update(user_ids)
            group = groups_by_id.get(group_id)
            group_assignments = [a for a in assignments if a.user_id in user_ids]
            rows.append(
                {
                    "group_id": group_id,
                    "group_name": group.name if group else f"Group {group_id}",
                    **self._assignment_stats(group_assignments),
                }
            )

        ungrouped_assignments = [a for a in assignments if a.user_id not in grouped_user_ids]
        if ungrouped_assignments:
            rows.append(
                {
                    "group_id": None,
                    "group_name": "Ungrouped",
                    **self._assignment_stats(ungrouped_assignments),
                }
            )

        return rows

    # ==================== Reminder defaults (SystemSetting) ====================

    async def get_reminder_defaults(self, *, tenant_id: int) -> List[int]:
        setting_key = _reminder_defaults_setting_key(tenant_id)
        result = await self.db.execute(
            select(SystemSetting).where(
                SystemSetting.tenant_id == tenant_id,
                SystemSetting.key == setting_key,
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
            logger.warning("Invalid %s setting for tenant %s", setting_key, tenant_id)
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
        setting_key = _reminder_defaults_setting_key(tenant_id)
        result = await self.db.execute(
            select(SystemSetting).where(
                SystemSetting.tenant_id == tenant_id,
                SystemSetting.key == setting_key,
            )
        )
        setting = result.scalar_one_or_none()
        if setting is None:
            setting = SystemSetting(
                tenant_id=tenant_id,
                key=setting_key,
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
                    "audience_group_ids": list(campaign.audience_group_ids or []),
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
                    "signature_disposition": assignment.signature_disposition,
                    "ip_address": assignment.ip_address,
                    "reminders_sent": assignment.reminders_sent,
                    "last_reminder_at": (
                        assignment.last_reminder_at.isoformat() if assignment.last_reminder_at else None
                    ),
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

    async def list_campaign_roster(
        self,
        *,
        tenant_id: int,
        campaign_id: int,
        status: Optional[str] = None,
        q: Optional[str] = None,
        opened: Optional[bool] = None,
        quiz_passed: Optional[bool] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Paginated assignee roster for HSEQ document results / central compliance."""
        campaign = await self.get_campaign(tenant_id=tenant_id, campaign_id=campaign_id)
        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        base_filters = [
            CampaignAssignment.campaign_id == campaign_id,
            CampaignAssignment.tenant_id == tenant_id,
        ]
        if status:
            try:
                status_enum = AssignmentStatus(status.lower())
            except ValueError as exc:
                raise BadRequestError(f"Invalid assignment status: {status}") from exc
            base_filters.append(CampaignAssignment.status == status_enum)
        if opened is True:
            base_filters.append(CampaignAssignment.first_opened_at.is_not(None))
        elif opened is False:
            base_filters.append(CampaignAssignment.first_opened_at.is_(None))
        if quiz_passed is True:
            base_filters.append(CampaignAssignment.quiz_passed.is_(True))
        elif quiz_passed is False:
            base_filters.append(CampaignAssignment.quiz_passed.is_(False))

        join_filters = list(base_filters)
        if q and q.strip():
            needle = f"%{q.strip().lower()}%"
            join_filters.append(
                or_(
                    func.lower(User.email).like(needle),
                    func.lower(User.first_name).like(needle),
                    func.lower(User.last_name).like(needle),
                )
            )

        count_result = await self.db.execute(
            select(func.count(CampaignAssignment.id))
            .select_from(CampaignAssignment)
            .join(User, User.id == CampaignAssignment.user_id)
            .where(and_(*join_filters))
        )
        total = int(count_result.scalar_one() or 0)

        rows_result = await self.db.execute(
            select(CampaignAssignment, User)
            .join(User, User.id == CampaignAssignment.user_id)
            .where(and_(*join_filters))
            .order_by(User.last_name, User.first_name)
            .offset(offset)
            .limit(limit)
        )

        items: List[Dict[str, Any]] = []
        for assignment, user in rows_result.all():
            status_value = assignment.status.value if hasattr(assignment.status, "value") else str(assignment.status)
            items.append(
                {
                    "assignment_id": assignment.id,
                    "user_id": user.id,
                    "user_email": user.email,
                    "user_name": user.full_name,
                    "status": status_value,
                    "assigned_at": assignment.assigned_at.isoformat() if assignment.assigned_at else None,
                    "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
                    "first_opened_at": (assignment.first_opened_at.isoformat() if assignment.first_opened_at else None),
                    "completed_at": assignment.completed_at.isoformat() if assignment.completed_at else None,
                    "quiz_score": assignment.quiz_score,
                    "quiz_passed": assignment.quiz_passed,
                    "quiz_attempts": assignment.quiz_attempts or 0,
                    "reminders_sent": assignment.reminders_sent or 0,
                    "last_reminder_at": (
                        assignment.last_reminder_at.isoformat() if assignment.last_reminder_at else None
                    ),
                }
            )

        summary_counts = await self._compliance_summary(campaign_id)
        opened_result = await self.db.execute(
            select(func.count(CampaignAssignment.id)).where(
                CampaignAssignment.campaign_id == campaign_id,
                CampaignAssignment.tenant_id == tenant_id,
                CampaignAssignment.first_opened_at.is_not(None),
            )
        )
        opened_count = int(opened_result.scalar_one() or 0)
        quiz_pass_result = await self.db.execute(
            select(func.count(CampaignAssignment.id)).where(
                CampaignAssignment.campaign_id == campaign_id,
                CampaignAssignment.tenant_id == tenant_id,
                CampaignAssignment.quiz_passed.is_(True),
            )
        )
        quiz_fail_result = await self.db.execute(
            select(func.count(CampaignAssignment.id)).where(
                CampaignAssignment.campaign_id == campaign_id,
                CampaignAssignment.tenant_id == tenant_id,
                CampaignAssignment.quiz_passed.is_(False),
            )
        )
        quiz_pass_count = int(quiz_pass_result.scalar_one() or 0)
        quiz_fail_count = int(quiz_fail_result.scalar_one() or 0)
        assigned = int(summary_counts["total_assigned"])
        open_rate = round((opened_count / assigned * 100), 1) if assigned > 0 else 0.0

        return {
            "campaign_id": campaign.id,
            "document_id": campaign.document_id,
            "require_quiz": bool(campaign.require_quiz),
            "items": items,
            "total": total,
            "limit": limit,
            "offset": offset,
            "summary": {
                "assigned": assigned,
                "completed": summary_counts["completed"],
                "pending": summary_counts["pending"],
                "overdue": summary_counts["overdue"],
                "expired": summary_counts["expired"],
                "opened": opened_count,
                "not_opened": max(assigned - opened_count, 0),
                "quiz_pass_count": quiz_pass_count,
                "quiz_fail_count": quiz_fail_count,
                "completion_rate": summary_counts["completion_rate"],
                "open_rate": open_rate,
            },
        }

    @staticmethod
    def _is_quiz_fail(*, require_quiz: bool, quiz_attempts: int, quiz_passed: Optional[bool]) -> bool:
        """True when quiz is required and the assignee failed or exhausted attempts."""
        if not require_quiz:
            return False
        attempts = quiz_attempts or 0
        if attempts >= MAX_QUIZ_ATTEMPTS and quiz_passed is not True:
            return True
        if attempts > 0 and quiz_passed is False:
            return True
        return False

    @staticmethod
    def _percentile(values: List[float], percentile: float) -> Optional[float]:
        if len(values) < 2:
            return None
        ordered = sorted(values)
        rank = (len(ordered) - 1) * (percentile / 100.0)
        lower = int(rank)
        upper = min(lower + 1, len(ordered) - 1)
        weight = rank - lower
        return round(ordered[lower] * (1 - weight) + ordered[upper] * weight, 2)

    @staticmethod
    def _iso_date(dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.date().isoformat()

    async def get_compliance_overview(self, *, tenant_id: int) -> Dict[str, Any]:
        """Tenant-wide HSEQ campaign effectiveness overview for the command centre."""
        active_result = await self.db.execute(
            select(func.count(DocumentCampaign.id)).where(
                DocumentCampaign.tenant_id == tenant_id,
                DocumentCampaign.status == CampaignStatus.ACTIVE,
            )
        )
        active_campaigns = int(active_result.scalar_one() or 0)

        rows_result = await self.db.execute(
            select(CampaignAssignment, DocumentCampaign)
            .join(DocumentCampaign, DocumentCampaign.id == CampaignAssignment.campaign_id)
            .where(CampaignAssignment.tenant_id == tenant_id)
        )
        rows = rows_result.all()

        total_assignments = len(rows)
        completed_assignments = 0
        overdue_count = 0
        quiz_fail_count = 0
        unanswered_hseq_count = 0
        opened_count = 0

        today = datetime.now(timezone.utc).date()
        series_dates = [(today - timedelta(days=offset)).isoformat() for offset in range(13, -1, -1)]
        series_buckets: Dict[str, Dict[str, int]] = {
            day: {"completed": 0, "opened": 0, "overdue": 0} for day in series_dates
        }

        for assignment, campaign in rows:
            if assignment.status == AssignmentStatus.COMPLETED:
                completed_assignments += 1
            if assignment.status == AssignmentStatus.OVERDUE:
                overdue_count += 1
            if assignment.first_opened_at is not None:
                opened_count += 1
            if self._is_quiz_fail(
                require_quiz=bool(campaign.require_quiz),
                quiz_attempts=assignment.quiz_attempts or 0,
                quiz_passed=assignment.quiz_passed,
            ):
                quiz_fail_count += 1
            disposition = assignment.signature_disposition or ""
            if disposition in (
                SIGNATURE_DISPOSITION_SIGNED_PENDING_HSEQ,
                SIGNATURE_DISPOSITION_DEFERRED,
            ):
                unanswered_hseq_count += 1

            completed_day = self._iso_date(assignment.completed_at)
            if completed_day in series_buckets:
                series_buckets[completed_day]["completed"] += 1

            opened_day = self._iso_date(assignment.first_opened_at)
            if opened_day in series_buckets:
                series_buckets[opened_day]["opened"] += 1

            due_day = self._iso_date(assignment.due_at)
            if due_day in series_buckets and assignment.status == AssignmentStatus.OVERDUE:
                series_buckets[due_day]["overdue"] += 1

        overall_completion_rate = (
            round((completed_assignments / total_assignments * 100), 1) if total_assignments > 0 else 0.0
        )
        open_rate = round((opened_count / total_assignments * 100), 1) if total_assignments > 0 else 0.0

        return {
            "active_campaigns": active_campaigns,
            "total_assignments": total_assignments,
            "completed_assignments": completed_assignments,
            "overall_completion_rate": overall_completion_rate,
            "overdue_count": overdue_count,
            "quiz_fail_count": quiz_fail_count,
            "unanswered_hseq_count": unanswered_hseq_count,
            "open_rate": open_rate,
            "series": [
                {
                    "date": day,
                    "completed": series_buckets[day]["completed"],
                    "opened": series_buckets[day]["opened"],
                    "overdue": series_buckets[day]["overdue"],
                }
                for day in series_dates
            ],
        }

    async def get_campaign_analytics(self, *, tenant_id: int, campaign_id: int) -> Dict[str, Any]:
        """Per-campaign funnel, score distribution, and completion timing."""
        campaign = await self.get_campaign(tenant_id=tenant_id, campaign_id=campaign_id)

        assignments_result = await self.db.execute(
            select(CampaignAssignment).where(
                CampaignAssignment.campaign_id == campaign_id,
                CampaignAssignment.tenant_id == tenant_id,
            )
        )
        assignments = list(assignments_result.scalars().all())

        assigned = len(assignments)
        opened = sum(1 for a in assignments if a.first_opened_at is not None)
        quiz_attempted = sum(1 for a in assignments if (a.quiz_attempts or 0) > 0 or a.quiz_passed is not None)
        quiz_passed = sum(1 for a in assignments if a.quiz_passed is True)
        completed = sum(1 for a in assignments if a.status == AssignmentStatus.COMPLETED)

        histogram_defs = [
            ("0-19", 0, 19),
            ("20-39", 20, 39),
            ("40-59", 40, 59),
            ("60-79", 60, 79),
            ("80-100", 80, 100),
        ]
        histogram_counts = {label: 0 for label, _, _ in histogram_defs}
        for assignment in assignments:
            if assignment.quiz_score is None:
                continue
            score = assignment.quiz_score
            for label, low, high in histogram_defs:
                if low <= score <= high:
                    histogram_counts[label] += 1
                    break

        attempts_counts: Dict[int, int] = {0: 0, 1: 0, 2: 0, 3: 0}
        for assignment in assignments:
            attempts = assignment.quiz_attempts or 0
            bucket = 3 if attempts >= 3 else attempts
            attempts_counts[bucket] = attempts_counts.get(bucket, 0) + 1

        completion_hours: List[float] = []
        for assignment in assignments:
            if assignment.completed_at is None:
                continue
            start = assignment.first_opened_at or assignment.assigned_at
            if start is None:
                continue
            start_dt = start if start.tzinfo else start.replace(tzinfo=timezone.utc)
            completed_dt = (
                assignment.completed_at
                if assignment.completed_at.tzinfo
                else assignment.completed_at.replace(tzinfo=timezone.utc)
            )
            completion_hours.append((completed_dt - start_dt).total_seconds() / 3600.0)

        reminder_sent_total = sum(a.reminders_sent or 0 for a in assignments)

        summary_counts = await self._compliance_summary(campaign_id)
        opened_result = await self.db.execute(
            select(func.count(CampaignAssignment.id)).where(
                CampaignAssignment.campaign_id == campaign_id,
                CampaignAssignment.tenant_id == tenant_id,
                CampaignAssignment.first_opened_at.is_not(None),
            )
        )
        opened_count = int(opened_result.scalar_one() or 0)
        quiz_pass_result = await self.db.execute(
            select(func.count(CampaignAssignment.id)).where(
                CampaignAssignment.campaign_id == campaign_id,
                CampaignAssignment.tenant_id == tenant_id,
                CampaignAssignment.quiz_passed.is_(True),
            )
        )
        quiz_fail_result = await self.db.execute(
            select(func.count(CampaignAssignment.id)).where(
                CampaignAssignment.campaign_id == campaign_id,
                CampaignAssignment.tenant_id == tenant_id,
                CampaignAssignment.quiz_passed.is_(False),
            )
        )
        quiz_pass_count = int(quiz_pass_result.scalar_one() or 0)
        quiz_fail_count = int(quiz_fail_result.scalar_one() or 0)
        assigned_total = int(summary_counts["total_assigned"])
        open_rate = round((opened_count / assigned_total * 100), 1) if assigned_total > 0 else 0.0

        return {
            "campaign_id": campaign.id,
            "document_id": campaign.document_id,
            "require_quiz": bool(campaign.require_quiz),
            "funnel": {
                "assigned": assigned,
                "opened": opened,
                "quiz_attempted": quiz_attempted,
                "quiz_passed": quiz_passed,
                "completed": completed,
            },
            "score_histogram": [{"bucket": label, "count": histogram_counts[label]} for label, _, _ in histogram_defs],
            "attempts_distribution": [{"attempts": k, "count": v} for k, v in sorted(attempts_counts.items())],
            "time_to_complete_hours": {
                "p50": self._percentile(completion_hours, 50),
                "p90": self._percentile(completion_hours, 90),
            },
            "reminder_sent_total": reminder_sent_total,
            "summary": {
                "assigned": assigned_total,
                "completed": summary_counts["completed"],
                "pending": summary_counts["pending"],
                "overdue": summary_counts["overdue"],
                "expired": summary_counts["expired"],
                "opened": opened_count,
                "not_opened": max(assigned_total - opened_count, 0),
                "quiz_pass_count": quiz_pass_count,
                "quiz_fail_count": quiz_fail_count,
                "completion_rate": summary_counts["completion_rate"],
                "open_rate": open_rate,
            },
        }

    async def list_compliance_people(
        self,
        *,
        tenant_id: int,
        status: str,
        q: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """Cross-campaign chase list for overdue assignees or quiz failures."""
        status_key = (status or "").strip().lower()
        if status_key not in ("overdue", "quiz_fail"):
            raise BadRequestError("status must be overdue or quiz_fail")

        limit = max(1, min(limit, 200))
        offset = max(0, offset)

        base_filters = [CampaignAssignment.tenant_id == tenant_id]
        if status_key == "overdue":
            base_filters.append(CampaignAssignment.status == AssignmentStatus.OVERDUE)
        else:
            base_filters.append(DocumentCampaign.require_quiz.is_(True))
            base_filters.append(
                or_(
                    and_(
                        CampaignAssignment.quiz_attempts > 0,
                        CampaignAssignment.quiz_passed.is_(False),
                    ),
                    and_(
                        CampaignAssignment.quiz_attempts >= MAX_QUIZ_ATTEMPTS,
                        CampaignAssignment.quiz_passed.is_not(True),
                    ),
                )
            )

        join_filters = list(base_filters)
        if q and q.strip():
            needle = f"%{q.strip().lower()}%"
            join_filters.append(
                or_(
                    func.lower(User.email).like(needle),
                    func.lower(User.first_name).like(needle),
                    func.lower(User.last_name).like(needle),
                )
            )

        count_result = await self.db.execute(
            select(func.count(CampaignAssignment.id))
            .select_from(CampaignAssignment)
            .join(DocumentCampaign, DocumentCampaign.id == CampaignAssignment.campaign_id)
            .join(User, User.id == CampaignAssignment.user_id)
            .join(Document, Document.id == DocumentCampaign.document_id)
            .where(and_(*join_filters))
        )
        total = int(count_result.scalar_one() or 0)

        rows_result = await self.db.execute(
            select(CampaignAssignment, DocumentCampaign, Document, User)
            .join(DocumentCampaign, DocumentCampaign.id == CampaignAssignment.campaign_id)
            .join(Document, Document.id == DocumentCampaign.document_id)
            .join(User, User.id == CampaignAssignment.user_id)
            .where(and_(*join_filters))
            .order_by(CampaignAssignment.due_at, User.last_name, User.first_name)
            .offset(offset)
            .limit(limit)
        )

        items: List[Dict[str, Any]] = []
        for assignment, _campaign, document, user in rows_result.all():
            status_value = assignment.status.value if hasattr(assignment.status, "value") else str(assignment.status)
            items.append(
                {
                    "assignment_id": assignment.id,
                    "campaign_id": assignment.campaign_id,
                    "document_id": document.id,
                    "document_title": document.title or f"Document #{document.id}",
                    "user_id": user.id,
                    "user_name": user.full_name,
                    "user_email": user.email,
                    "status": status_value,
                    "quiz_score": assignment.quiz_score,
                    "quiz_passed": assignment.quiz_passed,
                    "quiz_attempts": assignment.quiz_attempts or 0,
                    "first_opened_at": (
                        assignment.first_opened_at.isoformat() if assignment.first_opened_at else None
                    ),
                    "completed_at": assignment.completed_at.isoformat() if assignment.completed_at else None,
                    "due_at": assignment.due_at.isoformat() if assignment.due_at else None,
                    "reminders_sent": assignment.reminders_sent or 0,
                }
            )

        return {"items": items, "total": total, "limit": limit, "offset": offset}

    # ==================== Question inbox (HSEQ) ====================

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

    # ==================== Compliance Passport (O-07) ====================

    async def get_my_passport(self, *, tenant_id: int, user_id: int) -> Dict[str, Any]:
        """Aggregate the current user's campaign assignments into a compliance passport."""
        result = await self.db.execute(
            select(CampaignAssignment, DocumentCampaign, Document)
            .join(DocumentCampaign, DocumentCampaign.id == CampaignAssignment.campaign_id)
            .join(Document, Document.id == DocumentCampaign.document_id)
            .where(
                CampaignAssignment.user_id == user_id,
                CampaignAssignment.tenant_id == tenant_id,
            )
            .order_by(CampaignAssignment.due_at)
        )

        outstanding: List[Dict[str, Any]] = []
        completed: List[Dict[str, Any]] = []
        quiz_attempted = 0
        quiz_passed_count = 0

        for assignment, campaign, document in result.all():
            status_value = assignment.status.value if hasattr(assignment.status, "value") else str(assignment.status)
            item = {
                "id": assignment.id,
                "campaign_id": campaign.id,
                "document_id": document.id,
                "document_title": document.title or f"Document #{document.id}",
                "campaign_title": campaign.title,
                "status": status_value,
                "assigned_at": assignment.assigned_at,
                "due_at": assignment.due_at,
                "completed_at": assignment.completed_at,
                "quiz_score": assignment.quiz_score,
                "quiz_passed": assignment.quiz_passed,
            }
            if assignment.status == AssignmentStatus.COMPLETED:
                completed.append(item)
            else:
                outstanding.append(item)

            if assignment.quiz_passed is not None:
                quiz_attempted += 1
                if assignment.quiz_passed:
                    quiz_passed_count += 1

        total_assigned = len(outstanding) + len(completed)
        completion_rate = round((len(completed) / total_assigned * 100), 1) if total_assigned else 0.0
        quiz_pass_rate = round((quiz_passed_count / quiz_attempted * 100), 1) if quiz_attempted else 0.0

        return {
            "outstanding": outstanding,
            "completed": completed,
            "stats": {
                "completion_rate": completion_rate,
                "quiz_pass_rate": quiz_pass_rate,
                "total_assigned": total_assigned,
            },
        }

    # ==================== Evidence CSV export (O-09) ====================

    async def build_evidence_pack_csv(self, *, tenant_id: int, campaign_id: int) -> Tuple[str, str]:
        """Build CSV evidence pack for a campaign (assignments + quiz/sign-off metadata)."""
        campaign = await self.get_campaign(tenant_id=tenant_id, campaign_id=campaign_id)

        result = await self.db.execute(
            select(CampaignAssignment, User.email)
            .join(User, User.id == CampaignAssignment.user_id)
            .where(
                CampaignAssignment.campaign_id == campaign_id,
                CampaignAssignment.tenant_id == tenant_id,
            )
            .order_by(User.email)
        )

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(
            [
                "user_email",
                "status",
                "assigned_at",
                "due_at",
                "first_opened_at",
                "completed_at",
                "quiz_score",
                "quiz_passed",
                "signature_present",
                "signature_disposition",
                "ip_address",
            ]
        )

        for assignment, email in result.all():
            status_value = assignment.status.value if hasattr(assignment.status, "value") else str(assignment.status)
            writer.writerow(
                [
                    email or "",
                    status_value,
                    assignment.assigned_at.isoformat() if assignment.assigned_at else "",
                    assignment.due_at.isoformat() if assignment.due_at else "",
                    assignment.first_opened_at.isoformat() if assignment.first_opened_at else "",
                    assignment.completed_at.isoformat() if assignment.completed_at else "",
                    assignment.quiz_score if assignment.quiz_score is not None else "",
                    assignment.quiz_passed if assignment.quiz_passed is not None else "",
                    bool(assignment.signature_data),
                    assignment.signature_disposition or "",
                    assignment.ip_address or "",
                ]
            )

        filename = f"campaign-{campaign.id}-evidence-pack.csv"
        return output.getvalue(), filename

    # ==================== Re-ack on new version (O-10) ====================

    async def spawn_reack_campaign(
        self,
        *,
        document_id: int,
        tenant_id: int,
        actor_id: int,
    ) -> Dict[str, Any]:
        """Create a draft re-acknowledgment campaign when active campaigns exist on a document."""
        result = await self.db.execute(
            select(DocumentCampaign)
            .where(
                DocumentCampaign.document_id == document_id,
                DocumentCampaign.tenant_id == tenant_id,
                DocumentCampaign.status == CampaignStatus.ACTIVE,
            )
            .order_by(DocumentCampaign.launched_at.desc().nullslast(), DocumentCampaign.id.desc())
        )
        source = result.scalars().first()
        if source is None:
            return {"spawned": False, "reason": "no_active_campaigns"}

        doc_title = await self._document_title(tenant_id=tenant_id, document_id=document_id)
        base_title = source.title or doc_title
        reack_title = f"Re-acknowledgment: {base_title}"

        existing_draft = await self.db.execute(
            select(DocumentCampaign).where(
                DocumentCampaign.document_id == document_id,
                DocumentCampaign.tenant_id == tenant_id,
                DocumentCampaign.status == CampaignStatus.DRAFT,
                DocumentCampaign.title == reack_title,
            )
        )
        if existing_draft.scalar_one_or_none() is not None:
            return {"spawned": False, "reason": "draft_reack_already_exists", "source_campaign_id": source.id}

        campaign = DocumentCampaign(
            tenant_id=tenant_id,
            document_id=document_id,
            quiz_draft_id=source.quiz_draft_id,
            title=reack_title,
            status=CampaignStatus.DRAFT,
            due_within_days=source.due_within_days,
            require_quiz=source.require_quiz,
            require_sign=source.require_sign,
            reminder_offsets_hours=list(source.reminder_offsets_hours or DEFAULT_REMINDER_OFFSETS_HOURS),
            audience_all_users=source.audience_all_users,
            audience_department=source.audience_department,
            audience_role=source.audience_role,
            audience_group_ids=list(source.audience_group_ids) if source.audience_group_ids else None,
            audience_user_ids=list(source.audience_user_ids) if source.audience_user_ids else None,
            quiz_questions=source.quiz_questions,
            quiz_pass_mark=source.quiz_pass_mark,
            created_by_id=actor_id,
        )
        self.db.add(campaign)
        await self.db.commit()
        await self.db.refresh(campaign)

        return {
            "spawned": True,
            "campaign_id": campaign.id,
            "source_campaign_id": source.id,
        }
