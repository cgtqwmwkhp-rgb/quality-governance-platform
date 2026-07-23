"""RIDDOR prepare must persist an honest draft pack (never looks HSE-filed)."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.domain.exceptions import NotFoundError
from src.domain.models.compliance_automation import RIDDORSubmission
from src.domain.models.incident import Incident, IncidentSeverity, IncidentType
from src.domain.services.compliance_automation_service import RIDDOR_STATUS_DRAFT_PACK, ComplianceAutomationService


def _incident(incident_id: int = 42) -> Incident:
    incident = Incident(
        tenant_id=1,
        title="Fracture on site",
        description="Worker fell from ladder",
        incident_type=IncidentType.INJURY,
        severity=IncidentSeverity.HIGH,
        location="Yard A",
        people_involved="Alex Example",
        immediate_actions="First aid given",
        reporter_name="Site Supervisor",
        reporter_email="supervisor@example.com",
        riddor_classification="specified_injury",
    )
    incident.id = incident_id
    incident.reference_number = "INC-0042"
    incident.incident_date = datetime(2026, 7, 1, 9, 30, tzinfo=timezone.utc)
    incident.body_parts = ["Hands", "Arms"]
    incident.days_lost = 9
    incident.is_lti = True
    return incident


def _db_for_prepare(*, incident: Incident | None, existing: RIDDORSubmission | None = None):
    incident_result = MagicMock()
    incident_result.scalar_one_or_none.return_value = incident

    existing_result = MagicMock()
    existing_result.scalar_one_or_none.return_value = existing

    db = SimpleNamespace(
        execute=AsyncMock(side_effect=[incident_result, existing_result]),
        add=MagicMock(),
        flush=AsyncMock(),
    )

    async def flush_side_effect():
        for call in db.add.call_args_list:
            obj = call.args[0]
            if isinstance(obj, RIDDORSubmission) and getattr(obj, "id", None) is None:
                obj.id = 77

    db.flush.side_effect = flush_side_effect
    return db


@pytest.mark.asyncio
async def test_prepare_riddor_persists_draft_pack_with_honest_status():
    incident = _incident()
    db = _db_for_prepare(incident=incident)
    service = ComplianceAutomationService(db=db)  # type: ignore[arg-type]

    result = await service.prepare_riddor_submission(
        tenant_id=1,
        incident_id=42,
        riddor_type="specified_injury",
    )

    assert result["persisted"] is True
    assert result["status"] == RIDDOR_STATUS_DRAFT_PACK
    assert result["submission_status"] == RIDDOR_STATUS_DRAFT_PACK
    assert result["id"] == 77
    assert result["incident_id"] == 42
    assert result["incident_reference"] == "INC-0042"
    assert result["gateway"] == "not_connected"
    assert "HSE portal" in result["status_label"]
    assert result["submission_data"]["location"] == "Yard A"
    assert result["submission_data"]["date_of_incident"] == "2026-07-01"
    assert result["submission_data"]["injury_details"]["body_part"] == "Hands, Arms"
    assert result["submission_data"]["injury_details"]["days_lost"] == 9
    assert result["submission_data"]["injury_details"]["is_lti"] is True
    db.add.assert_called_once()
    added = db.add.call_args.args[0]
    assert isinstance(added, RIDDORSubmission)
    assert added.submission_status == RIDDOR_STATUS_DRAFT_PACK


@pytest.mark.asyncio
async def test_prepare_riddor_missing_incident_raises():
    db = SimpleNamespace(
        execute=AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None))),
        add=MagicMock(),
        flush=AsyncMock(),
    )
    service = ComplianceAutomationService(db=db)  # type: ignore[arg-type]

    with pytest.raises(NotFoundError):
        await service.prepare_riddor_submission(
            tenant_id=1,
            incident_id=999,
            riddor_type="death",
        )


@pytest.mark.asyncio
async def test_list_riddor_submissions_returns_persisted_rows():
    pack = RIDDORSubmission(
        tenant_id=1,
        incident_id=42,
        riddor_type="specified_injury",
        submission_status=RIDDOR_STATUS_DRAFT_PACK,
        submission_data={"report_type": "specified_injury"},
        deadline=datetime(2026, 7, 20),
        is_overdue=False,
    )
    pack.id = 7
    pack.created_at = datetime(2026, 7, 10)

    result_rows = MagicMock()
    result_rows.all.return_value = [(pack, "INC-0042")]
    db = SimpleNamespace(execute=AsyncMock(return_value=result_rows))
    service = ComplianceAutomationService(db=db)  # type: ignore[arg-type]

    listed = await service.list_riddor_submissions(tenant_id=1)
    assert listed["total"] == 1
    assert listed["submissions"][0]["id"] == 7
    assert listed["submissions"][0]["persisted"] is True
    assert listed["submissions"][0]["incident_reference"] == "INC-0042"
