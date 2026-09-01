"""CB-PR2: competence change requests — routing, one-open cell, auto-close."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.api.routes import workforce_competence_board as board_routes
from src.core.config import settings
from src.domain.exceptions import BadRequestError
from src.domain.services.competence_change_request_service import (
    PLANT_MAILBOX_DEFAULT,
    STATUTORY_MAILBOX_UNSET,
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


@pytest.mark.asyncio
async def test_change_requests_404_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", False)
    with pytest.raises(HTTPException) as exc_info:
        await board_routes.require_competence_board_enabled()
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_atlas_board_still_422(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    with pytest.raises(HTTPException) as exc_info:
        await board_routes.get_competence_board(
            db=MagicMock(),
            current_user=SimpleNamespace(tenant_id=1),
            family="atlas",
        )
    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == board_routes.ATLAS_NOT_SHIPPED
