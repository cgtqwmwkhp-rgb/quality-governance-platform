"""Parent-source chronology for the investigation timeline (INV-C9 / D7).

``GET /investigations/{id}/timeline`` used to read ``investigation_revision_events``
and nothing else, so the chronology stopped at the investigation boundary: every
entry the case accumulated *before* an investigation was raised — and everything
still being written to the source case afterwards — was invisible from the
investigation. This module supplies the two missing feeds:

* ``audit_log_entries`` for the parent record (create / update / status rows), and
* the register's running-sheet table (the investigator-authored narrative).

Both are read-only and tenant-scoped. Nothing here writes.

Shape
-----
Rows come back as :class:`ParentTimelineRow`, deliberately field-for-field
compatible with what the route emits for a revision event, so the response
schema (``InvestigationTimelineEventResponse``) does not change. Origin travels
in ``event_metadata["origin"]`` (``"source"`` here, ``"investigation"`` for
revision events) rather than a new top-level field.

Synthetic ids
-------------
``id`` is a required ``int`` on the response and the frontend keys rows off it,
so parent rows need ids that cannot collide with revision-event ids or with each
other. Scheme: ``-(source_row_id * 10 + feed_code)`` where ``feed_code`` is a
single digit unique per feed (see :data:`_FEED_ID_CODES`).

* Negative, so disjoint from revision-event ids, which are positive autoincrement.
* ``(row_id, feed_code)`` -> ``row_id * 10 + feed_code`` is injective while
  ``feed_code < 10``, so two feeds cannot produce the same id.
* Reversible: ``abs(id) // 10`` is the source row id, ``abs(id) % 10`` the feed.
  The originating row id is also carried explicitly as
  ``event_metadata["source_row_id"]`` so no consumer has to do that arithmetic.

Deliberate omissions
--------------------
``AuditLogEntry.old_values`` / ``new_values`` hold the whole mutation payload for
the parent record — for an incident that is reporter, injured person, and
free-text description. They are **not** copied into the timeline. The row emits
the audit entry's description and the *names* of the changed fields
(``event_metadata["source_changed_fields"]``); the values stay in the Admin Audit
Trail, which has its own authorisation. The running-sheet ``content`` *is*
emitted — that narrative is the chronology D7 is about, and the investigation is
by definition the case's own record.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit_log import AuditLogEntry
from src.domain.models.complaint import ComplaintRunningSheetEntry
from src.domain.models.incident import IncidentRunningSheetEntry
from src.domain.models.investigation import AssignedEntityType
from src.domain.models.near_miss import NearMissRunningSheetEntry
from src.domain.models.rta import RunningSheetEntry

logger = logging.getLogger(__name__)

# event_metadata["origin"] values. A revision event written before INV-C9 has no
# origin key at all; the route treats a missing origin as "investigation", which
# is what those rows have always been.
ORIGIN_INVESTIGATION = "investigation"
ORIGIN_SOURCE = "source"

# event_metadata["source_feed"] values.
FEED_AUDIT = "audit"
FEED_RUNNING_SHEET = "running_sheet"

# Coarse event_type values for parent rows. Coarse on purpose: ``event_type`` is
# also the ``?event_type=`` filter and the frontend's filter vocabulary, so the
# specific audit event ("incident.status_changed") travels in
# event_metadata["source_event_type"] instead of fragmenting the filter list.
EVENT_TYPE_SOURCE_AUDIT = "SOURCE_AUDIT"
EVENT_TYPE_SOURCE_RUNNING_SHEET = "SOURCE_RUNNING_SHEET"

SOURCE_EVENT_TYPES = (EVENT_TYPE_SOURCE_AUDIT, EVENT_TYPE_SOURCE_RUNNING_SHEET)

# Newest N rows *per parent feed*, so at most 2 * PARENT_ROW_CAP parent rows for
# one investigation. A three-year-old incident can carry thousands of audit rows;
# without a cap the merge would load all of them to render one page of twenty.
PARENT_ROW_CAP = 200

# Newest N revision events considered for the merge. Merging correctly means
# ordering both feeds together before slicing, which rules out paginating the
# revision feed in SQL, so it needs a bound of its own.
INVESTIGATION_ROW_CAP = 1000

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)

_FEED_ID_CODES = {FEED_AUDIT: 1, FEED_RUNNING_SHEET: 2}


@dataclass(frozen=True)
class ParentTimelineRow:
    """One parent-source row, shaped like a timeline event.

    ``fallback_actor_name`` is only used when the live ``users`` join resolves
    nothing — see :func:`resolved_actor_name`.
    """

    id: int
    event_type: str
    created_at: Optional[datetime]
    field_path: Optional[str] = None
    old_value: Optional[str] = None
    new_value: Optional[str] = None
    actor_id: Optional[int] = None
    fallback_actor_name: Optional[str] = None
    version: Optional[int] = None
    event_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class _SourceBinding:
    """How one ``AssignedEntityType`` maps onto the parent tables."""

    entity_type: str
    label: str
    audit_entity_types: tuple[str, ...]
    running_sheet_model: Any
    running_sheet_parent_attr: str


# ``AuditLogEntry.entity_type`` is a free-text String(100), so the values here are
# the ones this repo actually writes, read off the call sites rather than guessed:
# ``incident`` (incident_service), ``near_miss`` (near_miss_service), ``rta``
# (rta_service), ``complaint`` (complaint_service). Where the register's audit
# spelling differs from the ``AssignedEntityType`` spelling the enum value is
# accepted as well, so a row written under the investigation's own vocabulary is
# not silently dropped. Child entity types (``incident_action``, ``rta_action``)
# are excluded: their ``entity_id`` is an action id, not the parent's, and
# matching them would attribute another record's history to this case.
_SOURCE_BINDINGS: dict[str, _SourceBinding] = {
    AssignedEntityType.REPORTING_INCIDENT.value: _SourceBinding(
        entity_type=AssignedEntityType.REPORTING_INCIDENT.value,
        label="Incident",
        audit_entity_types=("incident", "reporting_incident"),
        running_sheet_model=IncidentRunningSheetEntry,
        running_sheet_parent_attr="incident_id",
    ),
    AssignedEntityType.NEAR_MISS.value: _SourceBinding(
        entity_type=AssignedEntityType.NEAR_MISS.value,
        label="Near miss",
        audit_entity_types=("near_miss",),
        running_sheet_model=NearMissRunningSheetEntry,
        running_sheet_parent_attr="near_miss_id",
    ),
    AssignedEntityType.ROAD_TRAFFIC_COLLISION.value: _SourceBinding(
        entity_type=AssignedEntityType.ROAD_TRAFFIC_COLLISION.value,
        label="Road traffic collision",
        audit_entity_types=("rta", "road_traffic_collision"),
        running_sheet_model=RunningSheetEntry,
        running_sheet_parent_attr="rta_id",
    ),
    AssignedEntityType.COMPLAINT.value: _SourceBinding(
        entity_type=AssignedEntityType.COMPLAINT.value,
        label="Complaint",
        audit_entity_types=("complaint",),
        running_sheet_model=ComplaintRunningSheetEntry,
        running_sheet_parent_attr="complaint_id",
    ),
}


def synthetic_row_id(feed: str, row_id: int) -> int:
    """Collision-free negative id for a parent row. See the module docstring."""
    code = _FEED_ID_CODES[feed]
    return -(abs(int(row_id)) * 10 + code)


def as_utc(value: Any) -> Optional[datetime]:
    """Normalise a timestamp column to an aware UTC datetime, or None.

    Necessary, not cosmetic: ``TimestampMixin.created_at`` is
    ``DateTime(timezone=True)`` (aware under Postgres) while
    ``AuditLogEntry.timestamp`` is ``NaiveUTCDateTime`` (naive by design).
    Sorting the two feeds together without this raises ``TypeError: can't
    compare offset-naive and offset-aware datetimes``. Both columns are
    documented UTC, so a naive value is read as UTC rather than as local time.
    """
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def timeline_sort_key(created_at: Any, row_id: Any) -> tuple[datetime, int]:
    """Sort key for the merged feed: newest first, then id descending.

    Used with ``reverse=True``. Because parent ids are negative and revision-event
    ids positive, a shared timestamp puts the investigation's own event first —
    arbitrary but deterministic, which is what pagination needs. A row with an
    unreadable timestamp sorts to the end rather than breaking the sort.
    """
    return (as_utc(created_at) or _EPOCH, _coerce_int(row_id) or 0)


def resolved_actor_name(row: ParentTimelineRow, actor_names: dict[int, str]) -> Optional[str]:
    """Live ``users`` name for the row's actor, else the row's own recorded name.

    The live join is preferred so a renamed user reads correctly. The fallback is
    already-stored, already-exposed data (``audit_log_entries.user_name`` /
    ``user_email`` are returned by the Admin Audit Trail API today, and a
    running-sheet ``author_email`` is only used when the entry has no
    ``author_id`` at all); nothing new about a person is derived here.
    """
    if row.actor_id is not None:
        resolved = actor_names.get(row.actor_id)
        if resolved:
            return resolved
    return row.fallback_actor_name


def resolve_source_binding(assigned_entity_type: Any) -> Optional[_SourceBinding]:
    """Binding for this investigation's source register, or None if unsupported.

    Returns None — rather than raising — for an unknown, unset or non-string
    entity type, so a run pointing at a register this module has no feed for
    still gets its own events back instead of a 500.
    """
    value = getattr(assigned_entity_type, "value", assigned_entity_type)
    if not isinstance(value, str):
        return None
    return _SOURCE_BINDINGS.get(value.strip().lower())


def _coerce_int(value: Any) -> Optional[int]:
    """Int from an int or a digit string, else None (bools and mocks refused)."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        candidate = value.strip()
        if candidate.lstrip("-").isdigit():
            return int(candidate)
    return None


