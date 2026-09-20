"""Unit tests: the investigation timeline carries the parent source chronology (INV-C9 / D7).

``GET /investigations/{id}/timeline`` read ``investigation_revision_events`` and
nothing else, so the chronology started when the investigation was raised. These
cover the two feeds that were missing — the parent record's ``audit_log_entries``
and its running sheet — plus the things a merge across three tables can get
wrong: ordering, id collisions, tenant scope, and a source that is absent or of
an unsupported type.
"""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.api.routes.investigations import get_investigation_timeline
from src.domain.models.audit_log import AuditLogEntry
from src.domain.models.complaint import ComplaintRunningSheetEntry
from src.domain.models.incident import IncidentRunningSheetEntry
from src.domain.models.investigation import AssignedEntityType, InvestigationRevisionEvent
from src.domain.models.near_miss import NearMissRunningSheetEntry
from src.domain.models.rta import RunningSheetEntry
from src.domain.models.user import User
from src.domain.services.investigation_parent_timeline import (
    EVENT_TYPE_SOURCE_AUDIT,
    EVENT_TYPE_SOURCE_RUNNING_SHEET,
    FEED_AUDIT,
    FEED_RUNNING_SHEET,
    ORIGIN_INVESTIGATION,
    ORIGIN_SOURCE,
    PARENT_ROW_CAP,
    load_parent_timeline_rows,
    resolve_source_binding,
    synthetic_row_id,
)

TENANT = 7
INCIDENT_ID = 314


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeResult:
    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def scalars(self) -> "_FakeResult":
        return self

    def all(self) -> list[Any]:
        return list(self._rows)


class _FakeDb:
    """Answers ``execute`` with canned rows chosen by the model the select targets.

    Real ``select()`` statements are built by the code under test, so the
    where-clauses this asserts on are the ones production would send.
    """

    def __init__(self, **rows_by_model: list[Any]) -> None:
        self._rows = {name: rows for name, rows in rows_by_model.items()}
        self.statements: list[Any] = []

    async def execute(self, statement: Any) -> _FakeResult:
        self.statements.append(statement)
        entity = statement.column_descriptions[0]["entity"]
        return _FakeResult(self._rows.get(entity.__name__, []))

    async def scalar(self, statement: Any) -> Any:  # pragma: no cover - unused by the merge
        self.statements.append(statement)
        return None

    def sql_for(self, model: type) -> str:
        for statement in self.statements:
            if statement.column_descriptions[0]["entity"] is model:
                return str(statement.compile(compile_kwargs={"literal_binds": True}))
        raise AssertionError(f"no statement was issued against {model.__name__}")

    def queried(self, model: type) -> bool:
        return any(s.column_descriptions[0]["entity"] is model for s in self.statements)


def _investigation(
    *,
    entity_type: Any = AssignedEntityType.REPORTING_INCIDENT,
    entity_id: Any = INCIDENT_ID,
    tenant_id: Any = TENANT,
):
    return SimpleNamespace(
        id=42,
        tenant_id=tenant_id,
        assigned_entity_type=entity_type,
        assigned_entity_id=entity_id,
    )


def _revision_event(
    *,
    event_id: int,
    created_at: datetime,
    event_type: str = "STATUS_CHANGED",
    actor_id: int | None = 11,
    metadata: dict | None = None,
) -> InvestigationRevisionEvent:
    return InvestigationRevisionEvent(
        id=event_id,
        tenant_id=TENANT,
        investigation_id=42,
        event_type=event_type,
        field_path="status",
        old_value="in_progress",
        new_value="closed",
        version=3,
        actor_id=actor_id,
        event_metadata=metadata,
        created_at=created_at,
    )


