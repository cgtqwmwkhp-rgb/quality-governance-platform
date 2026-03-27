from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from src.api.routes.actions import ActionCreate, create_action
from src.domain.models.capa import CAPAAction, CAPAPriority, CAPAStatus, CAPASource, CAPAType


@pytest.mark.asyncio
async def test_create_action_supports_audit_finding_source() -> None:
    finding = SimpleNamespace(
        id=55,
        run_id=12,
        reference_number="AF-2026-0055",
        title="Missing evidence",
        clause_ids_json_legacy=["7.5"],
    )
    run = SimpleNamespace(id=12, assurance_scheme="ISO 9001:2015", external_reference="7.5")
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.side_effect = [finding, run]

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


def test_capa_enums_bind_lowercase_values_for_postgres() -> None:
    dialect = postgresql.dialect()

    source_processor = CAPAAction.__table__.c.source_type.type.bind_processor(dialect)
    status_processor = CAPAAction.__table__.c.status.type.bind_processor(dialect)
    priority_processor = CAPAAction.__table__.c.priority.type.bind_processor(dialect)
    type_processor = CAPAAction.__table__.c.capa_type.type.bind_processor(dialect)

    assert source_processor is not None
    assert status_processor is not None
    assert priority_processor is not None
    assert type_processor is not None

    assert source_processor(CAPASource.AUDIT_FINDING) == "audit_finding"
    assert status_processor(CAPAStatus.OPEN) == "open"
    assert priority_processor(CAPAPriority.HIGH) == "high"
    assert type_processor(CAPAType.CORRECTIVE) == "corrective"
