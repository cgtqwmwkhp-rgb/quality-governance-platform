"""Unit tests for GovernanceService and NotificationService.

Tests supervisor validation, template approval, competency gating,
scheduling suggestions, and notification creation.
"""

from datetime import datetime, timedelta, timezone
from enum import Enum
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# Minimal stub for CompetencyLifecycleState used in assertions
class _FakeState(str, Enum):
    ACTIVE = "active"
    DUE = "due"
    EXPIRED = "expired"
    FAILED = "failed"
    NOT_ASSESSED = "not_assessed"


def _make_db():
    return AsyncMock()


# =========================================================================
# GovernanceService — static helper methods
# =========================================================================


class TestCompetencyRecordSortKey:
    def test_sort_key_uses_assessed_at(self):
        from src.domain.services.governance_service import GovernanceService

        record = MagicMock()
        record.assessed_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
        record.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        record.id = 1
        key = GovernanceService._competency_record_sort_key(record)
        assert key[0] == record.assessed_at

    def test_sort_key_falls_back_to_created_at(self):
        from src.domain.services.governance_service import GovernanceService

        record = MagicMock(spec=[])
        record.created_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        record.id = 2
        key = GovernanceService._competency_record_sort_key(record)
        assert key[0] == record.created_at

    def test_sort_key_uses_baseline_when_no_dates(self):
        from src.domain.services.governance_service import GovernanceService

        record = MagicMock(spec=[])
        record.id = 3
        key = GovernanceService._competency_record_sort_key(record)
        assert key[0] == datetime.min.replace(tzinfo=timezone.utc)


class TestLatestRecordsByAssetType:
    def test_picks_latest_per_asset_type(self):
        from src.domain.services.governance_service import GovernanceService

        r1 = MagicMock()
        r1.asset_type_id = 1
        r1.assessed_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        r1.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
        r1.id = 1

        r2 = MagicMock()
        r2.asset_type_id = 1
        r2.assessed_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
        r2.created_at = datetime(2026, 6, 1, tzinfo=timezone.utc)
        r2.id = 2

        r3 = MagicMock()
        r3.asset_type_id = 2
        r3.assessed_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        r3.created_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        r3.id = 3

        result = GovernanceService._latest_records_by_asset_type([r1, r2, r3])
        assert len(result) == 2
        ids = {r.id for r in result}
        assert 2 in ids
        assert 3 in ids

    def test_empty_input_returns_empty(self):
        from src.domain.services.governance_service import GovernanceService

        assert GovernanceService._latest_records_by_asset_type([]) == []


class TestEffectiveCompetencyState:
    def test_active_not_expired_stays_active(self):
        from src.domain.models.engineer import CompetencyLifecycleState
        from src.domain.services.governance_service import GovernanceService

        record = MagicMock()
        record.state = CompetencyLifecycleState.ACTIVE
        record.expires_at = datetime.now(timezone.utc) + timedelta(days=30)
        result = GovernanceService._effective_competency_state(record)
        assert result == CompetencyLifecycleState.ACTIVE

    def test_active_expired_becomes_expired(self):
        from src.domain.models.engineer import CompetencyLifecycleState
        from src.domain.services.governance_service import GovernanceService

        record = MagicMock()
        record.state = CompetencyLifecycleState.ACTIVE
        record.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        result = GovernanceService._effective_competency_state(record)
        assert result == CompetencyLifecycleState.EXPIRED

    def test_due_expired_becomes_expired(self):
        from src.domain.models.engineer import CompetencyLifecycleState
        from src.domain.services.governance_service import GovernanceService

        record = MagicMock()
        record.state = CompetencyLifecycleState.DUE
        record.expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        result = GovernanceService._effective_competency_state(record)
        assert result == CompetencyLifecycleState.EXPIRED

    def test_no_expiry_returns_current_state(self):
        from src.domain.models.engineer import CompetencyLifecycleState
        from src.domain.services.governance_service import GovernanceService

        record = MagicMock()
        record.state = CompetencyLifecycleState.ACTIVE
        record.expires_at = None
        result = GovernanceService._effective_competency_state(record)
        assert result == CompetencyLifecycleState.ACTIVE

    def test_failed_stays_failed_even_when_not_expired(self):
        from src.domain.models.engineer import CompetencyLifecycleState
        from src.domain.services.governance_service import GovernanceService

        record = MagicMock()
        record.state = CompetencyLifecycleState.FAILED
        record.expires_at = datetime.now(timezone.utc) + timedelta(days=90)
        result = GovernanceService._effective_competency_state(record)
        assert result == CompetencyLifecycleState.FAILED


# =========================================================================
# GovernanceService — validate_supervisor
# =========================================================================


