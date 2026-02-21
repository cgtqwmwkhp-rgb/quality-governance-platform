"""Tests for token revocation service."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.services.token_service import TokenService


class TestTokenService:
    """Tests for TokenService methods."""

    @pytest.mark.asyncio
    async def test_revoke_token(self):
        """Test single token revocation."""
        db = AsyncMock()
        jti = "test-jti-123"
        user_id = 1
        expires_at = datetime.utcnow() + timedelta(hours=1)

        await TokenService.revoke_token(db, jti, user_id, expires_at, reason="logout")

        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        added_entry = db.add.call_args[0][0]
        assert added_entry.jti == jti
        assert added_entry.user_id == user_id
        assert added_entry.reason == "logout"

    @pytest.mark.asyncio
    async def test_is_revoked_true(self):
        """Test checking a revoked token."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = 1
        db.execute.return_value = mock_result

        result = await TokenService.is_revoked(db, "revoked-jti")

        assert result is True

    @pytest.mark.asyncio
    async def test_is_revoked_false(self):
        """Test checking a non-revoked token."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        db.execute.return_value = mock_result

        result = await TokenService.is_revoked(db, "valid-jti")

        assert result is False

    @pytest.mark.asyncio
    async def test_cleanup_expired(self):
        """Test cleanup of expired blacklist entries."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 5
        db.execute.return_value = mock_result

        count = await TokenService.cleanup_expired(db)

        assert count == 5
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_revoke_all_user_tokens(self):
        """Test revoking all tokens for a user."""
        db = AsyncMock()
        mock_result = MagicMock()
        mock_result.rowcount = 3
        db.execute.return_value = mock_result

        count = await TokenService.revoke_all_user_tokens(
            db, user_id=42, reason="admin_revoke"
        )

        assert count == 3
        db.commit.assert_awaited_once()
