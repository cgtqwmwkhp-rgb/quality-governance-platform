"""Tests for src.domain.services.form_config_service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import AuthorizationError, ConflictError, NotFoundError
from src.domain.services.form_config_service import FormConfigService


def _make_service():
    db = AsyncMock()
    return FormConfigService(db), db


def _mock_scalar(value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    return result


# ---------------------------------------------------------------------------
# _get_or_raise  (tested indirectly via higher-level methods)
# ---------------------------------------------------------------------------


class TestGetOrRaise:
    @pytest.mark.asyncio
    async def test_get_template_returns_entity_when_found(self):
        svc, db = _make_service()
        entity = MagicMock(id=1)
        db.execute.return_value = _mock_scalar(entity)
        result = await svc.get_template(1, tenant_id=1)
        assert result is entity

    @pytest.mark.asyncio
    async def test_get_template_raises_not_found_when_missing(self):
        svc, db = _make_service()
        db.execute.return_value = _mock_scalar(None)
        with pytest.raises(NotFoundError):
            await svc.get_template(999, tenant_id=1)


# ---------------------------------------------------------------------------
# Template CRUD
# ---------------------------------------------------------------------------


class TestCreateTemplate:
    @pytest.mark.asyncio
    @patch("src.domain.services.form_config_service.record_audit_event", new_callable=AsyncMock)
    @patch("src.domain.services.form_config_service.track_metric")
    async def test_create_template_raises_conflict_on_duplicate_slug(self, _metric, _audit):
        svc, db = _make_service()
        db.execute.return_value = _mock_scalar(MagicMock())
        data = MagicMock()
        data.slug = "existing-slug"
        with pytest.raises(ConflictError):
            await svc.create_template(data=data, user_id=1, request_id="r1")


class TestGetTemplateBySlug:
    @pytest.mark.asyncio
    async def test_returns_template_when_found(self):
        svc, db = _make_service()
        template = MagicMock()
        db.execute.return_value = _mock_scalar(template)
        result = await svc.get_template_by_slug("my-form")
        assert result is template

    @pytest.mark.asyncio
    async def test_raises_not_found_when_missing(self):
        svc, db = _make_service()
        db.execute.return_value = _mock_scalar(None)
        with pytest.raises(NotFoundError):
            await svc.get_template_by_slug("nonexistent")


class TestDeleteTemplate:
    @pytest.mark.asyncio
    @patch("src.domain.services.form_config_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.form_config_service.record_audit_event", new_callable=AsyncMock)
    @patch("src.domain.services.form_config_service.track_metric")
    async def test_delete_template_happy_path(self, _metric, _audit, _cache):
        svc, db = _make_service()
        entity = MagicMock(id=1, name="T")
        db.execute.return_value = _mock_scalar(entity)
        await svc.delete_template(1, user_id=1, tenant_id=1, request_id="r1")
        db.delete.assert_called_once_with(entity)
        db.commit.assert_awaited_once()


class TestPublishTemplate:
    @pytest.mark.asyncio
    @patch("src.domain.services.form_config_service.record_audit_event", new_callable=AsyncMock)
    async def test_publish_sets_published(self, _audit):
        svc, db = _make_service()
        template = MagicMock(id=1, is_published=False, published_at=None)
        db.execute.return_value = _mock_scalar(template)
        db.refresh = AsyncMock()
        result = await svc.publish_template(1, user_id=1, tenant_id=1, request_id="r1")
        assert result.is_published is True
        assert result.published_at is not None


# ---------------------------------------------------------------------------
# Contract CRUD
# ---------------------------------------------------------------------------


class TestContracts:
    @pytest.mark.asyncio
    @patch("src.domain.services.form_config_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.form_config_service.record_audit_event", new_callable=AsyncMock)
    @patch("src.domain.services.form_config_service.track_metric")
    async def test_create_contract_raises_conflict_on_duplicate_code(self, _m, _a, _c):
        svc, db = _make_service()
        db.execute.return_value = _mock_scalar(MagicMock())
        data = MagicMock()
        data.code = "DUP"
        with pytest.raises(ConflictError):
            await svc.create_contract(data=data, user_id=1, tenant_id=1, request_id="r1")

    @pytest.mark.asyncio
    async def test_get_contract_found(self):
        svc, db = _make_service()
        contract = MagicMock(id=1)
        db.execute.return_value = _mock_scalar(contract)
        result = await svc.get_contract(1, tenant_id=1)
        assert result is contract

    @pytest.mark.asyncio
    async def test_get_contract_not_found(self):
        svc, db = _make_service()
        db.execute.return_value = _mock_scalar(None)
        with pytest.raises(NotFoundError):
            await svc.get_contract(999, tenant_id=1)

    @pytest.mark.asyncio
    @patch("src.domain.services.form_config_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.form_config_service.record_audit_event", new_callable=AsyncMock)
    @patch("src.domain.services.form_config_service.track_metric")
    async def test_delete_contract(self, _m, _a, _c):
        svc, db = _make_service()
        contract = MagicMock(id=1, name="C")
        db.execute.return_value = _mock_scalar(contract)
        await svc.delete_contract(1, user_id=1, tenant_id=1, request_id="r1")
        db.delete.assert_called_once_with(contract)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


class TestSettings:
    @pytest.mark.asyncio
    @patch("src.domain.services.form_config_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.form_config_service.track_metric")
    async def test_create_setting_raises_conflict_on_duplicate_key(self, _metric, _cache):
        svc, db = _make_service()
        db.execute.return_value = _mock_scalar(MagicMock())
        data = MagicMock()
        data.key = "existing.key"
        with pytest.raises(ConflictError):
            await svc.create_setting(data=data, user_id=1, tenant_id=1)

    @pytest.mark.asyncio
    @patch("src.domain.services.form_config_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.form_config_service.track_metric")
    async def test_update_setting_raises_not_found(self, _metric, _cache):
        svc, db = _make_service()
        db.execute.return_value = _mock_scalar(None)
        with pytest.raises(NotFoundError):
            await svc.update_setting("missing.key", data=MagicMock(), user_id=1, tenant_id=1)

    @pytest.mark.asyncio
    @patch("src.domain.services.form_config_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.form_config_service.track_metric")
    async def test_update_setting_raises_authorization_when_not_editable(self, _metric, _cache):
        svc, db = _make_service()
        setting = MagicMock(is_editable=False)
        db.execute.return_value = _mock_scalar(setting)
        with pytest.raises(AuthorizationError):
            await svc.update_setting("locked.key", data=MagicMock(), user_id=1, tenant_id=1)


# ---------------------------------------------------------------------------
# Lookup options
# ---------------------------------------------------------------------------


class TestLookupOptions:
    @pytest.mark.asyncio
    @patch("src.domain.services.form_config_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.form_config_service.track_metric")
    async def test_delete_lookup_option_not_found(self, _metric, _cache):
        svc, db = _make_service()
        db.execute.return_value = _mock_scalar(None)
        with pytest.raises(NotFoundError):
            await svc.delete_lookup_option("category", 999, tenant_id=1)

    @pytest.mark.asyncio
    @patch("src.domain.services.form_config_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.form_config_service.track_metric")
    async def test_update_lookup_option_not_found(self, _metric, _cache):
        svc, db = _make_service()
        db.execute.return_value = _mock_scalar(None)
        with pytest.raises(NotFoundError):
            await svc.update_lookup_option("cat", 999, data=MagicMock(), tenant_id=1)

    @pytest.mark.asyncio
    @patch("src.domain.services.form_config_service.invalidate_tenant_cache", new_callable=AsyncMock)
    @patch("src.domain.services.form_config_service.track_metric")
    async def test_update_lookup_option_happy_path(self, _metric, _cache):
        svc, db = _make_service()
        option = MagicMock(id=1, category="cat")
        db.execute.return_value = _mock_scalar(option)
        db.refresh = AsyncMock()
        result = await svc.update_lookup_option("cat", 1, data=MagicMock(), tenant_id=1)
        assert result is option


# ---------------------------------------------------------------------------
# Step/field CRUD (via _get_or_raise)
# ---------------------------------------------------------------------------


class TestStepAndFieldCRUD:
    @pytest.mark.asyncio
    async def test_delete_step_not_found(self):
        svc, db = _make_service()
        db.execute.return_value = _mock_scalar(None)
        with pytest.raises(NotFoundError):
            await svc.delete_step(999, tenant_id=1)

    @pytest.mark.asyncio
    async def test_delete_field_not_found(self):
        svc, db = _make_service()
        db.execute.return_value = _mock_scalar(None)
        with pytest.raises(NotFoundError):
            await svc.delete_field(999, tenant_id=1)

    @pytest.mark.asyncio
    async def test_delete_step_happy_path(self):
        svc, db = _make_service()
        step = MagicMock(id=1)
        db.execute.return_value = _mock_scalar(step)
        await svc.delete_step(1, tenant_id=1)
        db.delete.assert_called_once_with(step)

    @pytest.mark.asyncio
    async def test_delete_field_happy_path(self):
        svc, db = _make_service()
        field = MagicMock(id=1)
        db.execute.return_value = _mock_scalar(field)
        await svc.delete_field(1, tenant_id=1)
        db.delete.assert_called_once_with(field)
