"""Unit tests for GDPRService."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import NotFoundError
from src.domain.services.gdpr_service import GDPRService


def _make_mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    return db


def _make_user_row(user_id=1):
    user = MagicMock()
    user.id = user_id
    user.email = "jane@example.com"
    user.first_name = "Jane"
    user.last_name = "Doe"
    user.phone = "+44123456"
    user.job_title = "Engineer"
    user.department = "QA"
    user.created_at = "2024-01-01T00:00:00"
    user.is_active = True
    return user


class TestExportUserData:
    @pytest.mark.asyncio
    async def test_export_user_data_returns_profile(self):
        db = _make_mock_db()
        user = _make_user_row(user_id=42)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = user

        entities_result = MagicMock()
        entities_result.scalars.return_value.all.return_value = []

        db.execute = AsyncMock(side_effect=[result_mock] + [entities_result] * 5)

        svc = GDPRService(db)
        data = await svc.export_user_data(user_id=42, tenant_id=1)

        assert "user_profile" in data
        assert data["user_profile"]["email"] == "jane@example.com"
        assert data["user_profile"]["first_name"] == "Jane"
        assert data["user_profile"]["last_name"] == "Doe"
        assert "export_date" in data

    @pytest.mark.asyncio
    async def test_export_user_data_not_found_raises(self):
        db = _make_mock_db()

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        svc = GDPRService(db)
        with pytest.raises(NotFoundError, match="User not found"):
            await svc.export_user_data(user_id=999, tenant_id=1)


class TestRequestErasure:
    @pytest.mark.asyncio
    async def test_request_erasure_anonymizes_user(self):
        db = _make_mock_db()
        user = _make_user_row(user_id=7)

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = user
        db.execute = AsyncMock(return_value=result_mock)

        svc = GDPRService(db)
        result = await svc.request_erasure(user_id=7, tenant_id=1, reason="GDPR request")

        assert user.first_name == "REDACTED"
        assert user.last_name == "REDACTED"
        assert user.phone is None
        assert user.job_title is None
        assert user.department is None
        assert user.is_active is False
        assert user.email == "deleted-7@anonymized.local"

        assert result["status"] == "completed"
        assert result["user_id"] == 7
        assert result["reason"] == "GDPR request"
        assert "anonymized_at" in result
        db.commit.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_request_erasure_not_found_raises(self):
        db = _make_mock_db()

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        svc = GDPRService(db)
        with pytest.raises(NotFoundError, match="User not found"):
            await svc.request_erasure(user_id=999, tenant_id=1)
