"""Tests for data retention service."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.services.data_retention_service import DataRetentionService


class TestDataRetentionService:
    """Tests for DataRetentionService."""

    def test_retention_policies_defined(self):
        """Verify retention policies are configured."""
        policies = DataRetentionService.RETENTION_POLICIES
        assert "token_blacklist" in policies
        assert "audit_trail_entries" in policies
        assert policies["token_blacklist"] == 7
        assert policies["audit_trail_entries"] == 365

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
    async def test_run_all_policies(self):
        """Test running all retention policies."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 3
        db.execute.return_value = mock_result

        results = await DataRetentionService.run_all_policies(db)

        assert "token_blacklist" in results
        assert isinstance(results["token_blacklist"], int)
