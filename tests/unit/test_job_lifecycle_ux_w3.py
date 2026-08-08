"""JL-UX-W3: document freshness, obsolete enforcement on attach, audit lapse.

Four claims worth pinning:

1. **Unknown is not "fine".** Every path with no review date, no cadence or no
   readable run must resolve to ``unknown`` with a reason, never to ``current``.
   A test that only checked the happy states would let a silent optimistic
   default through.
2. **Obsolescence is the document SSOT's call.** Library status and Document
   Control status both block an attach; the job lifecycle stores nothing.
3. **Enforcement applies to newly added ids only.** ``PUT .../documents``
   replaces the whole membership list, so enforcing on the whole list would
   trap an operator who is trying to *remove* a reference that went obsolete
   after it was attached.
4. **No migration.** W3 is read-side; nothing about freshness is persisted on
   the job lifecycle tables.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException

from src.api.schemas.job_lifecycle import (
    JobCellLinkResponse,
    JobDocumentFreshnessItem,
    JobDocumentFreshnessResponse,
)
from src.domain.models.job_lifecycle import JobCell, JobCellDocument, JobCellLink
from src.domain.services.job_lifecycle_freshness import (
    AUDIT_FREQUENCY_DAYS,
    DOCUMENT_FRESHNESS_STATES,
    OBSOLETE_LIBRARY_STATUSES,
    as_aware_utc,
    audit_frequency_days,
    classify_audit_lapse,
    classify_document_freshness,
    normalise_status,
)
from src.domain.services.job_lifecycle_service import (
    MAX_FRESHNESS_DOCUMENT_IDS,
    JobLifecycleService,
    serialize_cell_link,
)

NOW = datetime(2026, 8, 8, 12, 0, tzinfo=timezone.utc)
REPO_ROOT = Path(__file__).resolve().parents[2]
ALEMBIC_VERSIONS = REPO_ROOT / "alembic/versions"


# ---------------------------------------------------------------------------
# No migration
# ---------------------------------------------------------------------------


def test_w3_adds_no_alembic_revision_after_the_w2_head():
    """Freshness is read-side. A new head here would be a schema change nobody asked for."""
    revisions: set[str] = set()
    down_revisions: set[str] = set()
    for path in ALEMBIC_VERSIONS.glob("*.py"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if '"' not in line:
                continue
            if line.startswith("revision: str = "):
                revisions.add(line.split('"')[1])
            elif line.startswith("down_revision"):
                down_revisions.add(line.split('"')[1])
    assert "20261021_job_nest_pdca" in revisions
    assert "20261021_job_nest_pdca" not in down_revisions, (
        "A revision now sits on top of the W2 head; W3 was specified as no-migration."
    )


def test_freshness_is_not_persisted_on_job_lifecycle_tables():
    """No cached status column: the document tables stay the only source."""
    for model in (JobCell, JobCellDocument, JobCellLink):
        columns = {c.name for c in model.__table__.columns}
        for leaked in ("freshness", "document_status", "is_obsolete", "review_date", "audit_lapse"):
            assert leaked not in columns, f"{model.__name__} caches document state in {leaked}"


# ---------------------------------------------------------------------------
# Document freshness classification
# ---------------------------------------------------------------------------


def test_missing_review_date_is_unknown_not_current():
    verdict = classify_document_freshness(library_status="approved", now=NOW)
    assert verdict.state == "unknown"
    assert verdict.reason == "no_review_date"
    assert verdict.is_obsolete is False


def test_a_document_outside_the_tenant_is_unknown_not_obsolete():
    verdict = classify_document_freshness(found=False, now=NOW)
    assert verdict.state == "unknown"
    assert verdict.reason == "document_not_found"
    assert verdict.is_obsolete is False


@pytest.mark.parametrize("status", sorted(OBSOLETE_LIBRARY_STATUSES))
def test_every_withdrawn_library_status_reads_as_obsolete(status):
    verdict = classify_document_freshness(library_status=status, now=NOW)
    assert verdict.state == "obsolete"
    assert verdict.reason == "obsolete_library_status"
    assert verdict.is_obsolete is True


def test_doc_control_obsolete_beats_an_approved_library_row():
    """Doc control withdrawing a controlled copy is the answer that matters."""
    verdict = classify_document_freshness(
        library_status="approved",
        controlled_status="Obsolete",
        library_review_date=NOW + timedelta(days=365),
        now=NOW,
    )
    assert verdict.state == "obsolete"
    assert verdict.reason == "obsolete_controlled_status"


def test_obsolescence_wins_over_an_overdue_review_date():
    """A withdrawn document is out of use, not merely late for review."""
    verdict = classify_document_freshness(
        library_status="obsolete",
        library_review_date=NOW - timedelta(days=900),
        now=NOW,
    )
    assert verdict.state == "obsolete"


@pytest.mark.parametrize(
    ("offset_days", "expected"),
    [(-1, "overdue"), (0, "due_soon"), (5, "due_soon"), (30, "due_soon"), (31, "current")],
)
def test_review_date_windows(offset_days, expected):
    verdict = classify_document_freshness(
        library_status="approved",
        library_review_date=NOW + timedelta(days=offset_days),
        now=NOW,
    )
    assert verdict.state == expected
    assert verdict.state in DOCUMENT_FRESHNESS_STATES


def test_doc_control_next_review_date_is_preferred_over_the_library_date():
    verdict = classify_document_freshness(
        library_status="approved",
        controlled_status="published",
        library_review_date=NOW + timedelta(days=400),
        controlled_next_review_date=NOW - timedelta(days=2),
        now=NOW,
    )
    assert verdict.state == "overdue"
    assert verdict.review_date == NOW - timedelta(days=2)


def test_naive_doc_control_dates_are_read_as_utc_not_crashed_on():
    """``controlled_documents.next_review_date`` is a naive column."""
    naive = (NOW - timedelta(days=3)).replace(tzinfo=None)
    verdict = classify_document_freshness(
        library_status="approved",
        controlled_next_review_date=naive,
        now=NOW,
    )
    assert verdict.state == "overdue"
    assert verdict.review_date is not None
    assert verdict.review_date.tzinfo is not None


def test_normalise_status_handles_enums_blanks_and_case():
    assert normalise_status(SimpleNamespace(value="OBSOLETE")) == "obsolete"
    assert normalise_status("  Approved ") == "approved"
    assert normalise_status("") is None
    assert normalise_status(None) is None
    assert as_aware_utc(None) is None


# ---------------------------------------------------------------------------
# Audit lapse classification
# ---------------------------------------------------------------------------


def test_ad_hoc_audits_never_lapse_they_report_unknown():
    verdict = classify_audit_lapse(
        completed_at=NOW - timedelta(days=5000), frequency="ad_hoc", now=NOW
    )
    assert verdict.state == "unknown"
    assert verdict.reason == "no_audit_cadence"


def test_unrecognised_frequency_is_unknown_not_a_guessed_cadence():
    assert audit_frequency_days("every other Tuesday") is None
    verdict = classify_audit_lapse(
        completed_at=NOW - timedelta(days=5000), frequency="every other Tuesday", now=NOW
    )
    assert verdict.state == "unknown"
    assert verdict.next_due_at is None


def test_no_run_data_at_all_is_unknown():
    assert classify_audit_lapse(found=False, now=NOW).state == "unknown"
    assert classify_audit_lapse(now=NOW).reason == "audit_not_completed"


@pytest.mark.parametrize("frequency", sorted(AUDIT_FREQUENCY_DAYS))
def test_a_completed_audit_lapses_once_its_cadence_elapses(frequency):
    days = AUDIT_FREQUENCY_DAYS[frequency]
    lapsed = classify_audit_lapse(
        completed_at=NOW - timedelta(days=days + 1), frequency=frequency, now=NOW
    )
    assert lapsed.state == "lapsed"
    assert lapsed.reason == "cadence_overdue"
    assert lapsed.next_due_at == NOW - timedelta(days=1)

    fresh = classify_audit_lapse(completed_at=NOW, frequency=frequency, now=NOW)
    assert fresh.state in ("current", "due_soon")


def test_a_short_cadence_is_not_permanently_due_soon():
    """A fixed 30-day warning would swallow a daily audit's whole cycle."""
    daily = classify_audit_lapse(completed_at=NOW, frequency="daily", now=NOW)
    assert daily.state == "current"
    annual = classify_audit_lapse(
        completed_at=NOW - timedelta(days=340), frequency="annually", now=NOW
    )
    assert annual.state == "due_soon"