def _audit_entry(
    *,
    entry_id: int,
    timestamp: datetime,
    entity_type: str = "incident",
    entity_id: str = str(INCIDENT_ID),
    user_id: int | None = 11,
    user_name: str | None = "Recorded Name",
    user_email: str | None = "recorded@example.com",
    metadata: dict | None = None,
    changed_fields: list | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
) -> AuditLogEntry:
    return AuditLogEntry(
        id=entry_id,
        tenant_id=TENANT,
        sequence=entry_id,
        entry_hash=f"h{entry_id}",
        previous_hash="p",
        entity_type=entity_type,
        entity_id=entity_id,
        entity_name="INC-2026-0001",
        action="update",
        old_values=old_values,
        new_values=new_values,
        changed_fields=changed_fields,
        user_id=user_id,
        user_name=user_name,
        user_email=user_email,
        entry_metadata=metadata,
        timestamp=timestamp,
    )


def _running_sheet_entry(
    *,
    entry_id: int,
    created_at: datetime,
    content: str = "Attended site, spoke to the operator",
    author_id: int | None = 12,
    author_email: str | None = "author@example.com",
    entry_type: str = "note",
) -> IncidentRunningSheetEntry:
    return IncidentRunningSheetEntry(
        id=entry_id,
        tenant_id=TENANT,
        incident_id=INCIDENT_ID,
        content=content,
        entry_type=entry_type,
        author_id=author_id,
        author_email=author_email,
        created_at=created_at,
    )


async def _timeline(db: _FakeDb, investigation: Any, **kwargs: Any) -> dict:
    params: dict[str, Any] = {"page": 1, "page_size": 20, "event_type": None}
    params.update(kwargs)
    with patch(
        "src.api.routes.investigations._get_investigation_or_404",
        new=AsyncMock(return_value=investigation),
    ):
        return await get_investigation_timeline(
            investigation_id=42,
            db=db,
            current_user=SimpleNamespace(id=11, tenant_id=TENANT),
            **params,
        )


# ---------------------------------------------------------------------------
# Synthetic ids
# ---------------------------------------------------------------------------


def test_synthetic_ids_are_negative_and_unique_across_both_parent_feeds():
    audit = [synthetic_row_id(FEED_AUDIT, i) for i in range(0, 500)]
    sheet = [synthetic_row_id(FEED_RUNNING_SHEET, i) for i in range(0, 500)]

    assert all(row_id < 0 for row_id in audit + sheet)
    assert len(set(audit + sheet)) == 1000


def test_synthetic_id_encodes_the_source_row_reversibly():
    row_id = synthetic_row_id(FEED_RUNNING_SHEET, 17)

    assert abs(row_id) // 10 == 17
    assert abs(row_id) % 10 == 2


@pytest.mark.asyncio
async def test_a_parent_row_cannot_take_the_id_of_a_revision_event():
    """A revision event and a parent row sharing a row number must not share an id."""
    db = _FakeDb(
        InvestigationRevisionEvent=[_revision_event(event_id=5, created_at=datetime(2026, 7, 3, tzinfo=timezone.utc))],
        AuditLogEntry=[_audit_entry(entry_id=5, timestamp=datetime(2026, 7, 2))],
        IncidentRunningSheetEntry=[_running_sheet_entry(entry_id=5, created_at=datetime(2026, 7, 1))],
    )

    response = await _timeline(db, _investigation())
    ids = [item["id"] for item in response["items"]]

    assert len(ids) == 3
    assert len(set(ids)) == 3
    assert 5 in ids


# ---------------------------------------------------------------------------
# Merge ordering and origin
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_merges_all_three_feeds_newest_first_across_naive_and_aware_timestamps():
    """audit_log_entries.timestamp is naive UTC; created_at columns are tz-aware."""
    db = _FakeDb(
        InvestigationRevisionEvent=[
            _revision_event(event_id=1, created_at=datetime(2026, 7, 4, 9, 0, tzinfo=timezone.utc))
        ],
        AuditLogEntry=[
            _audit_entry(entry_id=2, timestamp=datetime(2026, 7, 5, 9, 0)),
            _audit_entry(entry_id=3, timestamp=datetime(2026, 7, 1, 9, 0)),
        ],
        IncidentRunningSheetEntry=[
            _running_sheet_entry(entry_id=4, created_at=datetime(2026, 7, 3, 9, 0, tzinfo=timezone.utc))
        ],
    )

    response = await _timeline(db, _investigation())

    assert [item["event_type"] for item in response["items"]] == [
        EVENT_TYPE_SOURCE_AUDIT,  # 5 Jul
        "STATUS_CHANGED",  # 4 Jul
        EVENT_TYPE_SOURCE_RUNNING_SHEET,  # 3 Jul
        EVENT_TYPE_SOURCE_AUDIT,  # 1 Jul
    ]
    assert response["total"] == 4


