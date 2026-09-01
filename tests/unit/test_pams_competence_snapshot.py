"""CB-PR1: PAMS competence snapshot mapping, join, stale banner, flag, beat."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.routes import workforce_competence_board as board_routes
from src.core.config import settings
from src.domain.features.catalogue import CLIENT_FEATURES_BY_KEY
from src.domain.models.engineer import Engineer
from src.domain.services.pams_competence_snapshot_service import (
    STALE_AFTER,
    map_competence_row,
    resolve_engineer_id,
    snapshot_stale_reason,
)
from src.infrastructure.tasks.celery_app import CELERY_TASK_MODULES, celery_app

MODULE_PATH = "src.infrastructure.tasks.pams_sync_tasks"
TASK_NAME = f"{MODULE_PATH}.sync_pams_competence"


def test_competence_board_flag_pre_registered_default_off():
    feature = CLIENT_FEATURES_BY_KEY["competence_board"]
    assert feature.settings_attr == "competence_board_enabled"
    assert feature.required_permission == "engineer:update"
    assert settings.competence_board_enabled is False


def test_map_competence_row_reads_view_columns():
    mapped = map_competence_row(
        {
            "technician_id": 158,
            "EngineerName": "Cameron Alexander-Forde",
            "Email": "cameron@example.com",
            "Depot": "SS11",
            "characteristic": "Trailer",
            "thorough_exam": 1,
        }
    )
    assert mapped is not None
    assert mapped.pams_technician_id == 158
    assert mapped.engineer_name == "Cameron Alexander-Forde"
    assert mapped.email == "cameron@example.com"
    assert mapped.depot == "SS11"
    assert mapped.characteristic_key == "Trailer"
    assert mapped.thorough_exam is True


def test_map_competence_row_skips_empty_characteristic():
    assert map_competence_row({"technician_id": 1, "characteristic": ""}) is None
    assert map_competence_row({"technician_id": 1}) is None


def test_map_competence_row_does_not_treat_generic_id_as_technician():
    mapped = map_competence_row({"id": 99, "characteristic": "Van"})
    assert mapped is not None
    assert mapped.pams_technician_id is None
    assert mapped.characteristic_key == "Van"


def test_resolve_engineer_id_pams_id_then_email_never_name():
    by_pams = {
        10: Engineer(id=1, tenant_id=1, pams_technician_id=10, display_name="Alex"),
    }
    by_email = {
        "sam@example.com": Engineer(id=2, tenant_id=1, display_name="Sam"),
    }
    from src.domain.services.pams_competence_snapshot_service import MappedCompetenceRow

    by_id = MappedCompetenceRow(
        pams_technician_id=10,
        engineer_name="Wrong Name",
        email="other@example.com",
        depot=None,
        characteristic_key="Van",
        thorough_exam=None,
        raw_data={},
    )
    assert resolve_engineer_id(by_id, by_pams_id=by_pams, by_email=by_email) == 1

    by_mail = MappedCompetenceRow(
        pams_technician_id=99,
        engineer_name="Sam",
        email="SAM@example.com",
        depot=None,
        characteristic_key="Van",
        thorough_exam=None,
        raw_data={},
    )
    assert resolve_engineer_id(by_mail, by_pams_id=by_pams, by_email=by_email) == 2

    name_only = MappedCompetenceRow(
        pams_technician_id=None,
        engineer_name="Alex",
        email=None,
        depot=None,
        characteristic_key="Van",
        thorough_exam=None,
        raw_data={},
    )
    assert resolve_engineer_id(name_only, by_pams_id=by_pams, by_email=by_email) is None


def test_snapshot_stale_after_25_hours():
    now = datetime(2026, 9, 1, 14, 0, 0)
    fresh = now - timedelta(hours=24)
    stale = now - STALE_AFTER - timedelta(minutes=1)
    assert snapshot_stale_reason(fresh, now=now) is None
    reason = snapshot_stale_reason(stale, now=now)
    assert reason is not None
    assert "stale" in reason.lower()
    assert snapshot_stale_reason(None, now=now) is not None


@pytest.mark.asyncio
async def test_flag_off_returns_404(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", False)
    with pytest.raises(HTTPException) as exc_info:
        await board_routes.require_competence_board_enabled()
    assert exc_info.value.status_code == 404
    assert exc_info.value.detail == board_routes.DISABLED_DETAIL


@pytest.mark.asyncio
async def test_flag_on_allows_dependency(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)
    await board_routes.require_competence_board_enabled()


def test_competence_task_is_imported_and_scheduled_once():
    assert MODULE_PATH in CELERY_TASK_MODULES
    import src.infrastructure.tasks.pams_sync_tasks  # noqa: F401

    assert TASK_NAME in celery_app.tasks
    scheduled = [name for name, entry in celery_app.conf.beat_schedule.items() if entry.get("task") == TASK_NAME]
    assert scheduled == ["sync-pams-competence"]
