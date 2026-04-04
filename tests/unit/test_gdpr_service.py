"""Unit tests for GDPRService — data export, erasure, and restriction.

All database interactions are mocked via AsyncMock.
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

import pytest


def _make_db():
    return AsyncMock()


def _fake_user(**overrides):
    defaults = {
        "id": 1,
        "email": "john@example.com",
        "first_name": "John",
        "last_name": "Doe",
        "phone": "555-1234",
        "job_title": "Engineer",
        "department": "QA",
        "created_at": datetime(2025, 1, 1, tzinfo=timezone.utc),
        "is_active": True,
        "tenant_id": 10,
    }
    defaults.update(overrides)
    obj = MagicMock(**defaults)
    for k, v in defaults.items():
        setattr(obj, k, v)
    return obj


class TestGDPRServiceInit:
    def test_default_dry_run_false(self):
        from src.domain.services.gdpr_service import GDPRService

        db = _make_db()
        svc = GDPRService(db)
        assert svc.dry_run is False

    def test_dry_run_mode(self):
        from src.domain.services.gdpr_service import GDPRService

        db = _make_db()
        svc = GDPRService(db, dry_run=True)
        assert svc.dry_run is True


class TestExportUserData:
    @pytest.mark.asyncio
    async def test_export_returns_user_profile(self):
        from src.domain.services.gdpr_service import GDPRService

        user = _fake_user()
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = user
        db.execute.return_value = result_mock

        svc = GDPRService(db)
        svc._collect_user_entities = AsyncMock(return_value=[])
        svc._collect_audit_entries = AsyncMock(return_value=[])

        data = await svc.export_user_data(1, tenant_id=10)
        assert data["user_profile"]["email"] == "john@example.com"
        assert data["user_profile"]["first_name"] == "John"
        assert "export_date" in data

    @pytest.mark.asyncio
    async def test_export_user_not_found_raises(self):
        from src.domain.exceptions import NotFoundError
        from src.domain.services.gdpr_service import GDPRService

        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = GDPRService(db)
        with pytest.raises(NotFoundError, match="User not found"):
            await svc.export_user_data(999, tenant_id=10)

    @pytest.mark.asyncio
    async def test_export_includes_all_entity_categories(self):
        from src.domain.services.gdpr_service import GDPRService

        user = _fake_user()
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = user
        db.execute.return_value = result_mock

        svc = GDPRService(db)
        svc._collect_user_entities = AsyncMock(return_value=[{"id": 1, "type": "test"}])
        svc._collect_audit_entries = AsyncMock(return_value=[])

        data = await svc.export_user_data(1, tenant_id=10)
        assert "incidents" in data
        assert "complaints" in data
        assert "incident_actions" in data
        assert "complaint_actions" in data
        assert "audit_log" in data


class TestCollectUserEntities:
    @pytest.mark.asyncio
    async def test_returns_empty_list_on_exception(self):
        from src.domain.services.gdpr_service import GDPRService

        db = _make_db()
        db.execute.side_effect = Exception("DB error")

        svc = GDPRService(db)
        result = await svc._collect_user_entities("Incident", "reporter_id", 1, 10)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_when_user_field_missing(self):
        from src.domain.services.gdpr_service import GDPRService

        db = _make_db()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        result_mock = MagicMock()
        result_mock.scalars.return_value = scalars_mock
        db.execute.return_value = result_mock

        svc = GDPRService(db)
        result = await svc._collect_user_entities("Incident", "nonexistent_field", 1, 10)
        assert result == []


class TestCollectAuditEntries:
    @pytest.mark.asyncio
    async def test_returns_empty_on_exception(self):
        from src.domain.services.gdpr_service import GDPRService

        db = _make_db()
        db.execute.side_effect = Exception("DB down")

        svc = GDPRService(db)
        result = await svc._collect_audit_entries(1, 10)
        assert result == []


class TestRestrictProcessing:
    @pytest.mark.asyncio
    async def test_unsupported_record_type_raises(self):
        from src.domain.exceptions import BadRequestError
        from src.domain.services.gdpr_service import GDPRService

        db = _make_db()

        svc = GDPRService(db)
        with pytest.raises(BadRequestError, match="Unsupported record type"):
            await svc.restrict_processing(1, "nonexistent_type", 100)

    @pytest.mark.asyncio
    async def test_record_not_found_raises(self):
        from src.domain.exceptions import NotFoundError
        from src.domain.services.gdpr_service import GDPRService

        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = GDPRService(db)
        with pytest.raises(NotFoundError):
            await svc.restrict_processing(1, "incident", 999)

    @pytest.mark.asyncio
    async def test_restrict_processing_success(self):
        from src.domain.services.gdpr_service import GDPRService

        db = _make_db()
        record = MagicMock()
        record.processing_restricted = False
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = record
        db.execute.return_value = result_mock

        svc = GDPRService(db)
        result = await svc.restrict_processing(1, "incident", 42)

        assert result["status"] == "restriction_applied"
        assert result["record_type"] == "incident"
        assert result["record_id"] == 42
        assert record.processing_restricted is True
        db.commit.assert_awaited_once()


class TestRequestErasure:
    @pytest.mark.asyncio
    async def test_erasure_user_not_found_raises(self):
        from src.domain.exceptions import NotFoundError
        from src.domain.services.gdpr_service import GDPRService

        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute.return_value = result_mock

        svc = GDPRService(db)
        with pytest.raises(NotFoundError, match="User not found"):
            await svc.request_erasure(999, tenant_id=10)

    @pytest.mark.asyncio
    async def test_dry_run_returns_would_affect(self):
        from src.domain.services.gdpr_service import GDPRService

        user = _fake_user()
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = user
        db.execute.return_value = result_mock

        pseudo_result = MagicMock()
        pseudo_result.fields_affected = {"email": "anonymized", "name": "anonymized"}

        svc = GDPRService(db, dry_run=True)
        svc._pseudo = MagicMock()
        svc._pseudo.pseudonymize_user = AsyncMock(return_value=pseudo_result)

        result = await svc.request_erasure(1, tenant_id=10, reason="GDPR request")
        assert result["status"] == "dry_run"
        assert result["would_affect"] == pseudo_result.fields_affected
        assert result["reason"] == "GDPR request"

    @pytest.mark.asyncio
    async def test_full_erasure_clears_metadata(self):
        from src.domain.services.gdpr_service import GDPRService

        user = _fake_user()
        db = _make_db()
        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = user
        db.execute.return_value = result_mock

        pseudo_result = MagicMock()
        pseudo_result.fields_affected = {"email": "hashed"}

        svc = GDPRService(db, dry_run=False)
        svc._pseudo = MagicMock()
        svc._pseudo.pseudonymize_user = AsyncMock(return_value=pseudo_result)

        result = await svc.request_erasure(1, tenant_id=10)
        assert result["status"] == "completed"
        assert user.job_title is None
        assert user.department is None
        db.commit.assert_awaited_once()


class TestGetModelMap:
    def test_model_map_contains_expected_keys(self):
        from src.domain.services.gdpr_service import GDPRService

        GDPRService._RECORD_TYPE_MAP = {}
        model_map = GDPRService._get_model_map()
        assert "incident" in model_map
        assert "complaint" in model_map
        assert "near_miss" in model_map

    def test_model_map_is_cached(self):
        from src.domain.services.gdpr_service import GDPRService

        GDPRService._RECORD_TYPE_MAP = {}
        first = GDPRService._get_model_map()
        second = GDPRService._get_model_map()
        assert first is second
