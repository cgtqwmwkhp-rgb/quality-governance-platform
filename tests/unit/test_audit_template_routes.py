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


@pytest.mark.asyncio
async def test_audits_patch_remaps_tags_to_tags_json_not_unknown_attr() -> None:
    """N-BUILD-1: PATCH /templates/{id} must stamp tags_json, not setattr tags."""
    from src.api.routes.audits import update_template as audits_update_template

    template = SimpleNamespace(
        id=1,
        tenant_id=7,
        is_published=False,
        version=1,
        tags_json=["builder_brief:abc", "source_case:complaint:9"],
        name="Depot",
    )
    result = MagicMock()
    result.scalar_one_or_none.return_value = template
    db = SimpleNamespace(
        execute=AsyncMock(return_value=result),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )
    user = SimpleNamespace(id=42, tenant_id=7, is_superuser=False)
    decoded = SimpleNamespace(name="Depot", description=None, category=None)

    with patch(
        "src.api.routes.audits.AuditTemplateResponse.model_validate",
        return_value=decoded,
    ), patch(
        "src.api.routes.audits._decode_template_response_entities",
        side_effect=lambda response: response,
    ):
        await audits_update_template(
            template_id=1,
            template_data=AuditTemplateUpdate(
                tags=["builder_brief:abc", "source_case:complaint:9", "instrument:skills"],
            ),
            db=db,
            current_user=user,
        )

    assert template.tags_json == [
        "builder_brief:abc",
        "source_case:complaint:9",
        "instrument:skills",
    ]
    assert not hasattr(template, "tags")