def _clean_str(value: Any, limit: int = 2000) -> Optional[str]:
    """Trim a value to a bounded string, or None when there is nothing to show."""
    if value is None:
        return None
    text = value if isinstance(value, str) else str(value)
    text = text.strip()
    if not text:
        return None
    return text[:limit]


async def load_parent_timeline_rows(
    db: AsyncSession,
    *,
    investigation: Any,
    event_type: Optional[str] = None,
    cap: int = PARENT_ROW_CAP,
) -> list[ParentTimelineRow]:
    """Newest ``cap`` rows per parent feed for this investigation's source record.

    Returns ``[]`` — never raises — whenever the parent chronology cannot be read
    safely or at all:

    * ``tenant_id`` is None or unreadable. Fail closed: every parent query is
      tenant-filtered, and a run with no tenant has nothing to filter on, so the
      alternative would be an unscoped read across tenants.
    * ``assigned_entity_type`` names no register this module has a feed for.
    * ``assigned_entity_id`` is missing or not an integer.
    * ``event_type`` is set to something no parent row can be, in which case the
      queries are skipped rather than run and discarded.
    """
    binding = resolve_source_binding(getattr(investigation, "assigned_entity_type", None))
    if binding is None:
        return []

    tenant_id = _coerce_int(getattr(investigation, "tenant_id", None))
    if tenant_id is None:
        logger.warning(
            "investigation_parent_timeline_fail_closed investigation_id=%s reason=no_tenant",
            getattr(investigation, "id", None),
        )
        return []

    entity_id = _coerce_int(getattr(investigation, "assigned_entity_id", None))
    if entity_id is None:
        return []

    wanted = _clean_str(event_type)
    if wanted is not None and wanted not in SOURCE_EVENT_TYPES:
        return []

    rows: list[ParentTimelineRow] = []
    if wanted in (None, EVENT_TYPE_SOURCE_AUDIT):
        rows.extend(await _load_audit_rows(db, binding, tenant_id=tenant_id, entity_id=entity_id, cap=cap))
    if wanted in (None, EVENT_TYPE_SOURCE_RUNNING_SHEET):
        rows.extend(await _load_running_sheet_rows(db, binding, tenant_id=tenant_id, entity_id=entity_id, cap=cap))

    # Every source column is NOT NULL, so this should drop nothing. It is here
    # because ``created_at`` is required on the response schema: one unreadable
    # timestamp would turn the whole page into a 500, and a row that cannot be
    # placed on a chronology has nothing to contribute to one anyway.
    placeable = [row for row in rows if row.created_at is not None]
    if len(placeable) != len(rows):
        logger.warning(
            "investigation_parent_timeline_dropped_undated investigation_id=%s dropped=%s",
            getattr(investigation, "id", None),
            len(rows) - len(placeable),
        )
    return placeable


