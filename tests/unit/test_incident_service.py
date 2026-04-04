"""Tests for src.domain.services.incident_service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import StateTransitionError
from src.domain.services.incident_service import INCIDENT_TRANSITIONS, IncidentService, validate_incident_transition

# ---------------------------------------------------------------------------
# validate_incident_transition
# ---------------------------------------------------------------------------


class TestValidateIncidentTransition:
    def test_valid_reported_to_under_investigation(self):
        validate_incident_transition("reported", "under_investigation")

    def test_valid_reported_to_closed(self):
        validate_incident_transition("reported", "closed")

    def test_valid_under_investigation_to_pending_actions(self):
        validate_incident_transition("under_investigation", "pending_actions")

    def test_invalid_closed_to_reported(self):
        with pytest.raises(StateTransitionError):
            validate_incident_transition("closed", "reported")

    def test_invalid_reported_to_pending_review(self):
        with pytest.raises(StateTransitionError):
            validate_incident_transition("reported", "pending_review")

    def test_unknown_status_does_not_raise(self):
        validate_incident_transition("unknown_status", "reported")

    def test_valid_pending_actions_to_actions_in_progress(self):
        validate_incident_transition("pending_actions", "actions_in_progress")

    def test_valid_actions_in_progress_to_pending_review(self):
        validate_incident_transition("actions_in_progress", "pending_review")

    def test_valid_pending_review_to_closed(self):
        validate_incident_transition("pending_review", "closed")

    def test_state_transition_error_includes_allowed(self):
        with pytest.raises(StateTransitionError) as exc_info:
            validate_incident_transition("closed", "reported")
        assert "allowed" in exc_info.value.details

    def test_closed_has_no_transitions(self):
        assert (
            INCIDENT_TRANSITIONS.get(
                __import__("src.domain.models.incident", fromlist=["IncidentStatus"]).IncidentStatus.CLOSED
            )
            == set()
        )


# ---------------------------------------------------------------------------
# IncidentService
# ---------------------------------------------------------------------------


class TestIncidentService:
    @pytest.fixture
    def service(self):
        db = AsyncMock()
        return IncidentService(db)

    @pytest.mark.asyncio
    async def test_get_incident_not_found(self, service):
        result = MagicMock()
        result.scalar_one_or_none.return_value = None
        service.db.execute.return_value = result

        with pytest.raises(LookupError, match="not found"):
            await service.get_incident(999, tenant_id=1)

    @pytest.mark.asyncio
    async def test_get_incident_found(self, service):
        incident = MagicMock(id=1)
        result = MagicMock()
        result.scalar_one_or_none.return_value = incident
        service.db.execute.return_value = result

        found = await service.get_incident(1, tenant_id=1)
        assert found is incident

    @pytest.mark.asyncio
    async def test_get_incident_skip_tenant_check(self, service):
        incident = MagicMock(id=1)
        result = MagicMock()
        result.scalar_one_or_none.return_value = incident
        service.db.execute.return_value = result

        found = await service.get_incident(1, None, skip_tenant_check=True)
        assert found is incident

    @pytest.mark.asyncio
    @patch("src.domain.services.incident_service.record_audit_event", new_callable=AsyncMock)
    @patch("src.domain.services.incident_service.invalidate_tenant_cache", new_callable=AsyncMock)
    async def test_delete_incident_happy_path(self, _cache, _audit, service):
        incident = MagicMock(id=1, reference_number="INC-001", tenant_id=1)
        service.get_incident = AsyncMock(return_value=incident)

        await service.delete_incident(1, user_id=1, tenant_id=1, request_id="r1")
        service.db.delete.assert_called_once_with(incident)
        service.db.flush.assert_awaited()

    @pytest.mark.asyncio
    async def test_delete_incident_not_found(self, service):
        service.get_incident = AsyncMock(side_effect=LookupError("not found"))

        with pytest.raises(LookupError):
            await service.delete_incident(999, user_id=1, tenant_id=1)

    @pytest.mark.asyncio
    @patch("src.domain.services.incident_service.record_incident_created", create=True)
    @patch("src.domain.services.incident_service.track_business_event")
    @patch("src.domain.services.incident_service.record_audit_event", new_callable=AsyncMock)
    @patch("src.domain.services.incident_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.incident_service.ReferenceNumberService.generate", new_callable=AsyncMock)
    @patch("src.domain.services.incident_service.Incident")
    async def test_create_incident_auto_reference(self, MockIncident, mock_gen, _cache, _audit, _track, _rec, service):
        mock_gen.return_value = "INC-2026-0001"
        mock_incident = MagicMock(id=1, reference_number="INC-2026-0001", tenant_id=1)
        MockIncident.return_value = mock_incident
        service.db.refresh = AsyncMock()

        data = MagicMock()
        data.model_dump.return_value = {
            "title": "Test",
            "description": "Desc",
            "incident_date": "2026-01-01",
        }

        result = await service.create_incident(
            incident_data=data,
            user_id=1,
            tenant_id=1,
            has_set_ref_permission=False,
        )
        mock_gen.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_create_incident_explicit_ref_no_permission(self, service):
        data = MagicMock()
        data.model_dump.return_value = {
            "title": "Test",
            "description": "Desc",
            "incident_date": "2026-01-01",
            "reference_number": "INC-CUSTOM",
        }

        with pytest.raises(PermissionError, match="Not authorized"):
            await service.create_incident(
                incident_data=data,
                user_id=1,
                tenant_id=1,
                has_set_ref_permission=False,
            )

    @pytest.mark.asyncio
    async def test_create_incident_duplicate_reference(self, service):
        data = MagicMock()
        data.model_dump.return_value = {
            "title": "Test",
            "description": "Desc",
            "incident_date": "2026-01-01",
            "reference_number": "INC-DUP",
        }
        existing = MagicMock()
        result = MagicMock()
        result.scalar_one_or_none.return_value = existing
        service.db.execute.return_value = result

        with pytest.raises(ValueError, match="Duplicate"):
            await service.create_incident(
                incident_data=data,
                user_id=1,
                tenant_id=1,
                has_set_ref_permission=True,
            )


# ---------------------------------------------------------------------------
# check_reporter_email_access
# ---------------------------------------------------------------------------


class TestCheckReporterEmailAccess:
    @pytest.fixture
    def service(self):
        return IncidentService(AsyncMock())

    @pytest.mark.asyncio
    async def test_superuser_always_allowed(self, service):
        assert (
            await service.check_reporter_email_access("any@email.com", None, has_view_all=False, is_superuser=True)
            is True
        )

    @pytest.mark.asyncio
    async def test_view_all_permission_allowed(self, service):
        assert (
            await service.check_reporter_email_access(
                "any@email.com", "other@email.com", has_view_all=True, is_superuser=False
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_own_email_allowed(self, service):
        assert (
            await service.check_reporter_email_access(
                "user@email.com", "USER@email.com", has_view_all=False, is_superuser=False
            )
            is True
        )

    @pytest.mark.asyncio
    async def test_different_email_denied(self, service):
        assert (
            await service.check_reporter_email_access(
                "other@email.com", "me@email.com", has_view_all=False, is_superuser=False
            )
            is False
        )

    @pytest.mark.asyncio
    async def test_no_current_email_denied(self, service):
        assert (
            await service.check_reporter_email_access("other@email.com", None, has_view_all=False, is_superuser=False)
            is False
        )
