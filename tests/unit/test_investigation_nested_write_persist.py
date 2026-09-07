"""The investigation persist paths store nested sections, not flat keys only (INV-C4).

The detail page (and any older client) sends `data.findings`. The template closure walk and the
pack read `data.sections` only, so the merge has to run on the way in — on PATCH and on autosave.
These tests drive the route functions directly, the same way the PX-141 revision-event tests do.
"""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.api.routes.investigations import autosave_investigation, update_investigation
from src.api.schemas.investigation import InvestigationRunUpdate
from src.domain.models.investigation import InvestigationStatus
from src.domain.services.investigation_service import InvestigationService

FINDINGS_SECTION = "section_3_investigation_findings"
ROOT_CAUSE_SECTION = "section_4_root_cause"


def _investigation(**overrides):
    base = dict(
        id=42,
        tenant_id=7,
        template_id=1,
        version=3,
        status=InvestigationStatus.IN_PROGRESS,
        title="Fork lift near miss",
        description="Original description",
        data={},
        reference_number="INV-42",
        started_at=datetime(2026, 7, 1),
        completed_at=None,
        closed_at=None,
        assigned_entity_type="incident",
        assigned_entity_id=99,
        assigned_entity_reference=None,
        created_at=datetime(2026, 7, 1),
        updated_at=datetime(2026, 7, 1),
        updated_by_id=1,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _db(investigation):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none = MagicMock(return_value=investigation)
    db.execute = AsyncMock(return_value=result)
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


async def _patch(investigation, payload):
    db = _db(investigation)
    with (
        patch(
            "src.api.routes.investigations._ensure_investigation_ready_for_status",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "src.domain.services.investigation_service.resolve_assigned_entity_reference",
            new=AsyncMock(return_value="INC-99"),
        ),
        patch(
            "src.domain.services.lessons_learnt_promote.promote_lessons_to_case",
            new=AsyncMock(return_value=False),
        ),
        patch.object(InvestigationService, "create_revision_event", new=AsyncMock()),
    ):
        await update_investigation(
            request=MagicMock(headers={"X-Request-ID": "req-123"}),
            investigation_id=42,
            investigation_data=InvestigationRunUpdate(**payload),
            db=db,
            current_user=SimpleNamespace(id=11, tenant_id=7),
        )
    return investigation


@pytest.mark.asyncio
async def test_patch_with_flat_keys_stores_the_nested_sections_too():
    investigation = await _patch(
        _investigation(),
        {"data": {"findings": "guard was removed", "why_1": "the interlock was bypassed"}},
    )

    assert investigation.data["findings"] == "guard was removed"
    assert investigation.data["sections"][FINDINGS_SECTION]["findings"] == "guard was removed"
    assert investigation.data["sections"][ROOT_CAUSE_SECTION]["why_1"] == "the interlock was bypassed"
    # Default template (id=1) names its root-cause section `rca`; the closure gate reads that key.
    assert investigation.data["sections"]["rca"]["why_1"] == "the interlock was bypassed"


@pytest.mark.asyncio
async def test_patch_copies_a_nested_finding_onto_the_flat_key_the_summary_gate_reads():
    investigation = await _patch(
        _investigation(),
        {"data": {"sections": {FINDINGS_SECTION: {"findings": "nested finding", "conclusion": "nested conclusion"}}}},
    )

    assert investigation.data["findings"] == "nested finding"
    assert investigation.data["conclusion"] == "nested conclusion"


@pytest.mark.asyncio
async def test_patch_without_a_data_blob_leaves_the_stored_json_alone():
    investigation = await _patch(_investigation(data={"findings": "already here"}), {"title": "Fork lift collision"})

    assert investigation.data == {"findings": "already here"}


@pytest.mark.asyncio
async def test_autosave_stores_the_nested_sections_and_bumps_the_version():
    investigation = _investigation()
    db = _db(investigation)

    with patch.object(InvestigationService, "create_revision_event", new=AsyncMock()) as spy:
        await autosave_investigation(
            investigation_id=42,
            data={"conclusion": "unsafe system of work"},
            version=3,
            db=db,
            current_user=SimpleNamespace(id=11, tenant_id=7),
        )

    assert investigation.data["conclusion"] == "unsafe system of work"
    assert investigation.data["sections"][FINDINGS_SECTION]["conclusion"] == "unsafe system of work"
    assert investigation.version == 4
    # The revision event records what was stored, not the pre-merge payload.
    assert spy.await_args.kwargs["new_value"]["sections"][FINDINGS_SECTION]["conclusion"] == "unsafe system of work"
