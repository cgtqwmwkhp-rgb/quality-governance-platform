"""Unit tests for campaign CUJ Wave 2 hardening."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.document_campaign import AssignmentStatus, CampaignStatus
from src.domain.services.document_campaign_notifications import portal_assignment_action_url
from src.domain.services.document_campaign_service import DocumentCampaignService

NOW = datetime(2026, 7, 18, 12, 0, tzinfo=timezone.utc)


class TestPortalReminderEmailHtml:
    def test_reminder_email_includes_portal_assignment_cta(self):
        html = DocumentCampaignService._build_reminder_email_html(
            doc_title="Fire Safety Policy",
            due_at=NOW,
            assignment_id=55,
            frontend_base="https://app.example.com",
        )
        assert portal_assignment_action_url(55) in html
        assert "https://app.example.com/portal/reading?assignment=55" in html

    def test_overdue_email_includes_portal_assignment_cta(self):
        html = DocumentCampaignService._build_overdue_email_html(
            doc_title="Fire Safety Policy",
            assignment_id=55,
            frontend_base="https://app.example.com",
        )
        assert "https://app.example.com/portal/reading?assignment=55" in html


class TestGetAssignmentDocumentUrl:
    @pytest.mark.asyncio
    async def test_returns_signed_url_for_own_active_assignment(self):
        assignment = SimpleNamespace(
            id=7,
            user_id=10,
            tenant_id=1,
            campaign_id=99,
            status=AssignmentStatus.PENDING,
        )
        campaign = SimpleNamespace(id=99, document_id=42)
        document = SimpleNamespace(
            id=42,
            file_name="policy.pdf",
            file_path="tenant/42/policy.pdf",
            mime_type="application/pdf",
            download_count=0,
            last_accessed_at=None,
        )

        db = SimpleNamespace(
            execute=AsyncMock(
                side_effect=[
                    MagicMock(scalar_one_or_none=lambda: assignment),
                    MagicMock(scalar_one_or_none=lambda: document),
                ]
            ),
            commit=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)

        with patch(
            "src.infrastructure.storage.storage_service",
        ) as storage_mock:
            storage_mock.return_value.get_signed_url.return_value = "https://storage.example/policy.pdf?sig=abc"
            result = await service.get_assignment_document_url(user_id=10, assignment_id=7)

        assert result["assignment_id"] == 7
        assert result["document_id"] == 42
        assert result["signed_url"].endswith("sig=abc")
        assert result["filename"] == "policy.pdf"
        storage_mock.return_value.get_signed_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_signed_url_for_completed_assignment(self):
        assignment = SimpleNamespace(
            id=7,
            user_id=10,
            tenant_id=1,
            campaign_id=99,
            status=AssignmentStatus.COMPLETED,
        )
        campaign = SimpleNamespace(id=99, document_id=42)
        document = SimpleNamespace(
            id=42,
            file_name="policy.pdf",
            file_path="tenant/42/policy.pdf",
            mime_type="application/pdf",
            download_count=0,
            last_accessed_at=None,
        )
        db = SimpleNamespace(
            execute=AsyncMock(
                side_effect=[
                    MagicMock(scalar_one_or_none=lambda: assignment),
                    MagicMock(scalar_one_or_none=lambda: document),
                ]
            ),
            commit=AsyncMock(),
        )
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)

        with patch("src.infrastructure.storage.storage_service") as storage_mock:
            storage_mock.return_value.get_signed_url.return_value = "https://storage.example/policy.pdf?sig=done"
            result = await service.get_assignment_document_url(user_id=10, assignment_id=7)

        assert result["signed_url"].endswith("sig=done")

    @pytest.mark.asyncio
    async def test_rejects_expired_assignment(self):
        assignment = SimpleNamespace(
            id=7,
            user_id=10,
            tenant_id=1,
            campaign_id=99,
            status=AssignmentStatus.EXPIRED,
        )
        db = SimpleNamespace(
            execute=AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: assignment)),
        )
        service = DocumentCampaignService(db)

        with pytest.raises(BadRequestError, match="owned campaign assignments"):
            await service.get_assignment_document_url(user_id=10, assignment_id=7)

    @pytest.mark.asyncio
    async def test_rejects_other_users_assignment(self):
        db = SimpleNamespace(
            execute=AsyncMock(return_value=MagicMock(scalar_one_or_none=lambda: None)),
        )
        service = DocumentCampaignService(db)

        with pytest.raises(NotFoundError):
            await service.get_assignment_document_url(user_id=10, assignment_id=7)


class TestReminderEmailAfterCommit:
    @pytest.mark.asyncio
    async def test_sends_reminder_email_only_after_db_commit(self):
        due_at = NOW + timedelta(hours=24)
        assignment = SimpleNamespace(
            id=7,
            user_id=10,
            tenant_id=1,
            campaign_id=99,
            status=AssignmentStatus.PENDING,
            due_at=due_at,
            reminders_sent=0,
            last_reminder_at=None,
            snooze_until=None,
        )
        campaign = SimpleNamespace(
            id=99,
            tenant_id=1,
            document_id=42,
            status=CampaignStatus.ACTIVE,
            reminder_offsets_hours=[24],
            created_by_id=5,
            launched_by_id=6,
        )
        pending_result = MagicMock()
        pending_result.all.return_value = [(assignment, campaign)]
        users_result = MagicMock()
        users_result.scalars.return_value.all.return_value = []

        call_order: list[str] = []
        commit = AsyncMock(side_effect=lambda: call_order.append("commit"))
        send_email = AsyncMock(side_effect=lambda **_kwargs: call_order.append("email"))

        db = SimpleNamespace(
            execute=AsyncMock(side_effect=[pending_result, users_result]),
            add=MagicMock(),
            commit=commit,
        )
        service = DocumentCampaignService(db)
        service._document_title = AsyncMock(return_value="Fire Safety Policy")
        service._send_assignee_campaign_email = send_email

        await service.process_due_reminders(now=NOW)

        assert call_order == ["commit", "email"]
        send_email.assert_awaited_once()
        assert send_email.await_args.kwargs["user_id"] == 10
        assert send_email.await_args.kwargs["subject"] == "Document campaign reminder"


class TestBuildEvidencePackDisposition:
    @pytest.mark.asyncio
    async def test_json_evidence_includes_signature_disposition(self):
        assignment = SimpleNamespace(
            id=1,
            status=AssignmentStatus.COMPLETED,
            assigned_at=NOW,
            due_at=NOW,
            first_opened_at=NOW,
            completed_at=NOW,
            quiz_score=100,
            quiz_passed=True,
            quiz_attempts=1,
            acceptance_statement="I agree",
            signature_data="Alex",
            signature_disposition="signed_pending_hseq_answer",
            ip_address="10.0.0.1",
            reminders_sent=0,
            last_reminder_at=None,
        )
        user = SimpleNamespace(id=5, email="engineer@example.com", full_name="Alex Engineer")
        campaign = SimpleNamespace(
            id=9,
            tenant_id=1,
            document_id=3,
            title="Q3 read",
            status=SimpleNamespace(value="active"),
            due_within_days=14,
            require_quiz=True,
            require_sign=True,
            reminder_offsets_hours=[24],
            launched_at=NOW,
            closed_at=None,
        )
        document = SimpleNamespace(id=3, title="Policy", version="2.0")

        assignments_result = MagicMock()
        assignments_result.all.return_value = [(assignment, user)]

        db = SimpleNamespace(
            execute=AsyncMock(
                side_effect=[
                    MagicMock(scalar_one_or_none=lambda: document),
                    assignments_result,
                ]
            ),
        )
        service = DocumentCampaignService(db)
        service.get_campaign = AsyncMock(return_value=campaign)

        pack = await service.build_evidence_pack(tenant_id=1, campaign_id=9)

        assert pack["assignments"][0]["signature_disposition"] == "signed_pending_hseq_answer"