@pytest.mark.asyncio
async def test_every_row_declares_its_origin():
    db = _FakeDb(
        InvestigationRevisionEvent=[_revision_event(event_id=1, created_at=datetime(2026, 7, 4, tzinfo=timezone.utc))],
        AuditLogEntry=[_audit_entry(entry_id=2, timestamp=datetime(2026, 7, 3))],
        IncidentRunningSheetEntry=[
            _running_sheet_entry(entry_id=3, created_at=datetime(2026, 7, 2, tzinfo=timezone.utc))
        ],
    )

    response = await _timeline(db, _investigation())
    origins = [item["event_metadata"]["origin"] for item in response["items"]]

    assert origins == [ORIGIN_INVESTIGATION, ORIGIN_SOURCE, ORIGIN_SOURCE]


@pytest.mark.asyncio
async def test_a_revision_event_with_no_metadata_is_still_labelled_investigation():
    """Rows written before INV-C9 carry no origin key; missing means investigation."""
    event = _revision_event(event_id=1, created_at=datetime(2026, 7, 4, tzinfo=timezone.utc), metadata=None)
    db = _FakeDb(InvestigationRevisionEvent=[event])

    response = await _timeline(db, _investigation(entity_type=None))

    assert response["items"][0]["event_metadata"] == {"origin": ORIGIN_INVESTIGATION}
    # The ORM row itself must not be stamped, or the next flush would write it.
    assert event.event_metadata is None


@pytest.mark.asyncio
async def test_existing_revision_metadata_survives_the_origin_stamp():
    db = _FakeDb(
        InvestigationRevisionEvent=[
            _revision_event(
                event_id=1,
                created_at=datetime(2026, 7, 4, tzinfo=timezone.utc),
                metadata={"source": "manual_timeline"},
            )
        ]
    )

    response = await _timeline(db, _investigation(entity_type=None))

    assert response["items"][0]["event_metadata"] == {
        "source": "manual_timeline",
        "origin": ORIGIN_INVESTIGATION,
    }


@pytest.mark.asyncio
async def test_source_rows_name_the_feed_and_the_record_they_came_from():
    db = _FakeDb(
        AuditLogEntry=[
            _audit_entry(
                entry_id=9,
                timestamp=datetime(2026, 7, 3),
                metadata={"event_type": "incident.status_changed", "description": "Incident closed"},
                changed_fields=["status", "closed_at"],
            )
        ],
        IncidentRunningSheetEntry=[
            _running_sheet_entry(entry_id=8, created_at=datetime(2026, 7, 2, tzinfo=timezone.utc))
        ],
    )

    response = await _timeline(db, _investigation())
    audit, sheet = response["items"]

    assert audit["event_metadata"] == {
        "origin": ORIGIN_SOURCE,
        "source_feed": FEED_AUDIT,
        "source_entity_type": AssignedEntityType.REPORTING_INCIDENT.value,
        "source_entity_id": INCIDENT_ID,
        "source_row_id": 9,
        "source_label": "Incident · update",
        "source_event_type": "incident.status_changed",
        "source_action": "update",
        "source_reference": "INC-2026-0001",
        "source_changed_fields": ["status", "closed_at"],
    }
    assert audit["new_value"] == "Incident closed"
    assert audit["field_path"] == "status"

    assert sheet["event_metadata"]["source_feed"] == FEED_RUNNING_SHEET
    assert sheet["event_metadata"]["source_entry_type"] == "note"
    assert sheet["new_value"] == "Attended site, spoke to the operator"
    assert sheet["field_path"] == "running_sheet.note"


