"""Executable spec: action-ownership denominators (w3-owner-count / PX-168).

Two measurements once shared a total of 21 and disagreed on ownership (8/21 vs
0/21). The six stores behind ``GET /api/v1/actions/`` do not share one ownership
column — CAPA stores use ``assigned_to_id``, operational stores use ``owner_id``
— and the unified API maps both onto response ``owner_id``.

These unit tests lock the label map and the mapping hazard so the next surface
cannot re-derive "count actions with an owner" from the wrong column name.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from scripts.governance.action_ownership_denominators import (
    ACTION_OWNERSHIP_STORES,
    naive_wrong_column,
    ownership_column_for,
)
from src.api.routes.actions import _capa_item_to_response
from src.domain.models.capa import CAPAAction
from src.domain.models.complaint import ComplaintAction
from src.domain.models.incident import IncidentAction
from src.domain.models.investigation import InvestigationAction
from src.domain.models.rca_tools import CAPAItem
from src.domain.models.rta import RTAAction

_EXPECTED = {
    "incident_actions": "owner_id",
    "rta_actions": "owner_id",
    "complaint_actions": "owner_id",
    "investigation_actions": "owner_id",
    "capa_actions": "assigned_to_id",
    "capa_items": "assigned_to_id",
}


def test_six_stores_cover_the_unified_actions_register() -> None:
    assert len(ACTION_OWNERSHIP_STORES) == 6
    assert {s.table for s in ACTION_OWNERSHIP_STORES} == set(_EXPECTED)


def test_ownership_column_per_store_matches_orm() -> None:
    """Physical columns on the models must match the published denominators."""
    orm_tables = {
        IncidentAction.__tablename__: IncidentAction.__table__,
        RTAAction.__tablename__: RTAAction.__table__,
        ComplaintAction.__tablename__: ComplaintAction.__table__,
        InvestigationAction.__tablename__: InvestigationAction.__table__,
        CAPAAction.__tablename__: CAPAAction.__table__,
        CAPAItem.__tablename__: CAPAItem.__table__,
    }
    for store in ACTION_OWNERSHIP_STORES:
        assert ownership_column_for(store.table) == _EXPECTED[store.table]
        assert store.ownership_column in orm_tables[store.table].c
        assert store.unified_response_field == "owner_id"


def test_capa_stores_have_no_owner_id_column() -> None:
    """A naive ``owner_id IS NOT NULL`` SQL on CAPA tables cannot see assignees."""
    for table in ("capa_actions", "capa_items"):
        assert naive_wrong_column(table) == "owner_id"
    assert "owner_id" not in CAPAAction.__table__.c
    assert "owner_id" not in CAPAItem.__table__.c
    assert "assigned_to_id" in CAPAAction.__table__.c
    assert "assigned_to_id" in CAPAItem.__table__.c


def test_operational_stores_have_no_assigned_to_id_column() -> None:
    for table in (
        "incident_actions",
        "rta_actions",
        "complaint_actions",
        "investigation_actions",
    ):
        assert naive_wrong_column(table) is None
    assert "assigned_to_id" not in IncidentAction.__table__.c
    assert "owner_id" in IncidentAction.__table__.c


def test_capa_item_response_maps_assigned_to_id_onto_owner_id() -> None:
    """Unified list truth: CAPA assignees appear as response.owner_id."""
    item = SimpleNamespace(
        id=7,
        title="Spec CAPA item",
        description="seeded",
        action_type="corrective",
        priority="medium",
        status="open",
        due_date=None,
        completed_at=None,
        verification_notes=None,
        investigation_id=3,
        assigned_to_id=42,
        created_at=datetime.now(timezone.utc),
    )
    response = _capa_item_to_response(item)  # type: ignore[arg-type]
    assert response.owner_id == 42
    assert response.source_type == "investigation"


def test_capa_item_without_assignee_reports_null_owner_id() -> None:
    item = SimpleNamespace(
        id=8,
        title="Unowned CAPA item",
        description="seeded",
        action_type="corrective",
        priority="medium",
        status="open",
        due_date=None,
        completed_at=None,
        verification_notes=None,
        investigation_id=3,
        assigned_to_id=None,
        created_at=datetime.now(timezone.utc),
    )
    response = _capa_item_to_response(item)  # type: ignore[arg-type]
    assert response.owner_id is None
