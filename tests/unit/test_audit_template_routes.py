from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from src.api.routes.audit_templates import update_template
from src.api.schemas.audit import AuditTemplateUpdate
from src.domain.models.audit import AuditTemplate


@pytest.mark.asyncio
async def test_alias_route_uses_canonical_model_for_optimistic_lock() -> None:
    db = SimpleNamespace(get=AsyncMock())
    db.get.return_value = SimpleNamespace(updated_at=datetime(2026, 3, 21, 20, 5, tzinfo=timezone.utc))
    user = SimpleNamespace(id=42, tenant_id=7)
    service_instance = MagicMock()
    service_instance.update_template = AsyncMock()

    with patch("src.api.routes.audit_templates.AuditService", return_value=service_instance):
        with pytest.raises(HTTPException) as exc_info:
            await update_template(
                template_id=99,
                updates=AuditTemplateUpdate(
                    name="Updated Template",
                    expected_updated_at="2026-03-21T20:00:00+00:00",
                ),
                db=db,
                user=user,
            )

    assert exc_info.value.status_code == 409
    assert "modified by another user" in exc_info.value.detail
    assert db.get.await_args.args == (AuditTemplate, 99)
    service_instance.update_template.assert_not_called()