@pytest.mark.asyncio
async def test_the_parent_records_field_values_stay_out_of_the_timeline():
    """Only the *names* of changed fields cross over; the payload stays in the audit trail."""
    db = _FakeDb(
        AuditLogEntry=[
            _audit_entry(
                entry_id=9,
                timestamp=datetime(2026, 7, 3),
                changed_fields=["reporter_name"],
                old_values={"reporter_name": "Dana Whitfield", "phone": "07700 900123"},
                new_values={"reporter_name": "Ilse Byrne"},
                metadata={"description": "Incident updated"},
            )
        ]
    )

    response = await _timeline(db, _investigation())
    rendered = repr(response["items"][0])

    assert "Dana Whitfield" not in rendered
    assert "07700 900123" not in rendered
    assert "Ilse Byrne" not in rendered
    assert response["items"][0]["event_metadata"]["source_changed_fields"] == ["reporter_name"]
    assert response["items"][0]["old_value"] is None


# ---------------------------------------------------------------------------
# Actor names
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_parent_rows_prefer_the_live_user_join_over_the_recorded_name():
    db = _FakeDb(
        AuditLogEntry=[_audit_entry(entry_id=9, timestamp=datetime(2026, 7, 3), user_id=11)],
        User=[User(id=11, email="dana@example.com", first_name="Dana", last_name="Whitfield")],
    )

    response = await _timeline(db, _investigation())

    assert response["items"][0]["actor_id"] == 11
    assert response["items"][0]["actor_name"] == "Dana Whitfield"


@pytest.mark.asyncio
async def test_parent_rows_fall_back_to_the_name_recorded_on_the_audit_entry():
    db = _FakeDb(
        AuditLogEntry=[_audit_entry(entry_id=9, timestamp=datetime(2026, 7, 3), user_id=99)],
        User=[],
    )

    response = await _timeline(db, _investigation())

    assert response["items"][0]["actor_name"] == "Recorded Name"


@pytest.mark.asyncio
async def test_running_sheet_email_is_used_only_when_the_entry_names_no_user():
    db = _FakeDb(
        IncidentRunningSheetEntry=[
            _running_sheet_entry(
                entry_id=1,
                created_at=datetime(2026, 7, 3, tzinfo=timezone.utc),
                author_id=None,
                author_email="anon@example.com",
            ),
            _running_sheet_entry(
                entry_id=2,
                created_at=datetime(2026, 7, 2, tzinfo=timezone.utc),
                author_id=12,
                author_email="author@example.com",
            ),
        ],
        User=[],
    )

    response = await _timeline(db, _investigation())
    without_user, with_user = response["items"]

    assert without_user["actor_name"] == "anon@example.com"
    assert with_user["actor_id"] == 12
    assert with_user["actor_name"] is None


# ---------------------------------------------------------------------------
# Tenant scope and fail-closed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_tenantless_investigation_reads_no_parent_rows_at_all():
    db = _FakeDb(
        InvestigationRevisionEvent=[_revision_event(event_id=1, created_at=datetime(2026, 7, 4, tzinfo=timezone.utc))],
        AuditLogEntry=[_audit_entry(entry_id=2, timestamp=datetime(2026, 7, 5))],
        IncidentRunningSheetEntry=[
            _running_sheet_entry(entry_id=3, created_at=datetime(2026, 7, 6, tzinfo=timezone.utc))
        ],
    )

    response = await _timeline(db, _investigation(tenant_id=None))

    assert [item["event_type"] for item in response["items"]] == ["STATUS_CHANGED"]
    assert not db.queried(AuditLogEntry)
    assert not db.queried(IncidentRunningSheetEntry)


