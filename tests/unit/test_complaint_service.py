"""Unit tests for ComplaintService and complaint transition logic.

Tests CRUD, status transition validation, and email access checks
using mocked AsyncSession (no real database).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import StateTransitionError, ValidationError
from src.domain.models.complaint import ComplaintStatus
from src.domain.services.complaint_service import (
    COMPLAINT_TRANSITIONS,
    ComplaintService,
    resolve_response_due_at,
    validate_complaint_transition,
)

# ---------------------------------------------------------------------------
# Transition validation (pure function, no DB needed)
# ---------------------------------------------------------------------------


class TestComplaintTransitionMap:
    """Validate the transition map constants."""

    def test_received_can_move_to_acknowledged(self):
        assert ComplaintStatus.ACKNOWLEDGED in COMPLAINT_TRANSITIONS[ComplaintStatus.RECEIVED]

    def test_received_can_escalate(self):
        assert ComplaintStatus.ESCALATED in COMPLAINT_TRANSITIONS[ComplaintStatus.RECEIVED]

    def test_closed_only_allows_the_reopen_edge(self):
        """Closed is no longer terminal: reopen goes to under_investigation and nowhere else."""
        assert COMPLAINT_TRANSITIONS[ComplaintStatus.CLOSED] == {ComplaintStatus.UNDER_INVESTIGATION}

    def test_resolved_can_reopen_or_close(self):
        allowed = COMPLAINT_TRANSITIONS[ComplaintStatus.RESOLVED]
        assert ComplaintStatus.CLOSED in allowed
        assert ComplaintStatus.UNDER_INVESTIGATION in allowed

    def test_escalated_can_investigate_or_close(self):
        allowed = COMPLAINT_TRANSITIONS[ComplaintStatus.ESCALATED]
        assert ComplaintStatus.UNDER_INVESTIGATION in allowed
        assert ComplaintStatus.CLOSED in allowed

    def test_all_statuses_have_transition_entries(self):
        for status in ComplaintStatus:
            assert status in COMPLAINT_TRANSITIONS


class TestValidateComplaintTransition:
    def test_valid_transition_passes(self):
        validate_complaint_transition("received", "acknowledged")

    def test_invalid_transition_raises(self):
        with pytest.raises(StateTransitionError, match="Cannot transition"):
            validate_complaint_transition("received", "closed")

    def test_closed_to_anything_but_reopen_raises(self):
        with pytest.raises(StateTransitionError):
            validate_complaint_transition("closed", "received")

    def test_closed_to_under_investigation_passes(self):
        validate_complaint_transition("closed", "under_investigation")

    def test_unknown_status_values_silently_pass(self):
        validate_complaint_transition("nonexistent", "anything")

    def test_error_includes_allowed_details(self):
        with pytest.raises(StateTransitionError) as exc_info:
            validate_complaint_transition("received", "closed")
        assert "allowed" in exc_info.value.details

    def test_received_to_under_investigation_raises(self):
        with pytest.raises(StateTransitionError):
            validate_complaint_transition("received", "under_investigation")

    def test_awaiting_customer_to_resolved_passes(self):
        validate_complaint_transition("awaiting_customer", "resolved")

    def test_under_investigation_to_pending_response_passes(self):
        validate_complaint_transition("under_investigation", "pending_response")

    def test_enum_members_are_accepted(self):
        validate_complaint_transition(ComplaintStatus.RECEIVED, ComplaintStatus.ACKNOWLEDGED)

    def test_message_carries_values_not_enum_reprs(self):
        # complaint.status is loaded as a ComplaintStatus member, so the message is built
        # from enum members in production; f-strings on a str-mixin enum render the repr.
        with pytest.raises(StateTransitionError) as exc_info:
            validate_complaint_transition(ComplaintStatus.ACKNOWLEDGED, ComplaintStatus.RESOLVED)
        message = str(exc_info.value)
        assert "ComplaintStatus." not in message
        assert "'acknowledged'" in message
        assert "'resolved'" in message


# ---------------------------------------------------------------------------
# ComplaintService
# ---------------------------------------------------------------------------


def _make_service(db=None):
    if db is None:
        db = AsyncMock()
    return ComplaintService(db)


def _fake_complaint(**overrides):
    defaults = {
        "id": 1,
        "reference_number": "CMP-2026-0001",
        "title": "Broken widget",
        "status": "received",
        "tenant_id": 10,
        "external_ref": None,
        "complainant_email": "user@example.com",
    }
    defaults.update(overrides)
    obj = MagicMock(**defaults)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


class TestGetComplaint:
    @pytest.mark.asyncio
    async def test_returns_complaint_when_found(self):
        complaint = _fake_complaint()
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = complaint
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.get_complaint(1, tenant_id=10)
        assert result.id == 1

    @pytest.mark.asyncio
    async def test_raises_lookup_error_when_not_found(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = _make_service(db)
        with pytest.raises(LookupError, match="Complaint with ID 99 not found"):
            await svc.get_complaint(99, tenant_id=10)

    @pytest.mark.asyncio
    async def test_skip_tenant_check_omits_tenant_filter(self):
        complaint = _fake_complaint()
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = complaint
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.get_complaint(1, tenant_id=None, skip_tenant_check=True)
        assert result.id == 1


class TestCreateComplaint:
    @pytest.mark.asyncio
    @patch("src.domain.services.complaint_service.track_metric")
    @patch("src.domain.services.complaint_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.complaint_service.record_audit_event", new_callable=AsyncMock)
    @patch("src.domain.services.complaint_service.ReferenceNumberService")
    async def test_create_complaint_success(self, mock_ref, mock_audit, mock_cache, mock_metric):
        mock_ref.generate = AsyncMock(return_value="CMP-2026-0042")
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        data = MagicMock()
        data.model_dump.return_value = {"title": "Issue", "external_ref": None}

        svc = _make_service(db)
        await svc.create_complaint(complaint_data=data, user_id=5, tenant_id=10)

        db.add.assert_called_once()
        db.flush.assert_awaited()
        mock_cache.assert_awaited_once_with(10, "complaints")
        mock_metric.assert_called_once_with("complaints.created")

    @pytest.mark.asyncio
    async def test_create_complaint_duplicate_external_ref_raises(self):
        existing = _fake_complaint(external_ref="EXT-001")
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = existing
        db.execute.return_value = result_mock

        data = MagicMock()
        data.model_dump.return_value = {"title": "Issue", "external_ref": "EXT-001"}

        svc = _make_service(db)
        with pytest.raises(ValueError, match="DUPLICATE_EXTERNAL_REF"):
            await svc.create_complaint(complaint_data=data, user_id=5, tenant_id=10)

    @pytest.mark.asyncio
    async def test_create_complaint_rejects_cross_tenant_contract_id(self):
        db = AsyncMock()
        missing = MagicMock()
        missing.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=missing)

        data = MagicMock()
        data.model_dump.return_value = {"title": "Issue", "external_ref": None, "contract_id": 99}

        svc = _make_service(db)
        with pytest.raises(ValueError, match="Contract with ID 99 not found"):
            await svc.create_complaint(complaint_data=data, user_id=5, tenant_id=10)

        db.flush.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_create_complaint_rejects_cross_tenant_subject_user_id(self):
        db = AsyncMock()
        wrong_tenant_user = MagicMock(is_active=True, tenant_id=99)

        async def execute_side_effect(stmt):
            result = MagicMock()
            sql = str(stmt)
            if "users" in sql.lower():
                result.scalar_one_or_none.return_value = wrong_tenant_user
            else:
                result.scalar_one_or_none.return_value = None
            return result

        db.execute = AsyncMock(side_effect=execute_side_effect)

        data = MagicMock()
        data.model_dump.return_value = {"title": "Issue", "external_ref": None, "subject_user_id": 7}

        svc = _make_service(db)
        with pytest.raises(ValueError, match="User with ID 7 not found"):
            await svc.create_complaint(complaint_data=data, user_id=5, tenant_id=10)

        db.flush.assert_not_awaited()


class TestUpdateComplaint:
    @pytest.mark.asyncio
    @patch("src.domain.services.complaint_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.complaint_service.record_audit_event", new_callable=AsyncMock)
    @patch("src.domain.services.complaint_service.apply_updates", return_value={"title": "Updated"})
    async def test_update_without_status_change(self, mock_apply, mock_audit, mock_cache):
        complaint = _fake_complaint()
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = complaint
        db.execute.return_value = result_mock

        data = MagicMock()
        data.model_dump.return_value = {"title": "Updated"}

        svc = _make_service(db)
        result = await svc.update_complaint(1, data, user_id=5, tenant_id=10)

        mock_apply.assert_called_once()
        db.flush.assert_awaited()
        mock_audit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_with_invalid_status_transition_raises(self):
        complaint = _fake_complaint(status="received")
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = complaint
        db.execute.return_value = result_mock

        data = MagicMock()
        data.model_dump.return_value = {"status": "closed"}

        svc = _make_service(db)
        with pytest.raises(StateTransitionError):
            await svc.update_complaint(1, data, user_id=5, tenant_id=10)


class TestResponseSla:
    """PX-210 — a complaint keeps a real response deadline, or honestly none."""

    RECEIVED = datetime(2026, 3, 2, 9, 0, tzinfo=timezone.utc)

    def test_no_sla_and_no_explicit_date_means_no_deadline(self):
        assert resolve_response_due_at(self.RECEIVED, None, None) is None

    def test_deadline_derives_from_received_date_plus_sla(self):
        assert resolve_response_due_at(self.RECEIVED, 48, None) == datetime(2026, 3, 4, 9, 0, tzinfo=timezone.utc)

    def test_explicit_date_wins_over_the_sla(self):
        explicit = datetime(2026, 3, 3, 17, 0, tzinfo=timezone.utc)
        assert resolve_response_due_at(self.RECEIVED, 48, explicit) == explicit

    def test_non_positive_sla_is_not_a_deadline(self):
        assert resolve_response_due_at(self.RECEIVED, 0, None) is None

    def test_changing_the_sla_rederives_the_deadline(self):
        complaint = _fake_complaint(
            received_date=self.RECEIVED,
            response_sla_hours=24,
            response_due_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
            first_response_at=None,
        )

        ComplaintService._apply_response_sla(
            complaint,
            old_status=ComplaintStatus.RECEIVED,
            raw_update={"response_sla_hours": 24},
        )

        assert complaint.response_due_at == datetime(2026, 3, 3, 9, 0, tzinfo=timezone.utc)

    def test_clearing_the_sla_clears_the_derived_deadline(self):
        complaint = _fake_complaint(
            received_date=self.RECEIVED,
            response_sla_hours=None,
            response_due_at=datetime(2026, 3, 4, 9, 0, tzinfo=timezone.utc),
            first_response_at=None,
        )

        ComplaintService._apply_response_sla(
            complaint,
            old_status=ComplaintStatus.RECEIVED,
            raw_update={"response_sla_hours": None},
        )

        assert complaint.response_due_at is None

    def test_a_deadline_sent_in_the_same_request_is_not_overwritten(self):
        explicit = datetime(2026, 3, 3, 17, 0, tzinfo=timezone.utc)
        complaint = _fake_complaint(
            received_date=self.RECEIVED,
            response_sla_hours=48,
            response_due_at=explicit,
            first_response_at=None,
        )

        ComplaintService._apply_response_sla(
            complaint,
            old_status=ComplaintStatus.RECEIVED,
            raw_update={"response_sla_hours": 48, "response_due_at": explicit},
        )

        assert complaint.response_due_at == explicit

    def test_first_response_is_stamped_on_reaching_awaiting_customer(self):
        complaint = _fake_complaint(
            received_date=self.RECEIVED,
            response_sla_hours=48,
            response_due_at=None,
            first_response_at=None,
            status=ComplaintStatus.AWAITING_CUSTOMER,
        )

        ComplaintService._apply_response_sla(
            complaint,
            old_status=ComplaintStatus.UNDER_INVESTIGATION,
            raw_update={"status": "awaiting_customer"},
        )

        assert complaint.first_response_at is not None

    def test_pending_response_does_not_count_as_having_responded(self):
        complaint = _fake_complaint(
            received_date=self.RECEIVED,
            response_sla_hours=48,
            response_due_at=None,
            first_response_at=None,
            status=ComplaintStatus.PENDING_RESPONSE,
        )

        ComplaintService._apply_response_sla(
            complaint,
            old_status=ComplaintStatus.UNDER_INVESTIGATION,
            raw_update={"status": "pending_response"},
        )

        assert complaint.first_response_at is None

    def test_first_response_is_never_restamped(self):
        original = datetime(2026, 3, 3, 8, 0, tzinfo=timezone.utc)
        complaint = _fake_complaint(
            received_date=self.RECEIVED,
            response_sla_hours=48,
            response_due_at=None,
            first_response_at=original,
            status=ComplaintStatus.RESOLVED,
        )

        ComplaintService._apply_response_sla(
            complaint,
            old_status=ComplaintStatus.AWAITING_CUSTOMER,
            raw_update={"status": "resolved"},
        )

        assert complaint.first_response_at == original


class TestDeleteComplaint:
    @pytest.mark.asyncio
    @patch("src.domain.services.complaint_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.complaint_service.record_audit_event", new_callable=AsyncMock)
    async def test_delete_complaint_soft_deletes(self, mock_audit, mock_cache):
        complaint = _fake_complaint(deleted_at=None, deleted_by_id=None)
        db = AsyncMock()
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = complaint
        empty_children = MagicMock()
        empty_children.scalars.return_value.all.return_value = []
        db.execute = AsyncMock(side_effect=[get_result, empty_children])

        svc = _make_service(db)
        await svc.delete_complaint(1, user_id=5, tenant_id=10, request_id="r1")

        assert complaint.deleted_at is not None
        assert complaint.deleted_by_id == 5
        db.delete.assert_not_called()
        db.flush.assert_awaited()
        mock_audit.assert_awaited_once()
        mock_cache.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_complaint_not_found(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = _make_service(db)
        with pytest.raises(LookupError):
            await svc.delete_complaint(999, user_id=5, tenant_id=10)


class TestCheckComplainantEmailAccess:
    def test_superuser_can_access_any(self):
        svc = _make_service()
        assert svc.check_complainant_email_access("any@x.com", None, False, True) is True

    def test_view_all_permission_allows_access(self):
        svc = _make_service()
        assert svc.check_complainant_email_access("any@x.com", None, True, False) is True

    def test_own_email_matches_case_insensitive(self):
        svc = _make_service()
        assert svc.check_complainant_email_access("User@Example.COM", "user@example.com", False, False) is True

    def test_different_email_denies_access(self):
        svc = _make_service()
        assert svc.check_complainant_email_access("other@x.com", "me@x.com", False, False) is False

    def test_no_current_user_email_denies(self):
        svc = _make_service()
        assert svc.check_complainant_email_access("any@x.com", None, False, False) is False


class TestFeedbackKindWritePath:
    @pytest.mark.asyncio
    async def test_flag_off_rejects_non_complaint_kind(self):
        db = AsyncMock()
        data = MagicMock()
        data.model_dump.return_value = {
            "title": "Well done",
            "external_ref": None,
            "feedback_kind": "compliment",
            "subject_name": "Alex Fitter",
        }
        svc = _make_service(db)
        with pytest.raises(ValidationError, match="customer_feedback_kinds"):
            await svc.create_complaint(complaint_data=data, user_id=5, tenant_id=10)

    @pytest.mark.asyncio
    async def test_compliment_requires_a_named_subject_when_flag_on(self, monkeypatch):
        from src.core.config import settings

        monkeypatch.setattr(settings, "customer_feedback_kinds_enabled", True)
        db = AsyncMock()
        data = MagicMock()
        data.model_dump.return_value = {
            "title": "Well done",
            "external_ref": None,
            "feedback_kind": "compliment",
            "subject_name": None,
            "subject_user_id": None,
        }
        svc = _make_service(db)
        with pytest.raises(ValidationError, match="staff member"):
            await svc.create_complaint(complaint_data=data, user_id=5, tenant_id=10)

    @pytest.mark.asyncio
    @patch("src.domain.services.complaint_service.track_metric")
    @patch("src.domain.services.complaint_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.complaint_service.record_audit_event", new_callable=AsyncMock)
    @patch("src.domain.services.complaint_service.ReferenceNumberService")
    async def test_compliment_mints_cmnd_prefix_when_flag_on(
        self, mock_ref, mock_audit, mock_cache, mock_metric, monkeypatch
    ):
        from src.core.config import settings

        monkeypatch.setattr(settings, "customer_feedback_kinds_enabled", True)
        mock_ref.generate = AsyncMock(return_value="CMND-2026-0001")
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock
        data = MagicMock()
        data.model_dump.return_value = {
            "title": "Well done",
            "external_ref": None,
            "feedback_kind": "compliment",
            "subject_name": "Alex Fitter",
        }
        svc = _make_service(db)
        await svc.create_complaint(complaint_data=data, user_id=5, tenant_id=10)
        assert mock_ref.generate.await_args.args[1] == "compliment"
        mock_metric.assert_called_once_with("complaints.created")

    def test_complaint_still_cannot_skip_investigation_to_close(self):
        with pytest.raises(StateTransitionError):
            validate_complaint_transition("acknowledged", "closed")
        validate_complaint_transition("acknowledged", "closed", kind="compliment")
