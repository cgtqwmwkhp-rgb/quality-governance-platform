"""Unit tests for the Compliance Schedule → Governance Library filing bridge.

Covers the decisions the bridge makes on its own: which requests it refuses,
which evidence it will and will not copy, and what it leaves behind on the
occurrence when the storage copy fails. The end-to-end happy paths are in
``tests/integration/test_compliance_schedule_filing_api.py``, where a real
database can show that the row actually changed.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.domain.exceptions import ConflictError, ExternalServiceError, NotFoundError, ValidationError
from src.domain.models.compliance_schedule import (
    ComplianceFilingStatus,
    ComplianceRecord,
    ComplianceRecordOutcome,
    ComplianceRequirement,
    ComplianceScheduleAnchor,
)
from src.domain.services import compliance_schedule_filing_service as filing
from src.infrastructure.storage import StorageError

MODULE = "src.domain.services.compliance_schedule_filing_service"


def _result(scalar=None):
    result = MagicMock()
    result.scalar_one_or_none.return_value = scalar
    return result


@pytest.fixture
def db():
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.get = AsyncMock(return_value=None)
    return session


@pytest.fixture
def user():
    return SimpleNamespace(id=7, tenant_id=1, is_superuser=False, has_permission=lambda _p: True)


def _record(**overrides) -> ComplianceRecord:
    values = dict(
        id=55,
        tenant_id=1,
        external_id="ext-55",
        reference_number="CRC-2026-0001",
        requirement_id=10,
        due_date=date(2026, 4, 1),
        outcome=ComplianceRecordOutcome.COMPLETED,
        completed_at=datetime(2026, 4, 2, tzinfo=timezone.utc),
        filing_status=ComplianceFilingStatus.NOT_FILED,
        library_document_id=None,
        filing_error=None,
    )
    values.update(overrides)
    return ComplianceRecord(**values)


def _requirement() -> ComplianceRequirement:
    return ComplianceRequirement(
        id=10,
        tenant_id=1,
        external_id="ext-10",
        reference_number="CSR-2026-0001",
        title="Fire Risk Assessment",
        taxonomy_id="03.01",
        frequency_months=12,
        frequency_days=None,
        anchor=ComplianceScheduleAnchor.SCHEDULE,
        statutory=True,
        next_due_date=date(2027, 4, 1),
        location_id=None,
        is_active=True,
    )


def _asset(filename: str = "fra-2026.pdf") -> SimpleNamespace:
    return SimpleNamespace(
        id=99,
        tenant_id=1,
        storage_key="evidence/compliance_record/55/abc_fra-2026.pdf",
        original_filename=filename,
        content_type="application/pdf",
        title="FRA 2026",
    )


def _category() -> SimpleNamespace:
    return SimpleNamespace(id=4, taxonomy_id="03.01", default_access="managers", name="Fire Safety", active=True)


# ---------------------------------------------------------------------------
# Mode selection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kwargs",
    [
        {},
        {"evidence_asset_id": 99, "category_id": 4, "library_document_id": 3},
    ],
    ids=["neither-mode", "both-modes"],
)
async def test_requires_exactly_one_mode(db, user, kwargs):
    """Refused before any lookup, so an ambiguous request files nothing."""
    with pytest.raises(ValidationError):
        await filing.file_record_to_library(db, record_id=55, tenant_id=1, user=user, **kwargs)
    db.execute.assert_not_called()


@pytest.mark.asyncio
async def test_evidence_mode_without_category_is_refused(db, user):
    db.execute = AsyncMock(return_value=_result(_record()))
    with pytest.raises(ValidationError, match="category_id"):
        await filing.file_record_to_library(
            db,
            record_id=55,
            tenant_id=1,
            user=user,
            evidence_asset_id=99,
        )


# ---------------------------------------------------------------------------
# Tenancy and re-filing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_from_another_tenant_is_not_found(db, user):
    """The scoped query returns nothing, and nothing is disclosed about why."""
    db.execute = AsyncMock(return_value=_result(None))
    with pytest.raises(NotFoundError):
        await filing.file_record_to_library(
            db,
            record_id=55,
            tenant_id=2,
            user=user,
            library_document_id=3,
        )


@pytest.mark.asyncio
async def test_already_filed_record_is_refused(db, user):
    """Re-filing would orphan the first document behind an overwritten id."""
    record = _record(filing_status=ComplianceFilingStatus.FILED, library_document_id=1234)
    db.execute = AsyncMock(return_value=_result(record))

    with pytest.raises(ConflictError) as excinfo:
        await filing.file_record_to_library(
            db,
            record_id=55,
            tenant_id=1,
            user=user,
            library_document_id=3,
        )
    # The caller needs to be able to go and look at what is already filed.
    assert excinfo.value.details["library_document_id"] == 1234


@pytest.mark.asyncio
async def test_a_previous_failure_can_be_retried(db, user):
    """``filing_failed`` is a retryable state, unlike ``filed``."""
    record = _record(filing_status=ComplianceFilingStatus.FILING_FAILED, filing_error="storage down")
    document = SimpleNamespace(id=321, tenant_id=1, category_id=None, access_level="all_staff", pel_doc_ref=None)
    db.execute = AsyncMock(side_effect=[_result(record), _result(document)])

    with patch(f"{MODULE}.record_audit_event", new=AsyncMock()):
        result = await filing.file_record_to_library(
            db,
            record_id=55,
            tenant_id=1,
            user=user,
            library_document_id=321,
        )

    assert result.record.filing_status == ComplianceFilingStatus.FILED
    assert result.record.library_document_id == 321
    # The stale reason must not survive a successful retry.
    assert result.record.filing_error is None


# ---------------------------------------------------------------------------
# Evidence must already belong to this occurrence
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_evidence_not_attached_to_this_occurrence_is_refused(db, user):
    """The source_module/source_id match is the authorisation, not a filter.

    Without it, ``compliance_schedule:update`` would be enough to copy any asset
    id in the tenant into the Library.
    """
    db.execute = AsyncMock(side_effect=[_result(_record()), _result(None)])

    with pytest.raises(NotFoundError, match="not attached"):
        await filing.file_record_to_library(
            db,
            record_id=55,
            tenant_id=1,
            user=user,
            evidence_asset_id=99,
            category_id=4,
        )
    db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_evidence_query_is_scoped_to_module_and_record(db, user):
    """Prove the WHERE clause carries the binding, not just that a row was used."""
    db.execute = AsyncMock(side_effect=[_result(_record()), _result(None)])

    with pytest.raises(NotFoundError):
        await filing.file_record_to_library(
            db,
            record_id=55,
            tenant_id=1,
            user=user,
            evidence_asset_id=99,
            category_id=4,
        )

    asset_query = str(db.execute.await_args_list[1].args[0])
    assert "evidence_assets.source_module" in asset_query
    assert "evidence_assets.source_id" in asset_query
    assert "evidence_assets.tenant_id" in asset_query


@pytest.mark.asyncio
async def test_unfilable_evidence_type_is_refused_without_touching_the_record(db, user):
    """Evidence accepts video; the Library does not. Refuse before any write."""
    record = _record()
    db.execute = AsyncMock(side_effect=[_result(record), _result(_asset("walkaround.mp4"))])

    with patch(f"{MODULE}.load_filing_category", new=AsyncMock(return_value=_category())):
        with pytest.raises(ValidationError, match="mp4"):
            await filing.file_record_to_library(
                db,
                record_id=55,
                tenant_id=1,
                user=user,
                evidence_asset_id=99,
                category_id=4,
            )

    # A precondition the caller can correct is not a filing failure.
    assert record.filing_status == ComplianceFilingStatus.NOT_FILED
    assert record.filing_error is None
    db.commit.assert_not_called()


# ---------------------------------------------------------------------------
# Storage failures leave a durable, readable reason
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unreadable_evidence_marks_the_occurrence_filing_failed(db, user):
    record = _record()
    db.execute = AsyncMock(
        side_effect=[
            _result(record),  # locked record
            _result(_asset()),  # bound evidence asset
            _result(_requirement()),  # requirement (site + description)
            _result(record),  # re-read inside _mark_filing_failed
        ]
    )
    storage = MagicMock()
    storage.download = AsyncMock(side_effect=StorageError("blob 404"))

    with (
        patch(f"{MODULE}.load_filing_category", new=AsyncMock(return_value=_category())),
        patch(f"{MODULE}.storage_service", return_value=storage),
    ):
        with pytest.raises(ExternalServiceError):
            await filing.file_record_to_library(
                db,
                record_id=55,
                tenant_id=1,
                user=user,
                evidence_asset_id=99,
                category_id=4,
            )

    db.rollback.assert_awaited()
    assert record.filing_status == ComplianceFilingStatus.FILING_FAILED
    assert "blob 404" in record.filing_error
    assert record.library_document_id is None
    db.commit.assert_awaited()


@pytest.mark.asyncio
async def test_failed_library_write_marks_filing_failed_and_files_nothing(db, user):
    """The document row is rolled back, so a half-filed document cannot linger."""
    record = _record()
    db.execute = AsyncMock(
        side_effect=[
            _result(record),
            _result(_asset()),
            _result(_requirement()),
            _result(record),
        ]
    )
    storage = MagicMock()
    storage.download = AsyncMock(return_value=b"%PDF-1.7 evidence")
    storage.upload = AsyncMock(side_effect=StorageError("container missing"))

    with (
        patch(f"{MODULE}.load_filing_category", new=AsyncMock(return_value=_category())),
        patch(f"{MODULE}.storage_service", return_value=storage),
        patch(f"{MODULE}.ReferenceNumberService.generate", new=AsyncMock(return_value="DOC-2026-0001")),
        patch(f"{MODULE}.allocate_pel_doc_ref", new=AsyncMock(return_value="PEL-HSE-01-004")),
        patch(f"{MODULE}.find_duplicate_approved_candidates", new=AsyncMock(return_value=[])),
    ):
        with pytest.raises(ExternalServiceError):
            await filing.file_record_to_library(
                db,
                record_id=55,
                tenant_id=1,
                user=user,
                evidence_asset_id=99,
                category_id=4,
            )

    db.rollback.assert_awaited()
    assert record.filing_status == ComplianceFilingStatus.FILING_FAILED
    assert "container missing" in record.filing_error
    assert record.library_document_id is None


@pytest.mark.asyncio
async def test_filing_error_is_truncated(db, user):
    """A driver traceback must not make the record row unreadable for everyone."""
    record = _record()
    db.execute = AsyncMock(
        side_effect=[
            _result(record),
            _result(_asset()),
            _result(_requirement()),
            _result(record),
        ]
    )
    storage = MagicMock()
    storage.download = AsyncMock(side_effect=StorageError("x" * 5000))

    with (
        patch(f"{MODULE}.load_filing_category", new=AsyncMock(return_value=_category())),
        patch(f"{MODULE}.storage_service", return_value=storage),
    ):
        with pytest.raises(ExternalServiceError):
            await filing.file_record_to_library(
                db,
                record_id=55,
                tenant_id=1,
                user=user,
                evidence_asset_id=99,
                category_id=4,
            )

    assert len(record.filing_error) == filing.FILING_ERROR_MAX_CHARS


# ---------------------------------------------------------------------------
# Link mode
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_linking_a_document_the_caller_cannot_read_is_not_found(db, user):
    """404 rather than 403, matching the Library's own read ACL behaviour."""
    record = _record()
    restricted = SimpleNamespace(
        id=321,
        tenant_id=1,
        category_id=8,
        access_level="restricted",
    )
    db.execute = AsyncMock(side_effect=[_result(record), _result(restricted)])
    db.get = AsyncMock(return_value=SimpleNamespace(taxonomy_id="02.08"))

    denied = SimpleNamespace(id=7, is_superuser=False, has_permission=lambda _p: False)

    with pytest.raises(NotFoundError):
        await filing.file_record_to_library(
            db,
            record_id=55,
            tenant_id=1,
            user=denied,
            library_document_id=321,
        )
    assert record.filing_status == ComplianceFilingStatus.NOT_FILED