def _base_metadata(binding: _SourceBinding, *, feed: str, entity_id: int, row_id: int) -> dict[str, Any]:
    return {
        "origin": ORIGIN_SOURCE,
        "source_feed": feed,
        "source_entity_type": binding.entity_type,
        "source_entity_id": entity_id,
        "source_row_id": row_id,
    }


async def _load_audit_rows(
    db: AsyncSession,
    binding: _SourceBinding,
    *,
    tenant_id: int,
    entity_id: int,
    cap: int,
) -> list[ParentTimelineRow]:
    """Immutable audit rows for the parent record, newest first."""
    query = (
        select(AuditLogEntry)
        .where(
            AuditLogEntry.tenant_id == tenant_id,
            AuditLogEntry.entity_type.in_(binding.audit_entity_types),
            # entity_id is a String(100) column; record_audit_event writes str(id).
            AuditLogEntry.entity_id == str(entity_id),
        )
        .order_by(desc(AuditLogEntry.timestamp), desc(AuditLogEntry.id))
        .limit(cap)
    )
    result = await db.execute(query)
    return [_audit_row(entry, binding, entity_id=entity_id) for entry in result.scalars().all()]


def _audit_row(entry: Any, binding: _SourceBinding, *, entity_id: int) -> ParentTimelineRow:
    entry_metadata = entry.entry_metadata if isinstance(entry.entry_metadata, dict) else {}
    # Both are free JSON columns, so neither shape is guaranteed by the schema.
    raw_changed = entry.changed_fields if isinstance(entry.changed_fields, list) else []
    changed_fields = [name for name in (_clean_str(f, 200) for f in raw_changed[:50]) if name is not None]
    action = _clean_str(entry.action, 50)
    row_id = _coerce_int(entry.id) or 0

    metadata = _base_metadata(binding, feed=FEED_AUDIT, entity_id=entity_id, row_id=row_id)
    metadata.update(
        {
            "source_label": f"{binding.label} · {action}" if action else binding.label,
            "source_event_type": _clean_str(entry_metadata.get("event_type"), 100),
            "source_action": action,
            "source_reference": _clean_str(entry.entity_name, 255),
            # Field names only. The old/new values behind them stay in the audit
            # trail — see the module docstring.
            "source_changed_fields": changed_fields,
        }
    )

    actor_id = _coerce_int(entry.user_id)
    return ParentTimelineRow(
        id=synthetic_row_id(FEED_AUDIT, row_id),
        event_type=EVENT_TYPE_SOURCE_AUDIT,
        created_at=as_utc(entry.timestamp),
        field_path=changed_fields[0] if changed_fields else None,
        new_value=(
            _clean_str(entry_metadata.get("description"))
            or _clean_str(entry.entity_name, 255)
            or _clean_str(entry_metadata.get("event_type"), 100)
        ),
        actor_id=actor_id,
        fallback_actor_name=_clean_str(entry.user_name, 255) or _clean_str(entry.user_email, 255),
        event_metadata=metadata,
    )


