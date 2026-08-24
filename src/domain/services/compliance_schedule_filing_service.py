"""Compliance Schedule → Governance Library filing bridge (Wave 2).

ADR-0020 keeps filing a **separate, explicit** step. Completing an occurrence
records that the work happened; it does not put anything in the Library. This
module is that second step and is the only writer of ``library_document_id`` —
nothing on the completion path calls it, so ``complete`` can never imply
``filed``.

Two modes, chosen by the caller:

* **file** — promote an evidence asset already bound to the occurrence into the
  Library as a new document, under the taxonomy category the caller names.
* **link** — point the occurrence at a library document that already exists.

Only the file mode copies bytes between storage keys, and that copy is the one
step here that can fail for reasons the caller cannot correct. When it does,
the occurrence is left durably marked ``filing_failed`` with the reason, which
is what the ``filing_error`` column is for: a filing that silently did not
happen is indistinguishable from one that was never attempted.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import false, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import ConflictError, ExternalServiceError, NotFoundError, ValidationError
from src.domain.models.compliance_schedule import ComplianceFilingStatus, ComplianceRecord, ComplianceRequirement
from src.domain.models.document import Document, FileType, IndexJob
from src.domain.models.document_library import DocumentCategory
from src.domain.models.enums import DocumentStatus, DocumentType
from src.domain.models.evidence_asset import EvidenceAsset, EvidenceSourceModule
from src.domain.models.user import User
from src.domain.services.audit_service import record_audit_event
from src.domain.services.document_category_service import (
    allocate_pel_doc_ref,
    coerce_cascade_level,
    resolve_function_code,
)
from src.domain.services.document_library_filing_service import (
    assert_library_read_access,
    filing_defaults_for_category,
    find_duplicate_approved_candidates,
    load_filing_category,
)
from src.domain.services.document_version_service import document_version_service
from src.domain.services.index_job_service import maybe_create_filing_index_job
from src.domain.services.reference_number import ReferenceNumberService
from src.infrastructure.storage import StorageError, storage_service

logger = logging.getLogger(__name__)

# ``filing_error`` is TEXT, but a storage driver's message can carry a whole
# request trace. Truncated so one failure cannot make the record row unwieldy
# for every reader of it.
FILING_ERROR_MAX_CHARS = 1000


@dataclass(frozen=True)
class FilingResult:
    """Outcome of one filing attempt.

    ``duplicate_warning`` is carried out to the caller rather than stored on the
    occurrence: it describes the Library document, and the occurrence already
    has somewhere to point at that document.

    ``index_job`` is set only when File mode created a new Library document and
    ``COMPLIANCE_FILING_INDEX_ENABLED`` is on. Link mode never indexes. The
    caller must dispatch after commit (this service commits before returning).
    """

    record: ComplianceRecord
    document: Document
    duplicate_warning: bool
    duplicate_warning_detail: Optional[list[dict]]
    linked_existing: bool
    index_job: Optional[IndexJob] = None


def _safe_storage_filename(filename: Optional[str]) -> str:
    """Prevent path traversal within storage keys (mirrors the upload route)."""
    return (filename or "unnamed").replace("/", "_").replace("\\", "_")


def _file_type_for(filename: Optional[str]) -> FileType:
    """Narrow an evidence filename to a Library-storable file type.

    Evidence accepts more than the Library does — video, audio, CCTV pointers —
    so this is a genuine precondition rather than an internal invariant, and it
    fails as a validation error before anything is written or copied.
    """
    name = filename or ""
    extension = name.rsplit(".", 1)[-1].lower() if "." in name else ""
    try:
        return FileType(extension)
    except ValueError:
        raise ValidationError(
            f"Evidence file type '{extension or 'unknown'}' cannot be filed to the Library. "
            f"Supported: {', '.join(f.value for f in FileType)}",
            code="VALIDATION_ERROR",
        ) from None


async def _load_record_for_filing(
    db: AsyncSession,
    *,
    record_id: int,
    tenant_id: Optional[int],
) -> ComplianceRecord:
    """Tenant-scoped record fetch, locked for the duration of the filing.

    ``with_for_update`` serialises two concurrent file requests for the same
    occurrence so the second sees the first's ``filed`` state and is refused,
    rather than both creating a Library document and the loser's being orphaned
    by the winner's overwrite of ``library_document_id``.
    """
    query = select(ComplianceRecord).where(ComplianceRecord.id == record_id)
    # Fail closed, matching ``compliance_schedule_service._tenant_filter``.
    query = query.where(false()) if tenant_id is None else query.where(ComplianceRecord.tenant_id == tenant_id)
    result = await db.execute(query.with_for_update())
    record = result.scalar_one_or_none()
    if record is None:
        raise NotFoundError(
            f"Compliance record {record_id} not found",
            code="ENTITY_NOT_FOUND",
        )
    return record


async def _load_bound_evidence_asset(
    db: AsyncSession,
    *,
    evidence_asset_id: int,
    record: ComplianceRecord,
    tenant_id: int,
) -> EvidenceAsset:
    """Fetch an evidence asset only if it is already bound to this occurrence.

    Matching on ``source_module``/``source_id`` as well as tenant is the
    authorisation, not a convenience: without it, ``compliance_schedule:update``
    on any occurrence would be enough to copy an arbitrary asset id — an
    investigation photo, an HR record — into the Library under a category of the
    caller's choosing. Attach it to the occurrence first, then file it.
    """
    result = await db.execute(
        select(EvidenceAsset).where(
            EvidenceAsset.id == evidence_asset_id,
            EvidenceAsset.tenant_id == tenant_id,
            EvidenceAsset.deleted_at.is_(None),
            EvidenceAsset.source_module == EvidenceSourceModule.COMPLIANCE_RECORD,
            EvidenceAsset.source_id == str(record.id),
        )
    )
    asset = result.scalar_one_or_none()
    if asset is None:
        raise NotFoundError(
            f"Evidence asset {evidence_asset_id} is not attached to {record.reference_number}",
            code="ENTITY_NOT_FOUND",
            details={"evidence_asset_id": evidence_asset_id},
        )
    return asset


async def _load_linkable_document(
    db: AsyncSession,
    *,
    library_document_id: int,
    tenant_id: int,
    user: User,
) -> Document:
    """Fetch a library document the caller is allowed to see.

    The ACL check is deliberately the Library's own, not a compliance-side
    approximation: linking makes the document's id readable off the occurrence,
    so a caller who could not open the document must not be able to surface it
    here. ``assert_library_read_access`` answers 404 rather than 403 for a denied
    read, which is the Library's existing choice and is kept.
    """
    result = await db.execute(
        select(Document).where(
            Document.id == library_document_id,
            Document.tenant_id == tenant_id,
        )
    )
    document = result.scalar_one_or_none()
    if document is None:
        raise NotFoundError(
            f"Library document {library_document_id} not found",
            code="ENTITY_NOT_FOUND",
        )

    # ``Document.category`` is a free-text string, so the RBAC helper cannot
    # reach the taxonomy id through it. Resolve the real category row and pass
    # the id explicitly, otherwise every restricted document fails closed and
    # even an entitled caller is told it does not exist.
    taxonomy_id: Optional[str] = None
    if document.category_id is not None:
        category = await db.get(DocumentCategory, document.category_id)
        taxonomy_id = getattr(category, "taxonomy_id", None)
    assert_library_read_access(document, user, taxonomy_id=taxonomy_id)
    return document


async def _mark_filing_failed(
    db: AsyncSession,
    *,
    record_id: int,
    tenant_id: int,
    user_id: int,
    message: str,
) -> None:
    """Roll back the attempt, then durably record that it failed.

    A separate transaction on purpose. The rollback is what discards the
    half-built document row and releases the PEL sequence; the write after it is
    the only thing that survives, so whoever looks at the occurrence next sees
    ``filing_failed`` and the reason instead of an unexplained ``not_filed``.

    Requires a session from ``get_db``. The tenant GUC is transaction-local
    (``set_config(..., true)``), so the rollback discards it, and the re-read
    below only sees the row because ``get_db`` re-applies the GUC on every
    ``after_begin``. Called with a bare ``async_session_maker()`` session — from
    a Celery task, say — this would find nothing under FORCE RLS and record
    nothing, and the failure it was called to make visible would vanish.
    """
    await db.rollback()
    result = await db.execute(
        select(ComplianceRecord).where(
            ComplianceRecord.id == record_id,
            ComplianceRecord.tenant_id == tenant_id,
        )
    )
    record = result.scalar_one_or_none()
    if record is None:
        return
    record.filing_status = ComplianceFilingStatus.FILING_FAILED
    record.filing_error = message[:FILING_ERROR_MAX_CHARS]
    record.updated_by_id = user_id
    await db.commit()


async def file_record_to_library(
    db: AsyncSession,
    *,
    record_id: int,
    tenant_id: int,
    user: User,
    evidence_asset_id: Optional[int] = None,
    category_id: Optional[int] = None,
    function_code: Optional[str] = None,
    cascade_level: Optional[int] = None,
    library_document_id: Optional[int] = None,
    title: Optional[str] = None,
) -> FilingResult:
    """File one occurrence's evidence into the Governance Library.

    Exactly one of ``evidence_asset_id`` (with ``category_id``) or
    ``library_document_id`` must be given; the request schema enforces that, and
    this function repeats the check because it is also reachable from tests and
    scripts.

    ``function_code`` is the owning function the PEL reference is drawn from
    (ADR-0023). It is optional: without it the filed document gets no
    ``pel_doc_ref``, because deriving a function from the evidence would print
    an immutable reference nobody confirmed.

    ``cascade_level`` (NS-1) is the band the reference is drawn from and is
    required whenever ``function_code`` is given. Filed evidence is very often
    a level-5 record, but "very often" is not "always" — a filed contractor
    method statement is a level-4 document — so the level is confirmed by the
    filer rather than defaulted here. A defaulted band would print an
    immutable reference that misplaces the document in the cascade.
    """
    if (evidence_asset_id is None) == (library_document_id is None):
        raise ValidationError(
            "Filing needs exactly one of evidence_asset_id or library_document_id",
            code="VALIDATION_ERROR",
        )

    record = await _load_record_for_filing(db, record_id=record_id, tenant_id=tenant_id)

    if record.filing_status == ComplianceFilingStatus.FILED and record.library_document_id is not None:
        raise ConflictError(
            f"{record.reference_number} is already filed to library document {record.library_document_id}",
            code="DUPLICATE_ENTITY",
            details={"library_document_id": record.library_document_id},
        )

    if library_document_id is not None:
        document = await _load_linkable_document(
            db,
            library_document_id=library_document_id,
            tenant_id=tenant_id,
            user=user,
        )
        duplicate_warning = False
        duplicate_warning_detail: Optional[list[dict]] = None
        linked_existing = True
        index_job = None
    else:
        if evidence_asset_id is None or category_id is None:
            raise ValidationError(
                "Filing an evidence asset needs both evidence_asset_id and category_id",
                code="VALIDATION_ERROR",
            )
        document, duplicate_warning, duplicate_warning_detail = await _create_library_document(
            db,
            record=record,
            tenant_id=tenant_id,
            user=user,
            evidence_asset_id=evidence_asset_id,
            category_id=category_id,
            function_code=function_code,
            cascade_level=cascade_level,
            title=title,
        )
        linked_existing = False
        # Same commit as the Document row — Celery must not see the job early.
        index_job = await maybe_create_filing_index_job(
            db,
            document=document,
            created_by_id=user.id,
        )

    record.library_document_id = document.id
    record.filing_status = ComplianceFilingStatus.FILED
    record.filing_error = None
    record.updated_by_id = user.id

    await record_audit_event(
        db=db,
        event_type="compliance_schedule.record_filed",
        entity_type="compliance_record",
        entity_id=str(record.id),
        entity_name=record.reference_number,
        action="update",
        description=(
            f"Filed {record.reference_number} to library document {document.id}"
            f"{' (linked existing)' if linked_existing else ''}"
        ),
        payload={
            "library_document_id": document.id,
            "pel_doc_ref": getattr(document, "pel_doc_ref", None),
            "evidence_asset_id": evidence_asset_id,
            "category_id": category_id,
            "function_code": function_code,
            "cascade_level": cascade_level,
            "linked_existing": linked_existing,
            "index_job_id": index_job.id if index_job is not None else None,
        },
        user_id=user.id,
        actor_user_id=user.id,
        changed_fields=["library_document_id", "filing_status"],
        tenant_id=tenant_id,
    )

    await db.commit()
    await db.refresh(record)
    return FilingResult(
        record=record,
        document=document,
        duplicate_warning=duplicate_warning,
        duplicate_warning_detail=duplicate_warning_detail,
        linked_existing=linked_existing,
        index_job=index_job,
    )


async def _create_library_document(
    db: AsyncSession,
    *,
    record: ComplianceRecord,
    tenant_id: int,
    user: User,
    evidence_asset_id: int,
    category_id: int,
    function_code: Optional[str],
    cascade_level: Optional[int],
    title: Optional[str],
) -> tuple[Document, bool, Optional[list[dict]]]:
    """Copy a bound evidence asset into the Library as a new draft document."""
    asset = await _load_bound_evidence_asset(
        db,
        evidence_asset_id=evidence_asset_id,
        record=record,
        tenant_id=tenant_id,
    )
    category = await load_filing_category(db, category_id)
    # Resolved before the storage download so an unknown function code fails the
    # request cheaply rather than after a file has been copied.
    filing_function = await resolve_function_code(db, function_code)
    if filing_function is not None and cascade_level is None:
        raise ValidationError(
            "cascade_level is required when function_code is supplied: the PEL "
            "reference is banded by cascade level and cannot be re-banded once "
            "issued (NS-1 / R02).",
            code="VALIDATION_ERROR",
        )
    file_type = _file_type_for(asset.original_filename)

    requirement = await _load_requirement(db, requirement_id=record.requirement_id, tenant_id=tenant_id)
    doc_title = title or asset.title or asset.original_filename or f"{record.reference_number} evidence"

    try:
        content = await storage_service().download(asset.storage_key)
    except StorageError as exc:
        await _mark_filing_failed(
            db,
            record_id=record.id,
            tenant_id=tenant_id,
            user_id=user.id,
            message=f"Could not read evidence {asset.storage_key}: {exc}",
        )
        logger.warning("compliance filing could not read evidence asset=%s: %s", evidence_asset_id, exc)
        raise ExternalServiceError(
            "Could not read the evidence file from storage; the occurrence is marked filing_failed.",
            code="EXTERNAL_SERVICE_ERROR",
        ) from exc

    reference_number = await ReferenceNumberService.generate(db, "document", Document)
    # ``coerce_cascade_level`` rather than the caller-supplied value directly:
    # the guard above already refuses a function with no level, but that guard
    # tests ``filing_function``, so nothing here would otherwise stop a None
    # reaching the allocator if that guard were ever moved or weakened.
    pel_doc_ref = (
        await allocate_pel_doc_ref(db, filing_function.id, coerce_cascade_level(cascade_level))
        if filing_function is not None
        else None
    )
    defaults = filing_defaults_for_category(category)

    site_location_id = getattr(requirement, "location_id", None)
    duplicates = await find_duplicate_approved_candidates(
        db,
        tenant_id=tenant_id,
        category_id=category_id,
        site_location_id=site_location_id,
        title=doc_title,
    )
    duplicate_warning_detail = (
        [
            {
                "document_id": d.document_id,
                "title": d.title,
                "reference_number": d.reference_number,
                "pel_doc_ref": d.pel_doc_ref,
            }
            for d in duplicates
        ]
        if duplicates
        else None
    )

    file_name = asset.original_filename or f"{record.reference_number}.{file_type.value}"
    storage_key = (
        f"documents/{datetime.now(timezone.utc).strftime('%Y/%m')}/"
        f"{uuid.uuid4()}/{_safe_storage_filename(file_name)}"
    )

    document = Document(
        tenant_id=tenant_id,
        title=doc_title,
        description=(
            f"Filed from Compliance Schedule occurrence {record.reference_number} "
            f"(due {record.due_date.isoformat()})."
        ),
        file_name=file_name,
        file_type=file_type,
        file_size=len(content),
        file_path=storage_key,
        mime_type=asset.content_type,
        # Lands as a draft, exactly as a category-filed upload does. Filing puts
        # the evidence in the Library; it does not approve or publish it, and
        # claiming otherwise would let an occurrence assert a governance state
        # nobody reviewed.
        document_type=DocumentType.RECORD,
        status=DocumentStatus.DRAFT,
        version="1.0",
        reference_number=reference_number,
        category_id=category_id,
        pel_doc_ref=pel_doc_ref,
        function_id=filing_function.id if filing_function is not None else None,
        cascade_level=cascade_level,
        site_location_id=site_location_id,
        access_level=defaults.access_level,
        is_statutory=defaults.is_statutory,
        duplicate_warning=bool(duplicates),
        duplicate_warning_detail=duplicate_warning_detail,
        created_by_id=user.id,
    )
    db.add(document)
    await db.flush()

    db.add(
        document_version_service.build_initial_library_version(
            document,
            created_by_id=user.id,
            change_notes=f"Filed from compliance record {record.reference_number}",
        )
    )

    try:
        await storage_service().upload(
            storage_key=storage_key,
            content=content,
            content_type=asset.content_type or "application/octet-stream",
            metadata={
                "document_id": str(document.id),
                "tenant_id": str(tenant_id),
                "uploaded_by": str(user.id),
                "file_name": file_name,
                "compliance_record_id": str(record.id),
            },
        )
    except StorageError as exc:
        await _mark_filing_failed(
            db,
            record_id=record.id,
            tenant_id=tenant_id,
            user_id=user.id,
            message=f"Could not write library copy to {storage_key}: {exc}",
        )
        logger.warning("compliance filing could not write library copy for record=%s: %s", record.id, exc)
        raise ExternalServiceError(
            "Could not store the Library copy of the evidence; the occurrence is marked filing_failed.",
            code="EXTERNAL_SERVICE_ERROR",
        ) from exc

    return document, bool(duplicates), duplicate_warning_detail


async def _load_requirement(
    db: AsyncSession,
    *,
    requirement_id: int,
    tenant_id: int,
) -> Optional[ComplianceRequirement]:
    result = await db.execute(
        select(ComplianceRequirement).where(
            ComplianceRequirement.id == requirement_id,
            ComplianceRequirement.tenant_id == tenant_id,
        )
    )
    return result.scalar_one_or_none()
