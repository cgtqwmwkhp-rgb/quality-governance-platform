"""Unit tests for CAPAService domain logic.

Tests CRUD operations, status transitions, and stats aggregation
using mocked AsyncSession (no real database).
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import StateTransitionError
from src.domain.models.capa import CAPAPriority, CAPASource, CAPAStatus, CAPAType
from src.domain.services.capa_service import CAPAService


def _make_service(db=None):
    if db is None:
        db = AsyncMock()
    return CAPAService(db)


def _fake_capa(**overrides):
    defaults = {
        "id": 1,
        "reference_number": "CAPA-2026-0001",
        "title": "Fix issue",
        "status": CAPAStatus.OPEN,
        "tenant_id": 10,
        "created_by_id": 5,
        "created_at": datetime.now(timezone.utc),
        "due_date": datetime(2026, 12, 31, tzinfo=timezone.utc),
        "completed_at": None,
        "verified_at": None,
        "verified_by_id": None,
    }
    defaults.update(overrides)
    obj = MagicMock(**defaults)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


class TestCAPAServiceInit:
    def test_stores_db_session(self):
        db = AsyncMock()
        svc = CAPAService(db)
        assert svc.db is db


class TestCAPAValidTransitions:
    """Verify the VALID_TRANSITIONS map is correct."""

    def test_open_can_move_to_in_progress(self):
        assert CAPAStatus.IN_PROGRESS in CAPAService.VALID_TRANSITIONS[CAPAStatus.OPEN]

    def test_open_cannot_move_to_closed(self):
        assert CAPAStatus.CLOSED not in CAPAService.VALID_TRANSITIONS[CAPAStatus.OPEN]

    def test_in_progress_can_move_to_verification(self):
        assert CAPAStatus.VERIFICATION in CAPAService.VALID_TRANSITIONS[CAPAStatus.IN_PROGRESS]

    def test_in_progress_can_revert_to_open(self):
        assert CAPAStatus.OPEN in CAPAService.VALID_TRANSITIONS[CAPAStatus.IN_PROGRESS]

    def test_verification_can_close(self):
        assert CAPAStatus.CLOSED in CAPAService.VALID_TRANSITIONS[CAPAStatus.VERIFICATION]

    def test_verification_can_revert_to_in_progress(self):
        assert CAPAStatus.IN_PROGRESS in CAPAService.VALID_TRANSITIONS[CAPAStatus.VERIFICATION]

    def test_overdue_can_move_to_in_progress_or_closed(self):
        allowed = CAPAService.VALID_TRANSITIONS[CAPAStatus.OVERDUE]
        assert CAPAStatus.IN_PROGRESS in allowed
        assert CAPAStatus.CLOSED in allowed

    def test_closed_has_no_transitions(self):
        assert CAPAStatus.CLOSED not in CAPAService.VALID_TRANSITIONS


class TestGetCAPAAction:
    @pytest.mark.asyncio
    async def test_returns_action_when_found(self):
        capa = _fake_capa()
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = capa
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.get_capa_action(1, tenant_id=10)
        assert result.id == 1
        assert result.reference_number == "CAPA-2026-0001"

    @pytest.mark.asyncio
    async def test_raises_lookup_error_when_not_found(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = _make_service(db)
        with pytest.raises(LookupError, match="CAPA with ID 99 not found"):
            await svc.get_capa_action(99, tenant_id=10)


class TestCreateCAPAAction:
    @pytest.mark.asyncio
    @patch("src.domain.services.capa_service.track_metric")
    @patch("src.domain.services.capa_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.capa_service.record_audit_event", new_callable=AsyncMock)
    @patch("src.domain.services.capa_service.ReferenceNumberService")
    async def test_create_generates_ref_and_commits(self, mock_ref_svc, mock_audit, mock_cache, mock_metric):
        mock_ref_svc.generate = AsyncMock(return_value="CAPA-2026-0042")
        db = AsyncMock()

        data = MagicMock()
        data.model_dump.return_value = {"title": "Fix it", "capa_type": "corrective"}

        svc = _make_service(db)
        await svc.create_capa_action(data=data, user_id=5, tenant_id=10)

        db.add.assert_called_once()
        db.commit.assert_awaited()
        db.refresh.assert_awaited()
        mock_cache.assert_awaited_once_with(10, "capa")
        mock_metric.assert_called_once_with("capa.created")
        mock_audit.assert_awaited_once()


class TestUpdateCAPAAction:
    @pytest.mark.asyncio
    @patch("src.domain.services.capa_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.capa_service.apply_updates")
    async def test_update_applies_changes_and_commits(self, mock_apply, mock_cache):
        capa = _fake_capa()
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = capa
        db.execute.return_value = result_mock

        data = MagicMock()
        svc = _make_service(db)
        result = await svc.update_capa_action(1, data, tenant_id=10)

        mock_apply.assert_called_once_with(capa, data)
        db.commit.assert_awaited()
        db.refresh.assert_awaited()
        mock_cache.assert_awaited_once_with(10, "capa")

    @pytest.mark.asyncio
    async def test_update_raises_when_not_found(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = _make_service(db)
        with pytest.raises(LookupError):
            await svc.update_capa_action(999, MagicMock(), tenant_id=10)


class TestTransitionStatus:
    @pytest.mark.asyncio
    @patch("src.domain.services.capa_service.record_audit_event", new_callable=AsyncMock)
    async def test_valid_transition_open_to_in_progress(self, mock_audit):
        capa = _fake_capa(status=CAPAStatus.OPEN)
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = capa
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.transition_status(1, CAPAStatus.IN_PROGRESS, user_id=5, tenant_id=10)
        assert result.status == CAPAStatus.IN_PROGRESS
        db.commit.assert_awaited()

    @pytest.mark.asyncio
    async def test_invalid_transition_raises_state_error(self):
        capa = _fake_capa(status=CAPAStatus.OPEN)
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = capa
        db.execute.return_value = result_mock

        svc = _make_service(db)
        with pytest.raises(StateTransitionError, match="Cannot transition"):
            await svc.transition_status(1, CAPAStatus.CLOSED, user_id=5, tenant_id=10)

    @pytest.mark.asyncio
    @patch("src.domain.services.capa_service.record_audit_event", new_callable=AsyncMock)
    async def test_transition_to_verification_sets_completed_at(self, mock_audit):
        capa = _fake_capa(status=CAPAStatus.IN_PROGRESS)
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = capa
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.transition_status(1, CAPAStatus.VERIFICATION, user_id=5, tenant_id=10)
        assert result.completed_at is not None

    @pytest.mark.asyncio
    @patch("src.domain.services.capa_service.track_metric")
    @patch("src.domain.services.capa_service.record_audit_event", new_callable=AsyncMock)
    async def test_transition_to_closed_sets_verified_fields(self, mock_audit, mock_metric):
        capa = _fake_capa(status=CAPAStatus.VERIFICATION)
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = capa
        db.execute.return_value = result_mock

        svc = _make_service(db)
        result = await svc.transition_status(1, CAPAStatus.CLOSED, user_id=5, tenant_id=10)
        assert result.verified_at is not None
        assert result.verified_by_id == 5
        mock_metric.assert_called_with("capa.closed")

    @pytest.mark.asyncio
    @patch("src.domain.services.capa_service.record_audit_event", new_callable=AsyncMock)
    async def test_transition_records_audit_event(self, mock_audit):
        capa = _fake_capa(status=CAPAStatus.OPEN)
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = capa
        db.execute.return_value = result_mock

        svc = _make_service(db)
        await svc.transition_status(1, CAPAStatus.IN_PROGRESS, user_id=5, tenant_id=10, comment="Starting work")
        mock_audit.assert_awaited_once()
        call_kwargs = mock_audit.call_args.kwargs
        assert call_kwargs["event_type"] == "capa.status_changed"
        assert call_kwargs["payload"]["comment"] == "Starting work"


class TestDeleteCAPAAction:
    @pytest.mark.asyncio
    @patch("src.domain.services.capa_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.capa_service.record_audit_event", new_callable=AsyncMock)
    async def test_delete_removes_and_commits(self, mock_audit, mock_cache):
        capa = _fake_capa()
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = capa
        db.execute.return_value = result_mock

        svc = _make_service(db)
        await svc.delete_capa_action(1, user_id=5, tenant_id=10)

        db.delete.assert_awaited_once_with(capa)
        db.commit.assert_awaited()
        mock_cache.assert_awaited_once_with(10, "capa")

    @pytest.mark.asyncio
    async def test_delete_raises_when_not_found(self):
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = _make_service(db)
        with pytest.raises(LookupError):
            await svc.delete_capa_action(999, user_id=5, tenant_id=10)

    @pytest.mark.asyncio
    @patch("src.domain.services.capa_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.capa_service.record_audit_event", new_callable=AsyncMock)
    async def test_delete_records_audit_event(self, mock_audit, mock_cache):
        capa = _fake_capa()
        db = AsyncMock()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = capa
        db.execute.return_value = result_mock

        svc = _make_service(db)
        await svc.delete_capa_action(1, user_id=5, tenant_id=10)

        mock_audit.assert_awaited_once()
        call_kwargs = mock_audit.call_args.kwargs
        assert call_kwargs["event_type"] == "capa.deleted"
        assert call_kwargs["action"] == "delete"


class TestGetStats:
    @pytest.mark.asyncio
    async def test_returns_aggregated_counts(self):
        db = AsyncMock()
        counters = iter([10, 3, 4, 2])
        result_mock = MagicMock()
        result_mock.scalar_one.side_effect = lambda: next(counters)
        db.execute.return_value = result_mock

        svc = _make_service(db)
        stats = await svc.get_stats(tenant_id=10)

        assert stats["total"] == 10
        assert stats["open"] == 3
        assert stats["in_progress"] == 4
        assert stats["overdue"] == 2
        assert db.execute.call_count == 4