def test_an_uncompleted_run_past_its_due_date_is_lapsed():
    verdict = classify_audit_lapse(due_date=NOW - timedelta(days=1), now=NOW)
    assert verdict.state == "lapsed"
    assert verdict.reason == "run_past_due"
    assert verdict.last_completed_at is None


def test_an_uncompleted_run_still_within_its_due_date_is_current():
    verdict = classify_audit_lapse(due_date=NOW + timedelta(days=90), now=NOW)
    assert verdict.state == "current"
    assert verdict.reason == "run_within_due"


# ---------------------------------------------------------------------------
# Link serialization
# ---------------------------------------------------------------------------


def _audit_link(**overrides):
    base = dict(
        id=1,
        tenant_id=1,
        cell_id=2,
        kind="audit_outcome",
        label="Finding 12",
        entity_type=None,
        entity_id=None,
        external_url=None,
        audit_run_id=5,
        audit_finding_id=12,
        target_job_type_id=None,
        sort_order=0,
        created_at=NOW,
        updated_at=NOW,
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_audit_lapse_is_attached_only_from_a_prefetched_map():
    verdict = classify_audit_lapse(completed_at=NOW - timedelta(days=400), frequency="annually", now=NOW)
    payload = serialize_cell_link(_audit_link(), audit_lapse_by_run={5: verdict})
    assert payload["audit_lapse"]["state"] == "lapsed"
    assert payload["audit_lapse"]["frequency"] == "annually"


def test_audit_lapse_is_none_when_the_run_is_not_in_the_map():
    """Absent evidence must not be rendered as a verdict."""
    assert serialize_cell_link(_audit_link(), audit_lapse_by_run={}).get("audit_lapse") is None
    assert serialize_cell_link(_audit_link()).get("audit_lapse") is None


def test_non_audit_links_never_carry_a_lapse():
    external = _audit_link(
        kind="external", external_url="https://a.test", audit_run_id=None, audit_finding_id=None
    )
    payload = serialize_cell_link(external, audit_lapse_by_run={5: classify_audit_lapse(now=NOW)})
    assert payload["audit_lapse"] is None


def test_link_response_schema_accepts_an_absent_lapse():
    """Old rows and non-audit kinds must still validate."""
    model = JobCellLinkResponse.model_validate(serialize_cell_link(_audit_link()))
    assert model.audit_lapse is None


# ---------------------------------------------------------------------------
# Freshness lookup service
# ---------------------------------------------------------------------------


class _Scalars:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class _Result:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return _Scalars(self._rows)

    def all(self):
        return self._rows


def _freshness_service(documents, controlled):
    """``document_freshness`` issues exactly two queries: documents, then controlled."""
    db = SimpleNamespace(execute=AsyncMock(side_effect=[_Result(documents), _Result(controlled)]))
    return JobLifecycleService(db=db)


def _document(doc_id, *, status="approved", review_date=None, title="Doc", reference="PEL-1"):
    return SimpleNamespace(
        id=doc_id, status=status, review_date=review_date, title=title, reference_number=reference
    )


def _controlled(library_document_id, *, status="published", next_review_date=None):
    return SimpleNamespace(
        library_document_id=library_document_id, status=status, next_review_date=next_review_date
    )


@pytest.mark.asyncio
async def test_freshness_returns_an_item_per_requested_id_in_order():
    service = _freshness_service([_document(2), _document(1)], [])
    items = await service.document_freshness(tenant_id=1, library_document_ids=[1, 2, 1])
    assert [i["library_document_id"] for i in items] == [1, 2], "deduped, request order kept"


@pytest.mark.asyncio
async def test_freshness_reports_an_unseen_id_rather_than_dropping_it():
    """Omitting the id would render as a blank chip, which reads as 'fine'."""
    service = _freshness_service([], [])
    items = await service.document_freshness(tenant_id=1, library_document_ids=[404])
    assert items[0]["found"] is False
    assert items[0]["state"] == "unknown"
    assert items[0]["reason"] == "document_not_found"


@pytest.mark.asyncio
async def test_freshness_echoes_both_raw_statuses_alongside_the_verdict():
    service = _freshness_service(
        [_document(1, status="approved")], [_controlled(1, status="obsolete")]
    )
    item = (await service.document_freshness(tenant_id=1, library_document_ids=[1]))[0]
    assert item["library_status"] == "approved"
    assert item["controlled_status"] == "obsolete"
    assert item["state"] == "obsolete"
    JobDocumentFreshnessItem.model_validate(item)


@pytest.mark.asyncio
async def test_the_strictest_controlled_record_wins_when_several_point_at_one_document():
    """``library_document_id`` is not unique — the softest copy must not win."""
    service = _freshness_service(
        [_document(1)],
        [_controlled(1, status="published"), _controlled(1, status="obsolete")],
    )
    item = (await service.document_freshness(tenant_id=1, library_document_ids=[1]))[0]
    assert item["is_obsolete"] is True


@pytest.mark.asyncio
async def test_the_earliest_review_date_wins_between_non_obsolete_controlled_copies():
    service = _freshness_service(
        [_document(1)],
        [
            _controlled(1, next_review_date=NOW + timedelta(days=400)),
            _controlled(1, next_review_date=NOW - timedelta(days=1)),
        ],
    )
    item = (await service.document_freshness(tenant_id=1, library_document_ids=[1]))[0]
    assert item["state"] == "overdue"


@pytest.mark.asyncio
async def test_no_ids_short_circuits_without_touching_the_database():
    db = SimpleNamespace(execute=AsyncMock())
    assert await JobLifecycleService(db=db).document_freshness(tenant_id=1, library_document_ids=[]) == []
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_an_oversized_id_list_is_refused_not_silently_truncated():
    db = SimpleNamespace(execute=AsyncMock())
    service = JobLifecycleService(db=db)
    with pytest.raises(HTTPException) as exc_info:
        await service.document_freshness(
            tenant_id=1, library_document_ids=list(range(1, MAX_FRESHNESS_DOCUMENT_IDS + 2))
        )
    assert exc_info.value.status_code == 422
    db.execute.assert_not_called()


def test_freshness_response_schema_round_trips():
    response = JobDocumentFreshnessResponse(
        items=[
            JobDocumentFreshnessItem(
                library_document_id=1,
                found=True,
                state="unknown",
                reason="no_review_date",
                is_obsolete=False,
            )
        ],
        total=1,
    )
    assert response.items[0].title is None
    assert response.items[0].review_date is None


# ---------------------------------------------------------------------------
# Obsolete enforcement on attach
# ---------------------------------------------------------------------------


def _guard_service(*, existing_ids, freshness_items):
    service = JobLifecycleService(db=SimpleNamespace(execute=AsyncMock()))
    cell = SimpleNamespace(id=99) if existing_ids is not None else None
    service._find_cell = AsyncMock(return_value=cell)  # type: ignore[method-assign]
    service.db.execute = AsyncMock(return_value=_Result(existing_ids or []))
    seen: list[list[int]] = []

    async def _freshness(*, tenant_id, library_document_ids):
        _ = tenant_id
        seen.append(list(library_document_ids))
        return [i for i in freshness_items if i["library_document_id"] in set(library_document_ids)]

    service.document_freshness = _freshness  # type: ignore[method-assign]
    return service, seen


def _verdict_item(doc_id, *, obsolete, reason="obsolete_library_status", library_status="obsolete"):
    return {
        "library_document_id": doc_id,
        "found": True,
        "title": "Doc",
        "reference": "PEL-1",
        "library_status": library_status,
        "controlled_status": None,
        "state": "obsolete" if obsolete else "current",
        "reason": reason,
        "review_date": None,
        "is_obsolete": obsolete,
    }


@pytest.mark.asyncio
async def test_attaching_an_obsolete_document_is_refused():
    service, _ = _guard_service(existing_ids=[], freshness_items=[_verdict_item(7, obsolete=True)])
    with pytest.raises(HTTPException) as exc_info:
        await service._assert_no_obsolete_attachments(
            tenant_id=1, job_type_id=1, lane_id=2, step_id=3, requested_ids=[7]
        )
    assert exc_info.value.status_code == 422
    assert "Obsolete" in exc_info.value.detail
    assert "7" in exc_info.value.detail


@pytest.mark.asyncio
async def test_the_refusal_names_the_doc_control_status_when_that_is_the_source():
    item = _verdict_item(7, obsolete=True, reason="obsolete_controlled_status")
    item["controlled_status"] = "obsolete"
    item["library_status"] = "approved"
    service, _ = _guard_service(existing_ids=[], freshness_items=[item])
    with pytest.raises(HTTPException) as exc_info:
        await service._assert_no_obsolete_attachments(
            tenant_id=1, job_type_id=1, lane_id=2, step_id=3, requested_ids=[7]
        )
    assert "obsolete" in exc_info.value.detail


@pytest.mark.asyncio
async def test_an_already_attached_obsolete_document_stays_removable():
    """The whole point of checking only new ids.

    Document 7 went obsolete after it was attached. A PUT that keeps 7 and
    drops 8 must succeed, or the operator can never clear the cell.
    """
    service, checked = _guard_service(
        existing_ids=[7, 8], freshness_items=[_verdict_item(7, obsolete=True)]
    )
    await service._assert_no_obsolete_attachments(
        tenant_id=1, job_type_id=1, lane_id=2, step_id=3, requested_ids=[7]
    )
    assert checked == [], "no freshness lookup at all when nothing is being added"


@pytest.mark.asyncio
async def test_only_the_newly_added_ids_are_checked():
    service, checked = _guard_service(
        existing_ids=[7],
        freshness_items=[_verdict_item(7, obsolete=True), _verdict_item(9, obsolete=False)],
    )
    await service._assert_no_obsolete_attachments(
        tenant_id=1, job_type_id=1, lane_id=2, step_id=3, requested_ids=[7, 9]
    )
    assert checked == [[9]]


@pytest.mark.asyncio
async def test_a_cell_that_does_not_exist_yet_treats_every_id_as_new():
    service, checked = _guard_service(
        existing_ids=None, freshness_items=[_verdict_item(4, obsolete=False)]
    )
    await service._assert_no_obsolete_attachments(
        tenant_id=1, job_type_id=1, lane_id=2, step_id=3, requested_ids=[4]
    )
    assert checked == [[4]]


@pytest.mark.asyncio
async def test_clearing_a_cell_is_never_blocked():
    service, checked = _guard_service(existing_ids=[7], freshness_items=[])
    await service._assert_no_obsolete_attachments(
        tenant_id=1, job_type_id=1, lane_id=2, step_id=3, requested_ids=[]
    )
    assert checked == []


@pytest.mark.asyncio
async def test_the_guard_never_creates_a_cell_before_it_has_passed():
    """A failed guard must leave no row behind, so the lookup is read-only."""
    service, _ = _guard_service(existing_ids=None, freshness_items=[_verdict_item(7, obsolete=True)])
    create = AsyncMock()
    service._get_or_create_cell = create  # type: ignore[method-assign]
    with pytest.raises(HTTPException):
        await service._assert_no_obsolete_attachments(
            tenant_id=1, job_type_id=1, lane_id=2, step_id=3, requested_ids=[7]
        )
    create.assert_not_called()
