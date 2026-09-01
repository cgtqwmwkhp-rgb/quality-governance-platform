"""CB-PR2: competence change requests — routing, one-open cell, auto-close."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException, Response
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.api.routes import workforce_competence_board as board_routes
from src.core.config import settings
from src.domain.exceptions import BadRequestError
from src.domain.models.competence_change_request import CompetenceChangeRequest
from src.domain.services import competence_change_request_service as change_service
from src.domain.services.competence_change_request_service import (
    PLANT_MAILBOX_DEFAULT,
    STATUTORY_MAILBOX_UNSET,
    close_pams_requests_from_snapshot,
    close_pams_requests_from_snapshot_async,
    mailbox_for,
    should_close_against_source,
)


def test_plant_mailbox_defaults_to_it_admin():
    assert mailbox_for("pams") == PLANT_MAILBOX_DEFAULT


def test_statutory_mailbox_unset_is_honest(monkeypatch):
    monkeypatch.setattr(settings, "competence_statutory_change_mailbox", "")
    with pytest.raises(BadRequestError) as exc_info:
        mailbox_for("atlas")
    assert STATUTORY_MAILBOX_UNSET in str(exc_info.value)


def test_statutory_mailbox_uses_hr_advisor_setting(monkeypatch):
    monkeypatch.setattr(settings, "competence_statutory_change_mailbox", "hr@plantexpand.com")
    assert mailbox_for("atlas") == "hr@plantexpand.com"


def test_issue_closes_when_source_has_the_cell():
    present = {(1, "Trailer")}
    assert should_close_against_source(action="issue", pair=(1, "Trailer"), present=present)
    assert not should_close_against_source(action="issue", pair=(1, "Van"), present=present)


def test_revoke_closes_when_source_no_longer_has_the_cell():
    present = {(1, "Trailer")}
    assert should_close_against_source(action="revoke", pair=(1, "Van"), present=present)
    assert not should_close_against_source(action="revoke", pair=(1, "Trailer"), present=present)


def test_missing_snapshot_does_not_close_revoke_requests():
    db = MagicMock()
    db.get.return_value = None

    assert close_pams_requests_from_snapshot(db, tenant_id=7) == 0
    db.scalars.assert_not_called()


@pytest.mark.asyncio
async def test_missing_snapshot_does_not_close_revoke_requests_async():
    db = SimpleNamespace(get=AsyncMock(return_value=None), scalars=AsyncMock())

    assert await close_pams_requests_from_snapshot_async(db, tenant_id=7) == 0
    db.scalars.assert_not_awaited()


def test_sqlite_allows_new_open_request_after_closed_request():
    engine = create_engine("sqlite:///:memory:")
    CompetenceChangeRequest.__table__.create(engine)
    common = {
        "tenant_id": 1,
        "family": "pams",
        "engineer_id": 2,
        "characteristic_key": "Trailer",
        "action": "issue",
        "routed_to_email": PLANT_MAILBOX_DEFAULT,
    }

    with Session(engine) as db:
        db.add(CompetenceChangeRequest(**common, status="closed_observed"))
        db.commit()
        db.add(CompetenceChangeRequest(**common, status="open"))
        db.commit()
        db.add(CompetenceChangeRequest(**common, status="open"))
        with pytest.raises(IntegrityError):
            db.commit()


@pytest.mark.asyncio
async def test_change_request_email_is_queued_after_row_commit(monkeypatch):
    events: list[str] = []
    row = SimpleNamespace(
        id=3,
        family="pams",
        engineer_id=2,
        characteristic_key="Trailer",
        action="issue",
        status="open",
        routed_to_email=PLANT_MAILBOX_DEFAULT,
        email_sent=False,
        notes=None,
        created_at=datetime(2026, 9, 1, 12, 0),
        closed_at=None,
        close_reason=None,
    )
    db = SimpleNamespace(
        commit=AsyncMock(side_effect=lambda: events.append("commit")),
        refresh=AsyncMock(side_effect=lambda _: events.append("refresh")),
    )
    monkeypatch.setattr(
        change_service,
        "create_change_request_async",
        AsyncMock(return_value=(row, True)),
    )

    def _send_email(created_row):
        events.append("email")
        created_row.email_sent = True

    monkeypatch.setattr(change_service, "try_send_change_request_email", _send_email)
    response = Response()

    result = await board_routes.create_competence_change_request(
        payload=board_routes.CompetenceChangeRequestCreate(
            family="pams",
            engineer_id=2,
            characteristic_key="Trailer",
            action="issue",
        ),
        db=db,
        current_user=SimpleNamespace(id=9, tenant_id=1),
        response=response,
    )

    assert events == ["commit", "email", "commit", "refresh"]
    assert result.email_sent is True


@pytest.mark.asyncio
async def test_change_requests_404_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", False)
    with pytest.raises(HTTPException) as exc_info:
        await board_routes.require_competence_board_enabled()
    assert exc_info.value.status_code == 404