@pytest.mark.asyncio
async def test_linking_resolves_the_taxonomy_id_for_the_acl(db, user):
    """``Document.category`` is free text, so the ACL needs the category row.

    Reading the taxonomy id off the string column returns None, which makes the
    RBAC helper fail closed and hides restricted documents from callers who are
    entitled to them.
    """
    record = _record()
    restricted = SimpleNamespace(id=321, tenant_id=1, category_id=8, access_level="restricted", pel_doc_ref=None)
    db.execute = AsyncMock(side_effect=[_result(record), _result(restricted)])
    db.get = AsyncMock(return_value=SimpleNamespace(taxonomy_id="02.08"))

    entitled = SimpleNamespace(
        id=7,
        is_superuser=False,
        has_permission=lambda p: p == "document:restricted:oh",
    )

    with patch(f"{MODULE}.record_audit_event", new=AsyncMock()):
        result = await filing.file_record_to_library(
            db,
            record_id=55,
            tenant_id=1,
            user=entitled,
            library_document_id=321,
        )

    assert result.linked_existing is True
    assert result.record.filing_status == ComplianceFilingStatus.FILED


@pytest.mark.asyncio
async def test_linking_a_document_from_another_tenant_is_not_found(db, user):
    record = _record()
    db.execute = AsyncMock(side_effect=[_result(record), _result(None)])

    with pytest.raises(NotFoundError, match="Library document"):
        await filing.file_record_to_library(
            db,
            record_id=55,
            tenant_id=1,
            user=user,
            library_document_id=321,
        )

    document_query = str(db.execute.await_args_list[1].args[0])
    assert "documents.tenant_id" in document_query