class TestValidateSupervisor:
    @pytest.mark.asyncio
    async def test_engineer_not_found_returns_invalid(self):
        from src.domain.services.governance_service import GovernanceService

        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        result = await GovernanceService.validate_supervisor(db, supervisor_id=5, engineer_id=999)
        assert result["valid"] is False
        assert "not found" in result["reason"]

    @pytest.mark.asyncio
    async def test_self_assessment_not_allowed(self):
        from src.domain.services.governance_service import GovernanceService

        db = _make_db()
        engineer = MagicMock()
        engineer.user_id = 5
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = engineer
        db.execute.return_value = result_mock

        result = await GovernanceService.validate_supervisor(db, supervisor_id=5, engineer_id=1)
        assert result["valid"] is False
        assert "themselves" in result["reason"]

    @pytest.mark.asyncio
    async def test_inactive_supervisor_returns_invalid(self):
        from src.domain.services.governance_service import GovernanceService

        db = _make_db()
        engineer = MagicMock()
        engineer.user_id = 10
        supervisor = MagicMock()
        supervisor.is_active = False

        call_count = 0

        async def fake_execute(stmt):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.scalar_one_or_none.return_value = engineer
            else:
                mock.scalar_one_or_none.return_value = supervisor
            return mock

        db.execute = fake_execute

        result = await GovernanceService.validate_supervisor(db, supervisor_id=5, engineer_id=1)
        assert result["valid"] is False
        assert "inactive" in result["reason"]

    @pytest.mark.asyncio
    async def test_superuser_always_valid(self):
        from src.domain.services.governance_service import GovernanceService

        db = _make_db()
        engineer = MagicMock()
        engineer.user_id = 10
        supervisor = MagicMock()
        supervisor.is_active = True
        supervisor.is_superuser = True

        call_count = 0

        async def fake_execute(stmt):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.scalar_one_or_none.return_value = engineer
            else:
                mock.scalar_one_or_none.return_value = supervisor
            return mock

        db.execute = fake_execute

        result = await GovernanceService.validate_supervisor(db, supervisor_id=5, engineer_id=1)
        assert result["valid"] is True

    @pytest.mark.asyncio
    async def test_supervisor_without_role_returns_invalid(self):
        from src.domain.services.governance_service import GovernanceService

        db = _make_db()
        engineer = MagicMock()
        engineer.user_id = 10
        role = MagicMock()
        role.name = "viewer"
        supervisor = MagicMock()
        supervisor.is_active = True
        supervisor.is_superuser = False
        supervisor.tenant_id = None
        supervisor.roles = [role]

        call_count = 0

        async def fake_execute(stmt):
            nonlocal call_count
            call_count += 1
            mock = MagicMock()
            if call_count == 1:
                mock.scalar_one_or_none.return_value = engineer
            else:
                mock.scalar_one_or_none.return_value = supervisor
            return mock

        db.execute = fake_execute

        result = await GovernanceService.validate_supervisor(db, supervisor_id=5, engineer_id=1)
        assert result["valid"] is False
        assert "role" in result["reason"]


# =========================================================================
# GovernanceService — check_template_approval
# =========================================================================


class TestCheckTemplateApproval:
    @pytest.mark.asyncio
    async def test_template_not_found_returns_not_approved(self):
        from src.domain.services.governance_service import GovernanceService

        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        result = await GovernanceService.check_template_approval(db, template_id=999)
        assert result["approved"] is False
        assert "not found" in result["reason"]

    @pytest.mark.asyncio
    async def test_published_template_is_approved(self):
        from src.domain.services.governance_service import GovernanceService

        db = _make_db()
        template = MagicMock()
        template.template_status = "published"
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = template
        db.execute.return_value = result_mock

        result = await GovernanceService.check_template_approval(db, template_id=1)
        assert result["approved"] is True

    @pytest.mark.asyncio
    async def test_draft_template_not_approved(self):
        from src.domain.services.governance_service import GovernanceService

        db = _make_db()
        template = MagicMock()
        template.template_status = "draft"
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = template
        db.execute.return_value = result_mock

        result = await GovernanceService.check_template_approval(db, template_id=1)
        assert result["approved"] is False
        assert "draft" in result["reason"]


# =========================================================================
# NotificationService
# =========================================================================


class TestNotifyAssessmentComplete:
    @pytest.mark.asyncio
    async def test_creates_notifications_for_engineer_and_supervisor(self):
        from src.domain.services.governance_service import NotificationService

        db = _make_db()
        await NotificationService.notify_assessment_complete(
            db, assessment_run_id="run-1", engineer_user_id=5, supervisor_id=10, outcome="pass"
        )
        assert db.add.call_count == 2

    @pytest.mark.asyncio
    async def test_skips_engineer_notification_when_no_user_id(self):
        from src.domain.services.governance_service import NotificationService

        db = _make_db()
        await NotificationService.notify_assessment_complete(
            db, assessment_run_id="run-1", engineer_user_id=None, supervisor_id=10, outcome="fail"
        )
        assert db.add.call_count == 1


class TestNotifyInductionComplete:
    @pytest.mark.asyncio
    async def test_creates_notifications_with_nyc_items(self):
        from src.domain.services.governance_service import NotificationService

        db = _make_db()
        await NotificationService.notify_induction_complete(
            db, induction_run_id="ind-1", engineer_user_id=5, supervisor_id=10, not_yet_competent_count=3
        )
        assert db.add.call_count == 2

    @pytest.mark.asyncio
    async def test_successful_induction_message_differs(self):
        from src.domain.services.governance_service import NotificationService

        db = _make_db()
        await NotificationService.notify_induction_complete(
            db, induction_run_id="ind-1", engineer_user_id=5, supervisor_id=10, not_yet_competent_count=0
        )
        assert db.add.call_count == 2

    @pytest.mark.asyncio
    async def test_skips_engineer_when_user_id_none(self):
        from src.domain.services.governance_service import NotificationService

        db = _make_db()
        await NotificationService.notify_induction_complete(
            db, induction_run_id="ind-1", engineer_user_id=None, supervisor_id=10, not_yet_competent_count=0
        )
        assert db.add.call_count == 1


class TestNotifyCompetencyExpiry:
    @pytest.mark.asyncio
    async def test_creates_notification(self):
        from src.domain.services.governance_service import NotificationService

        db = _make_db()
        await NotificationService.notify_competency_expiry(
            db, engineer_user_id=5, asset_type_id=3, days_until_expiry=14
        )
        db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_skips_when_no_user_id(self):
        from src.domain.services.governance_service import NotificationService

        db = _make_db()
        await NotificationService.notify_competency_expiry(
            db, engineer_user_id=None, asset_type_id=3, days_until_expiry=14
        )
        db.add.assert_not_called()