@pytest.mark.asyncio
async def test_every_parent_query_is_tenant_filtered():
    db = _FakeDb(
        AuditLogEntry=[_audit_entry(entry_id=1, timestamp=datetime(2026, 7, 3))],
        IncidentRunningSheetEntry=[
            _running_sheet_entry(entry_id=1, created_at=datetime(2026, 7, 2, tzinfo=timezone.utc))
        ],
    )

    await _timeline(db, _investigation())

    audit_sql = db.sql_for(AuditLogEntry)
    assert f"audit_log_entries.tenant_id = {TENANT}" in audit_sql
    assert f"audit_log_entries.entity_id = '{INCIDENT_ID}'" in audit_sql
    assert f"LIMIT {PARENT_ROW_CAP}" in audit_sql

    sheet_sql = db.sql_for(IncidentRunningSheetEntry)
    assert f"incident_running_sheet_entries.tenant_id = {TENANT}" in sheet_sql
    assert f"incident_running_sheet_entries.incident_id = {INCIDENT_ID}" in sheet_sql
    assert f"LIMIT {PARENT_ROW_CAP}" in sheet_sql


# ---------------------------------------------------------------------------
# Absent or unsupported source
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "investigation",
    [
        _investigation(entity_type=None),
        _investigation(entity_type="workforce_competency"),
        _investigation(entity_id=None),
        _investigation(entity_id="not-a-number"),
    ],
    ids=["no-type", "unsupported-type", "no-id", "unparseable-id"],
)
async def test_an_absent_or_unsupported_source_returns_investigation_events_only(investigation):
    db = _FakeDb(
        InvestigationRevisionEvent=[_revision_event(event_id=1, created_at=datetime(2026, 7, 4, tzinfo=timezone.utc))],
        AuditLogEntry=[_audit_entry(entry_id=2, timestamp=datetime(2026, 7, 5))],
    )

    response = await _timeline(db, investigation)

    assert [item["id"] for item in response["items"]] == [1]
    assert response["total"] == 1
    assert not db.queried(AuditLogEntry)


@pytest.mark.asyncio
async def test_an_undated_parent_row_is_dropped_rather_than_failing_the_page():
    """created_at is required on the response schema; one bad row must not 500 the page."""
    db = _FakeDb(
        InvestigationRevisionEvent=[_revision_event(event_id=1, created_at=datetime(2026, 7, 4, tzinfo=timezone.utc))],
        AuditLogEntry=[
            _audit_entry(entry_id=2, timestamp=None),
            _audit_entry(entry_id=3, timestamp=datetime(2026, 7, 5)),
        ],
    )

    response = await _timeline(db, _investigation())

    assert [item["id"] for item in response["items"]] == [synthetic_row_id(FEED_AUDIT, 3), 1]
    assert response["total"] == 2


@pytest.mark.asyncio
async def test_an_audit_row_with_unusable_json_columns_still_renders():
    """entry_metadata and changed_fields are free JSON; neither shape is guaranteed."""
    db = _FakeDb(
        AuditLogEntry=[
            _audit_entry(
                entry_id=2,
                timestamp=datetime(2026, 7, 5),
                metadata=None,
                changed_fields={"status": "closed"},
            )
        ]
    )

    response = await _timeline(db, _investigation())
    item = response["items"][0]

    assert item["event_metadata"]["source_changed_fields"] == []
    assert item["event_metadata"]["source_event_type"] is None
    assert item["field_path"] is None
    assert item["new_value"] == "INC-2026-0001"


@pytest.mark.asyncio
async def test_an_investigation_with_nothing_recorded_anywhere_returns_an_empty_page():
    db = _FakeDb()

    response = await _timeline(db, _investigation())

    assert response["items"] == []
    assert response["total"] == 0
    assert response["pages"] == 1


# ---------------------------------------------------------------------------
# Register mapping
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("assigned_entity_type", "audit_entity_type", "running_sheet_model", "parent_attr"),
    [
        (AssignedEntityType.REPORTING_INCIDENT, "incident", IncidentRunningSheetEntry, "incident_id"),
        (AssignedEntityType.NEAR_MISS, "near_miss", NearMissRunningSheetEntry, "near_miss_id"),
        (AssignedEntityType.ROAD_TRAFFIC_COLLISION, "rta", RunningSheetEntry, "rta_id"),
        (AssignedEntityType.COMPLAINT, "complaint", ComplaintRunningSheetEntry, "complaint_id"),
    ],
)
def test_each_register_maps_to_the_entity_type_its_service_actually_writes(
    assigned_entity_type, audit_entity_type, running_sheet_model, parent_attr
):
    binding = resolve_source_binding(assigned_entity_type)

    assert binding is not None
    assert binding.audit_entity_types[0] == audit_entity_type
    assert binding.running_sheet_model is running_sheet_model
    assert binding.running_sheet_parent_attr == parent_attr


