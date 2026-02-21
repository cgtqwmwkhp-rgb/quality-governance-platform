"""Tests for data retention service."""

import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

from src.domain.services.data_retention_service import DataRetentionService  # noqa: E402


class TestDataRetentionService:
    """Tests for DataRetentionService."""

    def test_retention_policies_defined(self):
        """Verify retention policies are configured."""
        policies = DataRetentionService.RETENTION_POLICIES
        assert "token_blacklist" in policies
        assert "audit_trail_entries" in policies
        assert policies["token_blacklist"] == 7
        assert policies["audit_trail_entries"] == 365

    def test_all_four_policies_present(self):
        """All four retention categories are configured."""
        policies = DataRetentionService.RETENTION_POLICIES
        expected = {"token_blacklist", "audit_trail_entries", "telemetry_events", "notification_history"}
        assert set(policies.keys()) == expected

    def test_policy_days_are_positive(self):
        """Every retention policy has a positive day count."""
        for key, days in DataRetentionService.RETENTION_POLICIES.items():
            assert days > 0, f"{key} has non-positive retention days"

    def test_telemetry_retention_is_90_days(self):
        """Telemetry events are retained for 90 days."""
        assert DataRetentionService.RETENTION_POLICIES["telemetry_events"] == 90

    def test_notification_retention_is_180_days(self):
        """Notification history is retained for 180 days."""
        assert DataRetentionService.RETENTION_POLICIES["notification_history"] == 180

    @pytest.mark.asyncio
    async def test_cleanup_expired_tokens(self):
        """Test expired token cleanup."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 10
        db.execute.return_value = mock_result

        count = await DataRetentionService.cleanup_expired_tokens(db)

        assert count == 10
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_audit_entries(self):
        """Audit entry cleanup commits and returns row count."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 25
        db.execute.return_value = mock_result

        count = await DataRetentionService.cleanup_old_audit_entries(db)

        assert count == 25
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_notifications(self):
        """Notification cleanup commits and returns row count."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 42
        db.execute.return_value = mock_result

        count = await DataRetentionService.cleanup_old_notifications(db)

        assert count == 42
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_telemetry_returns_zero(self):
        """Telemetry cleanup is a no-op and returns 0."""
        db = AsyncMock()
        count = await DataRetentionService.cleanup_old_telemetry(db)
        assert count == 0
        db.execute.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_run_all_policies(self):
        """Test running all retention policies."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 3
        db.execute.return_value = mock_result

        results = await DataRetentionService.run_all_policies(db)

        assert "token_blacklist" in results
        assert isinstance(results["token_blacklist"], int)

    @pytest.mark.asyncio
    async def test_run_all_policies_returns_all_keys(self):
        """run_all_policies returns a dict with all four policy keys."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 0
        db.execute.return_value = mock_result

        results = await DataRetentionService.run_all_policies(db)

        expected_keys = {"token_blacklist", "audit_trail_entries", "telemetry_events", "notification_history"}
        assert set(results.keys()) == expected_keys

    @pytest.mark.asyncio
    async def test_run_all_policies_telemetry_is_zero(self):
        """Telemetry key in run_all_policies is always 0 (no-op)."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 5
        db.execute.return_value = mock_result

        results = await DataRetentionService.run_all_policies(db)
        assert results["telemetry_events"] == 0
