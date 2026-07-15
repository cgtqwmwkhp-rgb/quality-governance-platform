"""Unit tests for Actions list Mine / Overdue server-side filter helpers."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from src.api.routes._action_unified import STORAGE_CAPA_ITEM, action_key_for
from src.api.routes.actions import (
    _CAPA_ITEM_DONE_STATUSES,
    _OPERATIONAL_DONE_STATUSES,
    _apply_capa_item_status_filter,
    _apply_owner_and_overdue_filters,
    _capa_item_to_response,
    _resolve_assigned_to_user_id,
)
from src.domain.exceptions import ValidationError
from src.domain.models.capa import CAPAAction, CAPAStatus
from src.domain.models.incident import IncidentAction
from src.domain.models.rca_tools import CAPAItem


def test_resolve_assigned_to_me_and_numeric() -> None:
    user = SimpleNamespace(id=42)
    assert _resolve_assigned_to_user_id("me", user) == 42
    assert _resolve_assigned_to_user_id("ME", user) == 42
    assert _resolve_assigned_to_user_id(" 7 ", user) == 7
    assert _resolve_assigned_to_user_id(None, user) is None
    assert _resolve_assigned_to_user_id("", user) is None
    assert _resolve_assigned_to_user_id("   ", user) is None


def test_resolve_assigned_to_rejects_invalid() -> None:
    user = SimpleNamespace(id=1)
    with pytest.raises(ValidationError, match="assigned_to"):
        _resolve_assigned_to_user_id("abc", user)
    with pytest.raises(ValidationError, match="assigned_to"):
        _resolve_assigned_to_user_id("0", user)
    with pytest.raises(ValidationError, match="assigned_to"):
        _resolve_assigned_to_user_id("-3", user)


def test_apply_owner_filter_compiles_for_incident() -> None:
    q = select(IncidentAction)
    filtered = _apply_owner_and_overdue_filters(
        q,
        owner_col=IncidentAction.owner_id,
        due_col=IncidentAction.due_date,
        status_col=IncidentAction.status,
        assigned_to_id=42,
        overdue=False,
        done_statuses=_OPERATIONAL_DONE_STATUSES,
    )
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True}))
    assert "owner_id" in sql.lower() or "owner_id" in sql
    assert "42" in sql


def test_apply_overdue_filter_excludes_done_and_requires_past_due() -> None:
    q = select(IncidentAction)
    filtered = _apply_owner_and_overdue_filters(
        q,
        owner_col=IncidentAction.owner_id,
        due_col=IncidentAction.due_date,
        status_col=IncidentAction.status,
        assigned_to_id=None,
        overdue=True,
        done_statuses=_OPERATIONAL_DONE_STATUSES,
    )
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True})).lower()
    assert "due_date" in sql
    assert "completed" in sql
    assert "cancelled" in sql
    assert "verified" in sql


def test_apply_mine_and_overdue_together_for_capa() -> None:
    q = select(CAPAAction)
    filtered = _apply_owner_and_overdue_filters(
        q,
        owner_col=CAPAAction.assigned_to_id,
        due_col=CAPAAction.due_date,
        status_col=CAPAAction.status,
        assigned_to_id=9,
        overdue=True,
        done_statuses=(CAPAStatus.CLOSED,),
    )
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True})).lower()
    assert "assigned_to_id" in sql
    assert "9" in sql
    assert "due_date" in sql
    assert "closed" in sql


def test_capa_item_to_response_uses_honest_fields() -> None:
    item = SimpleNamespace(
        id=7,
        title="Replace guard",
        description="Install missing guard on press",
        action_type="corrective",
        priority="high",
        status="open",
        investigation_id=99,
        assigned_to_id=42,
        due_date=None,
        completed_at=None,
        verification_notes=None,
        created_at=None,
    )
    response = _capa_item_to_response(item)  # type: ignore[arg-type]
    assert response.action_key == action_key_for(STORAGE_CAPA_ITEM, 7)
    assert response.title == "Replace guard"
    assert response.description == "Install missing guard on press"
    assert response.source_type == "investigation"
    assert response.source_id == 99
    assert response.owner_id == 42


def test_apply_capa_item_status_filter_maps_completed() -> None:
    q = select(CAPAItem)
    filtered = _apply_capa_item_status_filter(q, "completed")
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True})).lower()
    for done_status in _CAPA_ITEM_DONE_STATUSES:
        assert done_status in sql


def test_apply_mine_and_overdue_together_for_capa_item() -> None:
    q = select(CAPAItem)
    filtered = _apply_owner_and_overdue_filters(
        q,
        owner_col=CAPAItem.assigned_to_id,
        due_col=CAPAItem.due_date,
        status_col=CAPAItem.status,
        assigned_to_id=9,
        overdue=True,
        done_statuses=_CAPA_ITEM_DONE_STATUSES,
    )
    sql = str(filtered.compile(compile_kwargs={"literal_binds": True})).lower()
    assert "assigned_to_id" in sql
    assert "9" in sql
    assert "due_date" in sql
    assert "closed" in sql
