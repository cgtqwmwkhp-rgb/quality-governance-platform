from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.actions import ActionCreate, create_action
from src.domain.models.capa import CAPAAction, CAPASource


@pytest.mark.asyncio
async def test_create_action_supports_audit_finding_source() -> None:
    finding = SimpleNamespace(id=55)
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = finding

    db = SimpleNamespace(
        execute=AsyncMock(return_value=execute_result),
        add=MagicMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    async def refresh_side_effect(action: CAPAAction) -> None:
        action.id = 101
        action.created_at = datetime(2026, 3, 21, 21, 0, tzinfo=timezone.utc)

    db.refresh.side_effect = refresh_side_effect
    current_user = SimpleNamespace(id=7)

    with patch(
        "src.domain.services.reference_number.ReferenceNumberService.generate",
        new=AsyncMock(return_value="CAPA-2026-0001"),
    ):
        response = await create_action(
            ActionCreate(
                title="Raise corrective action",
                description="Follow up the failed audit control",
                source_type="audit_finding",
                source_id=55,
                priority="high",
            ),
            db=db,
            current_user=current_user,
        )

    created_action = db.add.call_args.args[0]
    assert isinstance(created_action, CAPAAction)
    assert created_action.source_type == CAPASource.AUDIT_FINDING
    assert created_action.source_id == 55
    assert response.reference_number == "CAPA-2026-0001"
    assert response.source_type == "audit_finding"
    assert response.source_id == 55
    assert response.priority == "high"
