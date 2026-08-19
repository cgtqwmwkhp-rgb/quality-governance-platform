"""PX-428: ActionCreate accepts owner_email + clause_reference. extra=forbid stays."""

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError as PydanticValidationError

from src.api.routes.actions import ActionCreate, _accepted_clause_reference, _resolve_requested_owner, create_action
from src.domain.exceptions import BadRequestError
from src.domain.models.capa import CAPAAction, CAPASource


def test_action_create_accepts_owner_email_and_clause_reference() -> None:
    body = ActionCreate(
        title="Echo GET",
        description="PX-428 parity",
        source_type="audit_finding",
        source_id=203,
        owner_email="capa.owner@example.com",
        clause_reference="9001-8.5.1",
    )
    assert body.owner_email == "capa.owner@example.com"
    assert body.clause_reference == "9001-8.5.1"


def test_action_create_still_forbids_unknown_fields() -> None:
    with pytest.raises(PydanticValidationError):
        ActionCreate(
            title="Misspelled",
            description="ownerId is not a field",
            source_type="incident",
            source_id=1,
            ownerId=1,  # type: ignore[call-arg]
        )


def test_action_create_clause_reference_max_length() -> None:
    with pytest.raises(PydanticValidationError):
        ActionCreate(
            title="Too long",
            description="max_length 50",
            source_type="audit_finding",
            source_id=1,
            clause_reference="x" * 51,
        )


def test_accepted_clause_reference_rejects_non_capa_source() -> None:
    with pytest.raises(BadRequestError, match="only accepted for CAPA sources"):
        _accepted_clause_reference("9001-8.5.1", "incident")


def test_accepted_clause_reference_strips_blank_to_none() -> None:
    assert _accepted_clause_reference("   ", "incident") is None
    assert _accepted_clause_reference("9001-8.5.1", "audit_finding") == "9001-8.5.1"


@pytest.mark.asyncio
async def test_resolve_requested_owner_owner_email_only() -> None:
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.return_value = SimpleNamespace(id=9)
    db = SimpleNamespace(execute=AsyncMock(return_value=execute_result))

    resolved = await _resolve_requested_owner(
        db,
        owner_id=None,
        assigned_to_email=None,
        owner_email="capa.owner@example.com",
        tenant_id=1,
    )

    assert resolved == 9


@pytest.mark.asyncio
async def test_resolve_requested_owner_three_way_agree() -> None:
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.side_effect = [
        SimpleNamespace(id=9),
        SimpleNamespace(id=9),
        SimpleNamespace(id=9),
    ]
    db = SimpleNamespace(execute=AsyncMock(return_value=execute_result))

    resolved = await _resolve_requested_owner(
        db,
        owner_id=9,
        assigned_to_email="capa.owner@example.com",
        owner_email="capa.owner@example.com",
        tenant_id=1,
    )

    assert resolved == 9
    # Same email is resolved once, then owner_id is confirmed.
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_resolve_requested_owner_three_way_disagree() -> None:
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.side_effect = [
        SimpleNamespace(id=9),
        SimpleNamespace(id=10),
    ]
    db = SimpleNamespace(execute=AsyncMock(return_value=execute_result))

    with pytest.raises(BadRequestError, match="identify different users"):
        await _resolve_requested_owner(
            db,
            owner_id=None,
            assigned_to_email="one@example.com",
            owner_email="two@example.com",
            tenant_id=1,
        )


@pytest.mark.asyncio
async def test_create_action_persists_clause_and_owner_email() -> None:
    finding = SimpleNamespace(
        id=203,
        run_id=84,
        reference_number="FND-2026-0203",
        title="NC",
        clause_ids_json_legacy=None,
    )
    run = SimpleNamespace(id=84, assurance_scheme="ISO 9001:2015", external_reference=None)
    owner = SimpleNamespace(id=9)
    execute_result = MagicMock()
    execute_result.scalar_one_or_none.side_effect = [finding, owner, finding, run]

    db = SimpleNamespace(
        execute=AsyncMock(return_value=execute_result),
        add=MagicMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    async def refresh_side_effect(action: CAPAAction) -> None:
        action.id = 75
        action.created_at = datetime(2026, 8, 19, 6, 0, tzinfo=timezone.utc)

    db.refresh.side_effect = refresh_side_effect
    current_user = SimpleNamespace(id=7, tenant_id=1)

    with (
        patch(
            "src.domain.services.reference_number.ReferenceNumberService.generate",
            new=AsyncMock(return_value="CAPA-2026-0011"),
        ),
        patch("src.api.routes.actions.record_audit_event", new=AsyncMock()),
        patch("src.api.routes.actions.notify_action_assignment", new=AsyncMock()),
        patch("src.api.routes.actions.record_action_assigned_audit", new=AsyncMock()),
    ):
        response = await create_action(
            ActionCreate(
                title="Raise from GET echo",
                description="owner_email + clause_reference",
                source_type="audit_finding",
                source_id=203,
                owner_email="capa.owner@example.com",
                clause_reference="9001-8.5.1",
            ),
            db=db,
            current_user=current_user,
        )

    created = db.add.call_args.args[0]
    assert isinstance(created, CAPAAction)
    assert created.source_type == CAPASource.AUDIT_FINDING
    assert created.clause_reference == "9001-8.5.1"
    assert created.assigned_to_id == 9
    assert response.clause_reference == "9001-8.5.1"
    assert response.owner_id == 9
    # CAPA create response hydrates roster-only emails; assigned_to_id is the SoR.
