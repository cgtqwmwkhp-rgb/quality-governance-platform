"""Unit tests for Actions list Mine / Overdue server-side filter helpers."""

from types import SimpleNamespace

import pytest
from sqlalchemy import select

from src.api.routes.actions import (
    _OPERATIONAL_DONE_STATUSES,
    _apply_owner_and_overdue_filters,
    _resolve_assigned_to_user_id,
)
from src.domain.exceptions import ValidationError
from src.domain.models.capa import CAPAAction, CAPAStatus
from src.domain.models.incident import IncidentAction


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
