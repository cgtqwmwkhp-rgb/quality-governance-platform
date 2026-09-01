"""CB-PR3: Atlas family board + person union. No new logins. No name join."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException

from src.api.routes import workforce_competence_board as board_routes
from src.core.config import settings
from src.domain.services.atlas_competence_board_service import (
    DUPLICATE_BANNER,
    NO_IMPORT_BANNER,
    assemble_atlas_board,
    empty_atlas_board,
)


def _import(**kwargs):
    data = {"id": 9, "status": "completed", "filename": "atlas.xlsx", "created_at": None}
    data.update(kwargs)
    return SimpleNamespace(**data)


def _person(*, pid: int, name: str, engineer_id=None, department=None):
    return SimpleNamespace(id=pid, atlas_name=name, engineer_id=engineer_id, department=department)


def _course(*, cid: int, key: str, label: str | None = None):
    return SimpleNamespace(id=cid, course_key=key, display_name=label or key)


def _cell(*, person_id: int, course_id: int, passed_on=None, expires_on=None):
    return SimpleNamespace(
        person_id=person_id,
        course_id=course_id,
        passed_on=passed_on,
        expires_on=expires_on,
    )


def test_empty_import_is_banner_not_grey_cells():
    view = empty_atlas_board()
    assert view.people == []
    assert view.columns == []
    assert view.banner == NO_IMPORT_BANNER
    assert view.snapshot.stale is True


def test_person_union_includes_unmapped_office_without_creating_a_user():
    office = _person(pid=1, name="Pat Office", department="Office")
    engineer = _person(pid=2, name="Cam Engineer", engineer_id=44, department="Engineer")
    view = assemble_atlas_board(
        import_row=_import(),
        people=[office, engineer],
        courses=[_course(cid=1, key="first-aid", label="First Aid")],
        cells=[
            _cell(person_id=1, course_id=1, passed_on=date(2026, 1, 10), expires_on=date(2029, 1, 10)),
            _cell(person_id=2, course_id=1, passed_on=date(2025, 6, 1)),
        ],
        engineers={44: SimpleNamespace(id=44, display_name="Cameron")},
    )
    assert {p.atlas_person_id for p in view.people} == {1, 2}
    unmapped = next(p for p in view.people if p.atlas_person_id == 1)
    mapped = next(p for p in view.people if p.atlas_person_id == 2)
    assert unmapped.mapped is False
    assert unmapped.engineer_id is None
    assert unmapped.display_name == "Pat Office"
    assert mapped.mapped is True
    assert mapped.display_name == "Cameron"
    assert view.unmapped_count == 1
    assert "first-aid" in unmapped.cells
    assert unmapped.cells["first-aid"].issued is True
    assert unmapped.cells["first-aid"].passed_on == date(2026, 1, 10)


def test_same_display_name_stays_two_rows():
    """Name is not a join key. Two Atlas people named Sam stay two humans."""
    a = _person(pid=10, name="Sam")
    b = _person(pid=11, name="Sam")
    view = assemble_atlas_board(
        import_row=_import(),
        people=[a, b],
        courses=[],
        cells=[],
        engineers={},
    )
    assert len(view.people) == 2
    assert {p.atlas_person_id for p in view.people} == {10, 11}
    assert view.duplicate_engineer_ids == ()


def test_duplicate_engineer_id_is_not_merged():
    a = _person(pid=1, name="Alex Atlas", engineer_id=7)
    b = _person(pid=2, name="Alex Duplicate", engineer_id=7)
    view = assemble_atlas_board(
        import_row=_import(),
        people=[a, b],
        courses=[],
        cells=[],
        engineers={7: SimpleNamespace(id=7, display_name="Alex")},
    )
    assert len(view.people) == 2
    assert view.duplicate_engineer_ids == (7,)
    assert view.banner == DUPLICATE_BANNER.format(count=1)


def test_empty_cells_are_absent_not_not_assessed():
    person = _person(pid=1, name="Pat")
    view = assemble_atlas_board(
        import_row=_import(),
        people=[person],
        courses=[_course(cid=1, key="first-aid"), _course(cid=2, key="fire-marshal")],
        cells=[
            _cell(person_id=1, course_id=1, passed_on=date(2026, 3, 1)),
            _cell(person_id=1, course_id=2),
        ],
        engineers={},
    )
    assert list(view.people[0].cells) == ["first-aid"]
    assert "fire-marshal" not in view.people[0].cells
    assert [c.key for c in view.columns] == ["first-aid"]


@pytest.mark.asyncio
async def test_atlas_board_still_404_when_flag_off(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", False)
    with pytest.raises(HTTPException) as exc_info:
        await board_routes.require_competence_board_enabled()
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_get_atlas_board_is_not_422(monkeypatch):
    monkeypatch.setattr(settings, "competence_board_enabled", True)

    async def _empty(_db, _tenant_id):
        return empty_atlas_board()

    monkeypatch.setattr(
        "src.api.routes.workforce_competence_board.build_atlas_board_async",
        _empty,
    )
    response = await board_routes.get_competence_board(
        db=MagicMock(),
        current_user=SimpleNamespace(tenant_id=1),
        family="atlas",
    )
    assert response.family == "atlas"
    assert response.banner == NO_IMPORT_BANNER
    assert response.people == []
