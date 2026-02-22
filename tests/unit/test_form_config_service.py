"""Unit tests for FormConfigService."""

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Break the circular import chain:
#   form_config_service -> src.api.schemas.error_codes -> src.api -> src.api.routes
#   -> routes/form_config -> form_config_service (cycle!)
# We stub the triggering module before importing the service under test.
_error_codes_stub = ModuleType("src.api.schemas.error_codes")
_error_codes_stub.ErrorCode = type(
    "ErrorCode",
    (),
    {  # type: ignore[attr-defined]
        "DUPLICATE_ENTITY": "DUPLICATE_ENTITY",
        "ENTITY_NOT_FOUND": "ENTITY_NOT_FOUND",
        "PERMISSION_DENIED": "PERMISSION_DENIED",
    },
)()

_patches = {
    "src.api.schemas.error_codes": _error_codes_stub,
    "src.api.utils.update": MagicMock(apply_updates=lambda obj, data, **kw: {}),
    "src.domain.services.audit_service": MagicMock(record_audit_event=AsyncMock()),
    "src.infrastructure.cache.redis_cache": MagicMock(invalidate_tenant_cache=AsyncMock()),
    "src.infrastructure.monitoring.azure_monitor": MagicMock(track_metric=MagicMock()),
}

# Only set if not yet loaded to avoid clobbering live modules from other tests
for _k, _v in _patches.items():
    if _k not in sys.modules:
        sys.modules[_k] = _v

from src.domain.exceptions import NotFoundError  # noqa: E402
from src.domain.services.form_config_service import FormConfigService  # noqa: E402


def _make_mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.refresh = AsyncMock()
    db.add = MagicMock()
    return db


class TestListTemplates:
    @pytest.mark.asyncio
    async def test_list_templates_returns_paginated(self):
        db = _make_mock_db()

        templates = [MagicMock(id=i, name=f"Form {i}") for i in range(3)]

        count_result = MagicMock()
        count_result.scalar_one.return_value = 3

        items_result = MagicMock()
        items_result.scalars.return_value.all.return_value = templates

        db.execute = AsyncMock(side_effect=[count_result, items_result])

        svc = FormConfigService(db)
        result = await svc.list_templates(tenant_id=1, page=1, page_size=10)

        assert result["total"] == 3
        assert result["page"] == 1
        assert result["page_size"] == 10
        assert len(result["items"]) == 3
        assert result["pages"] == 1


class TestCreateTemplate:
    @pytest.mark.asyncio
    async def test_create_template_success(self):
        db = _make_mock_db()

        no_existing = MagicMock()
        no_existing.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=no_existing)

        data = MagicMock()
        data.name = "New Template"
        data.slug = "new-template"
        data.description = "A new form template"
        data.form_type = "complaint"
        data.icon = None
        data.color = None
        data.allow_drafts = True
        data.allow_attachments = True
        data.require_signature = False
        data.auto_assign_reference = True
        data.reference_prefix = "CMP"
        data.notify_on_submit = False
        data.notification_emails = []
        data.workflow_id = None
        data.steps = None

        svc = FormConfigService(db)

        with (
            patch("src.domain.services.form_config_service.record_audit_event", new_callable=AsyncMock),
            patch("src.domain.services.form_config_service.track_metric"),
        ):
            await svc.create_template(data=data, user_id=1, request_id="req-1")

        db.add.assert_called_once()
        db.commit.assert_awaited_once()
        db.refresh.assert_awaited_once()


class TestGetTemplate:
    @pytest.mark.asyncio
    async def test_get_template_not_found_raises(self):
        db = _make_mock_db()

        result_mock = MagicMock()
        result_mock.scalar_one_or_none.return_value = None
        db.execute = AsyncMock(return_value=result_mock)

        svc = FormConfigService(db)
        with pytest.raises(NotFoundError):
            await svc.get_template(999, tenant_id=1)
