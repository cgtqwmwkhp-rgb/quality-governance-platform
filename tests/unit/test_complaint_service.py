"""Unit tests for ComplaintService and complaint transition logic.

Tests CRUD, status transition validation, and email access checks
using mocked AsyncSession (no real database).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import StateTransitionError
from src.domain.models.complaint import ComplaintStatus
from src.domain.services.complaint_service import COMPLAINT_TRANSITIONS, ComplaintService, validate_complaint_transition

# ---------------------------------------------------------------------------
# Transition validation (pure function, no DB needed)
# ---------------------------------------------------------------------------


class TestComplaintTransitionMap:
    """Validate the transition map constants."""

    def test_received_can_move_to_acknowledged(self):
        assert ComplaintStatus.ACKNOWLEDGED in COMPLAINT_TRANSITIONS[ComplaintStatus.RECEIVED]

    def test_received_can_escalate(self):
        assert ComplaintStatus.ESCALATED in COMPLAINT_TRANSITIONS[ComplaintStatus.RECEIVED]

    def test_closed_has_no_transitions(self):
        assert COMPLAINT_TRANSITIONS[ComplaintStatus.CLOSED] == set()

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

    def test_closed_to_anything_raises(self):
        with pytest.raises(StateTransitionError):
            validate_complaint_transition("closed", "received")

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
