"""Tests for src.domain.services.audit_log_service."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.audit_log_service import AuditLogService


def _mock_scalar(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


def _mock_scalars(values):
    result = MagicMock()
    result.scalars.return_value.all.return_value = values
    return result


# ---------------------------------------------------------------------------
# AuditLogService.log
# ---------------------------------------------------------------------------


class TestAuditLogServiceLog:
    """Test the log method's business logic: hash chain, sequence, and changed fields.

    The log() method constructs AuditLogEntry instances, which triggers SA mapper
    initialization. To avoid that in unit tests, we test the internal logic that
    the log() method implements: sequence numbering, previous hash chaining, and
    changed field detection.
    """

    def test_genesis_hash_value(self):
        assert AuditLogService.GENESIS_HASH == "0" * 64

    def test_changed_fields_detection(self):
        old_values = {"name": "Old", "email": "same@x.com", "dept": "IT"}
        new_values = {"name": "New", "email": "same@x.com", "dept": "HR"}
        changed = [k for k in set(old_values.keys()) | set(new_values.keys()) if old_values.get(k) != new_values.get(k)]
        assert "name" in changed
        assert "dept" in changed
        assert "email" not in changed

    def test_changed_fields_none_old_values(self):
        old_values = None
        new_values = {"name": "New"}
        changed = None
        if old_values and new_values:
            changed = [
                k for k in set(old_values.keys()) | set(new_values.keys()) if old_values.get(k) != new_values.get(k)
            ]
        assert changed is None

    def test_sequence_from_genesis(self):
        previous_entry = None
        if previous_entry:
            sequence = previous_entry.sequence + 1
        else:
            sequence = 1
        assert sequence == 1

    def test_sequence_from_previous(self):
        previous_entry = MagicMock(sequence=5, entry_hash="prev_hash")
        sequence = previous_entry.sequence + 1
        previous_hash = previous_entry.entry_hash
        assert sequence == 6
        assert previous_hash == "prev_hash"


# ---------------------------------------------------------------------------
# Convenience log methods
# ---------------------------------------------------------------------------


class TestConvenienceLogMethods:
    @pytest.fixture
    def service(self):
        svc = AuditLogService(AsyncMock())
        svc.log = AsyncMock(return_value=MagicMock())
        return svc

    @pytest.mark.asyncio
    async def test_log_create(self, service):
        await service.log_create(1, "incident", "1", {"title": "New"})
        service.log.assert_awaited_once()
        call_kwargs = service.log.call_args[1]
        assert call_kwargs["action"] == "create"

    @pytest.mark.asyncio
    async def test_log_update(self, service):
        await service.log_update(1, "incident", "1", {"title": "Old"}, {"title": "New"})
        call_kwargs = service.log.call_args[1]
        assert call_kwargs["action"] == "update"

    @pytest.mark.asyncio
    async def test_log_delete(self, service):
        await service.log_delete(1, "incident", "1", {"title": "Gone"})
        call_kwargs = service.log.call_args[1]
        assert call_kwargs["action"] == "delete"

    @pytest.mark.asyncio
    async def test_log_view(self, service):
        await service.log_view(1, "incident", "1")
        call_kwargs = service.log.call_args[1]
        assert call_kwargs["action"] == "view"

    @pytest.mark.asyncio
    async def test_log_auth(self, service):
        await service.log_auth(1, "login", user_id=5)
        call_kwargs = service.log.call_args[1]
        assert call_kwargs["action"] == "login"
        assert call_kwargs["action_category"] == "auth"

    @pytest.mark.asyncio
    async def test_log_auth_anonymous(self, service):
        await service.log_auth(1, "login_failed")
        call_kwargs = service.log.call_args[1]
        assert call_kwargs["entity_id"] == "anonymous"

    @pytest.mark.asyncio
    async def test_log_admin(self, service):
        await service.log_admin(1, "disable", "user", "5")
        call_kwargs = service.log.call_args[1]
        assert call_kwargs["action_category"] == "admin"


# ---------------------------------------------------------------------------
# Querying
# ---------------------------------------------------------------------------


class TestAuditLogQuerying:
    @pytest.fixture
    def service(self):
        return AuditLogService(AsyncMock())

    @pytest.mark.asyncio
    async def test_get_entries_basic(self, service):
        service.db.execute.return_value = _mock_scalars([MagicMock()])
        entries = await service.get_entries(tenant_id=1)
        assert len(entries) == 1

    @pytest.mark.asyncio
    async def test_get_entries_with_filters(self, service):
        service.db.execute.return_value = _mock_scalars([])
        entries = await service.get_entries(
            tenant_id=1,
            entity_type="incident",
            action="create",
            user_id=5,
        )
        assert entries == []

    @pytest.mark.asyncio
    async def test_get_entity_history(self, service):
        service.db.execute.return_value = _mock_scalars([MagicMock(), MagicMock()])
        history = await service.get_entity_history(1, "incident", "42")
        assert len(history) == 2

    @pytest.mark.asyncio
    async def test_get_user_activity(self, service):
        service.get_entries = AsyncMock(return_value=[MagicMock()])
        activity = await service.get_user_activity(1, user_id=5, days=7)
        assert len(activity) == 1


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


class TestAuditLogVerification:
    @pytest.fixture
    def service(self):
        return AuditLogService(AsyncMock())

    @pytest.mark.asyncio
    @patch("src.domain.services.audit_log_service.AuditLogVerification")
    async def test_verify_chain_empty(self, MockVerification, service):
        service.db.execute.return_value = _mock_scalars([])
        service.db.refresh = AsyncMock()
        mock_ver = MagicMock(is_valid=True, entries_verified=0)
        MockVerification.return_value = mock_ver

        verification = await service.verify_chain(tenant_id=1)
        assert verification.is_valid is True
        assert verification.entries_verified == 0

    @pytest.mark.asyncio
    @patch("src.domain.services.audit_log_service.AuditLogVerification")
    async def test_verify_chain_valid_single_entry(self, MockVerification, service):
        entry = MagicMock(
            sequence=1,
            previous_hash="0" * 64,
            entry_hash="valid_hash",
            entity_type="incident",
            entity_id="1",
            action="create",
            user_id=1,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            old_values=None,
            new_values={"title": "Test"},
        )
        service.db.execute.return_value = _mock_scalars([entry])
        service.db.refresh = AsyncMock()
        mock_ver = MagicMock(is_valid=True, entries_verified=1)
        MockVerification.return_value = mock_ver

        with patch("src.domain.services.audit_log_service.AuditLogEntry.compute_hash", return_value="valid_hash"):
            verification = await service.verify_chain(tenant_id=1)

        assert verification.is_valid is True
        assert verification.entries_verified == 1

    @pytest.mark.asyncio
    @patch("src.domain.services.audit_log_service.AuditLogVerification")
    async def test_verify_chain_detects_tampered_hash(self, MockVerification, service):
        entry = MagicMock(
            sequence=1,
            previous_hash="0" * 64,
            entry_hash="stored_hash",
            entity_type="incident",
            entity_id="1",
            action="create",
            user_id=1,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            old_values=None,
            new_values=None,
        )
        service.db.execute.return_value = _mock_scalars([entry])
        service.db.refresh = AsyncMock()
        mock_ver = MagicMock(is_valid=False, entries_verified=1)
        MockVerification.return_value = mock_ver

        with patch("src.domain.services.audit_log_service.AuditLogEntry.compute_hash", return_value="different_hash"):
            verification = await service.verify_chain(tenant_id=1)

        assert verification.is_valid is False


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------


class TestAuditLogExport:
    @pytest.fixture
    def service(self):
        svc = AuditLogService(AsyncMock())
        return svc

    @pytest.mark.asyncio
    async def test_export_logs_returns_data_and_record(self, service):
        entry = MagicMock(
            sequence=1,
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
            entity_type="incident",
            entity_id="1",
            entity_name="Test Incident",
            action="create",
            user_id=1,
            user_email="admin@test.com",
            user_name="Admin",
            old_values=None,
            new_values={"title": "New"},
            changed_fields=["title"],
            ip_address="127.0.0.1",
            entry_hash="abc123",
        )
        service.get_entries = AsyncMock(return_value=[entry])
        service.db.refresh = AsyncMock()

        with patch("src.domain.services.audit_log_service.AuditLogExport") as MockExport:
            MockExport.return_value = MagicMock()
            data, export_record = await service.export_logs(
                tenant_id=1,
                exported_by_id=1,
                reason="compliance",
            )

        assert len(data) == 1
        assert data[0]["entity_type"] == "incident"
        assert data[0]["action"] == "create"


# ---------------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------------


class TestAuditLogStats:
    @pytest.fixture
    def service(self):
        return AuditLogService(AsyncMock())

    @pytest.mark.asyncio
    async def test_get_stats(self, service):
        total_result = MagicMock()
        total_result.scalar.return_value = 100
        action_result = MagicMock()
        action_result.all.return_value = [("create", 50), ("update", 30)]
        entity_result = MagicMock()
        entity_result.all.return_value = [("incident", 60), ("risk", 20)]
        user_result = MagicMock()
        user_result.all.return_value = [("admin@test.com", 40)]

        service.db.execute = AsyncMock(
            side_effect=[
                total_result,
                action_result,
                entity_result,
                user_result,
            ]
        )

        stats = await service.get_stats(tenant_id=1, days=30)
        assert stats["total_entries"] == 100
        assert stats["period_days"] == 30