async def _load_running_sheet_rows(
    db: AsyncSession,
    binding: _SourceBinding,
    *,
    tenant_id: int,
    entity_id: int,
    cap: int,
) -> list[ParentTimelineRow]:
    """Running-sheet narrative for the parent record, newest first.

    ``tenant_id`` on all four running-sheet tables is nullable. Filtering on
    equality therefore excludes any legacy row that never recorded a tenant; that
    is the fail-closed direction and the deliberate one — an entry that cannot be
    proved to belong to this tenant is not shown to it.
    """
    model = binding.running_sheet_model
    parent_column = getattr(model, binding.running_sheet_parent_attr)
    query = (
        select(model)
        .where(model.tenant_id == tenant_id, parent_column == entity_id)
        .order_by(desc(model.created_at), desc(model.id))
        .limit(cap)
    )
    result = await db.execute(query)
    return [_running_sheet_row(entry, binding, entity_id=entity_id) for entry in result.scalars().all()]


def _running_sheet_row(entry: Any, binding: _SourceBinding, *, entity_id: int) -> ParentTimelineRow:
    row_id = _coerce_int(entry.id) or 0
    entry_type = _clean_str(entry.entry_type, 50) or "note"

    metadata = _base_metadata(binding, feed=FEED_RUNNING_SHEET, entity_id=entity_id, row_id=row_id)
    metadata.update(
        {
            "source_label": f"{binding.label} · running sheet",
            "source_entry_type": entry_type,
        }
    )

    actor_id = _coerce_int(entry.author_id)
    return ParentTimelineRow(
        id=synthetic_row_id(FEED_RUNNING_SHEET, row_id),
        event_type=EVENT_TYPE_SOURCE_RUNNING_SHEET,
        created_at=as_utc(entry.created_at),
        field_path=f"running_sheet.{entry_type}",
        new_value=_clean_str(entry.content, 5000),
        actor_id=actor_id,
        # Only when the entry names no user at all, so the timeline never prefers
        # an email address over a resolvable identity.
        fallback_actor_name=None if actor_id is not None else _clean_str(entry.author_email, 255),
        event_metadata=metadata,
    )