def test_child_entity_types_are_not_mistaken_for_the_parent_record():
    """incident_action / rta_action rows carry an action id, not the case's id."""
    for assigned_entity_type in AssignedEntityType:
        binding = resolve_source_binding(assigned_entity_type)
        assert binding is not None
        assert not any(entity_type.endswith("_action") for entity_type in binding.audit_entity_types)


@pytest.mark.asyncio
async def test_an_event_type_filter_no_parent_row_can_satisfy_skips_the_parent_queries():
    db = _FakeDb(AuditLogEntry=[_audit_entry(entry_id=1, timestamp=datetime(2026, 7, 3))])

    rows = await load_parent_timeline_rows(db, investigation=_investigation(), event_type="STATUS_CHANGED")

    assert rows == []
    assert not db.queried(AuditLogEntry)


@pytest.mark.asyncio
async def test_filtering_to_the_running_sheet_leaves_the_audit_feed_unread():
    db = _FakeDb(
        AuditLogEntry=[_audit_entry(entry_id=1, timestamp=datetime(2026, 7, 3))],
        IncidentRunningSheetEntry=[
            _running_sheet_entry(entry_id=1, created_at=datetime(2026, 7, 2, tzinfo=timezone.utc))
        ],
    )

    rows = await load_parent_timeline_rows(
        db, investigation=_investigation(), event_type=EVENT_TYPE_SOURCE_RUNNING_SHEET
    )

    assert [row.event_type for row in rows] == [EVENT_TYPE_SOURCE_RUNNING_SHEET]
    assert not db.queried(AuditLogEntry)


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pages_are_cut_after_the_merge_not_per_feed():
    db = _FakeDb(
        InvestigationRevisionEvent=[
            _revision_event(event_id=1, created_at=datetime(2026, 7, 5, tzinfo=timezone.utc)),
            _revision_event(event_id=2, created_at=datetime(2026, 7, 3, tzinfo=timezone.utc)),
        ],
        AuditLogEntry=[
            _audit_entry(entry_id=3, timestamp=datetime(2026, 7, 4)),
            _audit_entry(entry_id=4, timestamp=datetime(2026, 7, 2)),
        ],
        IncidentRunningSheetEntry=[
            _running_sheet_entry(entry_id=5, created_at=datetime(2026, 7, 1, tzinfo=timezone.utc))
        ],
    )
    investigation = _investigation()

    pages = [await _timeline(db, investigation, page=page, page_size=2) for page in (1, 2, 3, 4)]

    assert [[item["id"] for item in page["items"]] for page in pages] == [
        [1, synthetic_row_id(FEED_AUDIT, 3)],
        [2, synthetic_row_id(FEED_AUDIT, 4)],
        [synthetic_row_id(FEED_RUNNING_SHEET, 5)],
        [],
    ]
    assert {page["total"] for page in pages} == {5}
    assert {page["pages"] for page in pages} == {3}


@pytest.mark.asyncio
async def test_a_shared_timestamp_still_orders_deterministically():
    """created_at ties break on id DESC, which puts the investigation's own row first."""
    same = datetime(2026, 7, 4, 9, 0)
    db = _FakeDb(
        InvestigationRevisionEvent=[_revision_event(event_id=1, created_at=same.replace(tzinfo=timezone.utc))],
        AuditLogEntry=[_audit_entry(entry_id=1, timestamp=same)],
    )

    first = await _timeline(db, _investigation())
    second = await _timeline(db, _investigation())

    assert [item["id"] for item in first["items"]] == [1, synthetic_row_id(FEED_AUDIT, 1)]
    assert [item["id"] for item in second["items"]] == [item["id"] for item in first["items"]]
