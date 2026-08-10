"""
Advanced Document Control API Routes

Provides endpoints for:
- Document CRUD with version control
- Approval workflows
- Distribution management
- Obsolete document handling
- Access tracking
"""

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.utils.tenant import apply_tenant_filter, require_tenant_id
from src.domain.exceptions import (
    ConflictError,
    FeatureNotProvisionedError,
    MeasurementUnavailableError,
    NotFoundError,
    ValidationError,
)
from src.domain.models.document_control import (
    ControlledDocument,
    ControlledDocumentVersion,
    DocumentAccessLog,
    DocumentApprovalAction,
    DocumentApprovalInstance,
    DocumentApprovalWorkflow,
    DocumentDistribution,
    ObsoleteDocumentRecord,
)
from src.domain.models.user import User
from src.domain.services.document_version_service import assert_document_metadata_editable, document_version_service
from src.domain.services.gkb_golden_thread import GoldenThreadContext, decide_golden_thread_publish
from src.domain.services.legal_hold_enforcement import assert_controlled_document_not_held
from src.domain.services.library_rules import LIBRARY_ACCESS_LEVELS, normalize_access_level
from src.domain.services.schema_presence import absent_tables

router = APIRouter()
logger = logging.getLogger(__name__)


# ============ Tables this module reads that production does not have ============
#
# Seven of the tables backing this router have no create migration; their absence
# from production was read from ``information_schema`` there. They exist in every
# test database — both CI harnesses build their schema with
# ``Base.metadata.create_all`` — and in no deployment, which is why no gate here
# has ever failed on endpoints that cannot have been working.
# All seven are on the deferral register at
# ``docs/governance/alembic_check_excluded_tables.md`` marked "migration coverage
# pending", so the honest statement is not "temporarily broken" but "never built".
#
# Named per read rather than as one set, because the endpoints diverge: the
# document-detail read needs two of them and is still worth answering without
# either, whereas a distribution write needs exactly one and cannot be answered
# at all without it. A single shared tuple would make every surface as
# unavailable as the least available one.
#
# ``docs/ops/absent-table-disclosure.md`` maps each name to the surfaces above it.

APPROVAL_WORKFLOW_TABLES: tuple[str, ...] = (DocumentApprovalWorkflow.__tablename__,)
APPROVAL_INSTANCE_TABLES: tuple[str, ...] = (
    DocumentApprovalInstance.__tablename__,
    DocumentApprovalAction.__tablename__,
)
DISTRIBUTION_TABLES: tuple[str, ...] = (DocumentDistribution.__tablename__,)
ACCESS_LOG_TABLES: tuple[str, ...] = (DocumentAccessLog.__tablename__,)
OBSOLETE_RECORD_TABLES: tuple[str, ...] = (ObsoleteDocumentRecord.__tablename__,)


async def _refuse_write_if_unprovisioned(db: AsyncSession, tables: tuple[str, ...], what: str) -> None:
    """Refuse a write whose table is absent, before the transaction is poisoned.

    Raises :class:`FeatureNotProvisionedError` rather than letting the INSERT
    fail. Two reasons beyond the message being better: on PostgreSQL the failed
    statement aborts the transaction, so any legitimate change staged alongside it
    is lost to ``InFailedSqlTransaction`` at commit rather than to a clear error;
    and the same absent table raises a different exception class on SQLite, so
    there is no one thing to catch.
    """
    absent = await absent_tables(db, tables)
    if not absent:
        return

    logger.error("%s cannot be recorded — absent tables: %s", what, ", ".join(absent))
    raise FeatureNotProvisionedError(
        f"{what} cannot be recorded because {', '.join(absent)} "
        f"{'is' if len(absent) == 1 else 'are'} absent from this database. "
        "Nothing was saved. This feature has no create-migration yet, so retrying "
        "will not help until one is deployed.",
        missing_tables=absent,
    )


async def _refuse_read_if_unmeasurable(db: AsyncSession, tables: tuple[str, ...], what: str) -> None:
    """Refuse a read whose only source is absent, rather than answering ``[]``.

    An empty list is reserved for a table that was read and found empty. For a
    list endpoint absence is inherently coercible to empty — every defensive
    client writes ``items ?? []`` — so the only signal a consumer cannot flatten
    back into "there is nothing" is not-a-success.
    """
    absent = await absent_tables(db, tables)
    if not absent:
        return

    logger.error("%s is unreadable — absent tables: %s", what, ", ".join(absent))
    raise MeasurementUnavailableError(
        f"{what} cannot be listed because {', '.join(absent)} "
        f"{'is' if len(absent) == 1 else 'are'} absent from this database. "
        "This is not a report that there are none.",
        missing_tables=absent,
    )


def _utcnow() -> datetime:
    """Current UTC instant as a naive datetime, matching this module's columns.

    Every ``DateTime`` column in ``src/domain/models/document_control.py`` is
    declared without ``timezone=True``, so Postgres stores them as ``timestamp
    without time zone``. asyncpg refuses to adapt an aware datetime for such a
    column and raises ``DataError: can't subtract offset-naive and offset-aware
    datetimes``, which surfaces as a 500 — it does not silently coerce, and
    SQLite does not reproduce it, so this only ever fails against Postgres.

    ``document_version_service`` already writes these columns via the same
    ``.replace(tzinfo=None)``; this keeps the routes consistent with both it and
    the models' own column defaults. Do not "fix" this by making the value aware:
    the column type is what defines the contract, and changing it is a migration.
    """
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _tenant_id(current_user: CurrentUser) -> int:
    """Return the authenticated tenant or reject unscoped document-control access."""
    return require_tenant_id(getattr(current_user, "tenant_id", None))


def _tenant_stmt(stmt: Any, model: Any, current_user: CurrentUser) -> Any:
    """Scope a statement to the exact authenticated tenant."""
    return apply_tenant_filter(stmt, model, _tenant_id(current_user))


# ============ Pydantic Schemas ============


class DocumentCreate(BaseModel):
    #: WC-1 / L-01d — the Register row this control record governs. Optional so
    #: the existing Document Control page keeps working while the in-app "bring
    #: under control" journey (L-18c) is built; supplying it is what folds the
    #: control record onto the one Register instead of starting a second home.
    library_document_id: Optional[int] = Field(default=None, ge=1)
    title: str = Field(..., min_length=5, max_length=500)
    description: Optional[str] = None
    document_type: str = Field(..., description="policy, procedure, work_instruction, etc.")
    category: str = Field(...)
    subcategory: Optional[str] = None
    department: Optional[str] = None
    author_name: Optional[str] = None
    owner_name: Optional[str] = None
    review_frequency_months: int = Field(default=12, ge=1, le=60)
    relevant_standards: Optional[list[str]] = None
    relevant_clauses: Optional[list[str]] = None
    #: CUT-1 / F-7 §3 — the one Library vocabulary. The old `internal` default
    #: was a second vocabulary for the same fact; it is still accepted and folds
    #: onto `all_staff`, but a control record anchored to a Register row takes
    #: that row's level instead, because the Register is the access SoR.
    access_level: str = Field(default="all_staff")
    is_confidential: bool = False
    training_required: bool = False


class DocumentUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    department: Optional[str] = None
    owner_name: Optional[str] = None
    review_frequency_months: Optional[int] = None
    relevant_standards: Optional[list[str]] = None
    relevant_clauses: Optional[list[str]] = None
    access_level: Optional[str] = None
    is_confidential: Optional[bool] = None
    training_required: Optional[bool] = None


class VersionCreate(BaseModel):
    change_summary: str = Field(..., min_length=10, max_length=2000)
    change_reason: Optional[str] = None
    change_type: str = Field(default="revision", description="new, revision, amendment")
    is_major_version: bool = False


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=5, max_length=255)
    description: Optional[str] = None
    applicable_document_types: list[str] = Field(...)
    applicable_categories: Optional[list[str]] = None
    applicable_departments: Optional[list[str]] = None
    workflow_steps: list[dict] = Field(...)
    allow_parallel_approval: bool = False
    require_all_approvals: bool = True
    auto_escalate_after_days: Optional[int] = None


class ApprovalActionRequest(BaseModel):
    """Approval workflow action body.

    ``extra="forbid"`` so a misspelled or unsupported field fails loudly instead
    of the action succeeding while the unknown key is silently dropped (B-10).
    """

    model_config = ConfigDict(extra="forbid")

    action: str = Field(..., description="approved, rejected, returned, delegated")
    comments: Optional[str] = None
    conditions: Optional[str] = None
    delegated_to: Optional[int] = None


class DistributionCreate(BaseModel):
    recipient_type: str = Field(..., description="user, department, role, external")
    recipient_id: Optional[int] = None
    recipient_name: str = Field(...)
    recipient_email: Optional[str] = None
    distribution_type: str = Field(default="controlled")
    copy_number: Optional[str] = None
    acknowledgment_required: bool = True


class ObsoleteRequest(BaseModel):
    """Mark-document-obsolete body.

    ``extra="forbid"`` so a misspelled or unsupported field fails loudly instead
    of obsolescence succeeding while the unknown key is silently dropped (B-10).
    """

    model_config = ConfigDict(extra="forbid")

    obsolete_reason: str = Field(..., min_length=10)
    superseded_by_id: Optional[int] = None


async def _assert_anchor_is_available(
    db: AsyncSession,
    *,
    tenant_id: int,
    library_document_id: int,
) -> None:
    """Refuse an anchor that is not this tenant's Register row, or already taken.

    Two refusals, both L-01d (one Register, enhance never replicate):

    * A document id from another tenant, or none at all, would create a control
      record whose golden thread points at nothing readable — which is worse than
      an unanchored one, because ``relationship_state`` would report ``linked``.
    * A second control record on the same Register row is a twin control register
      for that document. There is no product question a second one answers, and
      the Register projection would have to pick between them.
    """
    from src.domain.models.document import Document as LibraryDocument

    library_document = await db.scalar(
        select(LibraryDocument.id).where(
            LibraryDocument.id == library_document_id,
            LibraryDocument.tenant_id == tenant_id,
        )
    )
    if library_document is None:
        raise NotFoundError(
            f"Register document {library_document_id} was not found in this tenant.",
            details={"library_document_id": library_document_id},
        )

    existing = await db.scalar(
        select(ControlledDocument.id).where(
            ControlledDocument.tenant_id == tenant_id,
            ControlledDocument.library_document_id == library_document_id,
        )
    )
    if existing is not None:
        raise ConflictError(
            f"Register document {library_document_id} is already under control as controlled document {existing}.",
            code="CONTROL_RECORD_EXISTS",
            details={"library_document_id": library_document_id, "controlled_document_id": existing},
        )


async def _register_access_level(
    db: AsyncSession,
    *,
    tenant_id: int,
    library_document_id: int,
) -> Optional[str]:
    """The anchored Register row's access level — the SoR for this control record."""
    from src.domain.models.document import Document as LibraryDocument

    return await db.scalar(
        select(LibraryDocument.access_level).where(
            LibraryDocument.id == library_document_id,
            LibraryDocument.tenant_id == tenant_id,
        )
    )


def _converged_access_level(requested: Optional[str], *, register_level: Optional[str]) -> Optional[str]:
    """Resolve one access level for a control record (CUT-1 / F-7 §3).

    The Register wins whenever the control record is anchored to one: F-7 keeps
    ``documents.access_level`` as the single live access field, so a control row
    holding a different answer for the same document is the parallel vocabulary
    CUT-1 exists to retire. Unanchored records keep their own value, folded onto
    the one vocabulary.

    An off-vocabulary value is refused rather than defaulted. Defaulting would
    write an access decision nobody made, and every value the existing UI sends
    (``internal``) has an honest mapping.
    """
    if register_level:
        normalised_register = normalize_access_level(register_level)
        if normalised_register is not None:
            return normalised_register
    if requested is None:
        return None
    converged = normalize_access_level(requested)
    if converged is None:
        raise ValidationError(
            f"access_level {requested!r} is not a Library access level. "
            f"Use one of {list(LIBRARY_ACCESS_LEVELS)} (F-7 §3 — one access vocabulary).",
            details={"access_level": requested, "allowed": list(LIBRARY_ACCESS_LEVELS)},
        )
    return converged


# ============ Document CRUD Endpoints ============


@router.get("/", response_model=dict)
async def list_documents(
    current_user: CurrentUser,
    document_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: DbSession = None,
) -> dict[str, Any]:
    """List controlled documents with filtering"""
    stmt = _tenant_stmt(
        select(ControlledDocument).where(ControlledDocument.is_current == True),
        ControlledDocument,
        current_user,
    )

    if document_type:
        stmt = stmt.where(ControlledDocument.document_type == document_type)
    if category:
        stmt = stmt.where(ControlledDocument.category == category)
    if department:
        stmt = stmt.where(ControlledDocument.department == department)
    if status:
        stmt = stmt.where(ControlledDocument.status == status)
    if search:
        stmt = stmt.where(
            ControlledDocument.title.ilike(f"%{search}%") | ControlledDocument.document_number.ilike(f"%{search}%"),
        )

    count_result = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = count_result.scalar()

    result = await db.execute(stmt.order_by(ControlledDocument.updated_at.desc()).offset(skip).limit(limit))
    documents = result.scalars().all()

    # PX-263 honesty: how many Library uploads exist while Document Control may be empty.
    # Count is informational only — Library rows are not controlled lifecycle records.
    library_document_count: Optional[int] = None
    try:
        from src.domain.models.document import Document

        tenant_id = _tenant_id(current_user)
        lib_count = await db.execute(
            select(func.count(Document.id)).where(
                Document.tenant_id == tenant_id,
                Document.is_active == True,  # noqa: E712
                Document.is_latest == True,  # noqa: E712
            )
        )
        library_document_count = int(lib_count.scalar_one() or 0)
    except Exception:  # noqa: BLE001 — honesty field must never break the list
        logger.exception("Failed to count library documents for document-control honesty")
        library_document_count = None

    return {
        "total": total,
        "library_document_count": library_document_count,
        "documents": [
            {
                "id": d.id,
                "document_number": d.document_number,
                "title": d.title,
                "document_type": d.document_type,
                "category": d.category,
                "current_version": d.current_version,
                "status": d.status,
                "department": d.department,
                "owner_name": d.owner_name,
                "effective_date": (d.effective_date.isoformat() if d.effective_date else None),
                "next_review_date": (d.next_review_date.isoformat() if d.next_review_date else None),
                "is_overdue": (d.next_review_date < _utcnow() if d.next_review_date else False),
            }
            for d in documents
        ],
    }


@router.post("/", response_model=dict, status_code=201)
async def create_document(
    document_data: DocumentCreate,
    current_user: Annotated[User, Depends(require_permission("document:create"))],
    db: DbSession = None,
) -> dict[str, Any]:
    """Create a new controlled document, optionally anchored to a Register row."""
    tenant_id = _tenant_id(current_user)
    register_access_level: Optional[str] = None
    if document_data.library_document_id is not None:
        await _assert_anchor_is_available(
            db, tenant_id=tenant_id, library_document_id=document_data.library_document_id
        )
        register_access_level = await _register_access_level(
            db, tenant_id=tenant_id, library_document_id=document_data.library_document_id
        )
    type_prefix = document_data.document_type[:3].upper()
    unique_suffix = uuid.uuid4().hex[:8].upper()
    document_number = f"{type_prefix}-{unique_suffix}"

    fields = document_data.model_dump()
    converged_access = _converged_access_level(fields.get("access_level"), register_level=register_access_level)
    if converged_access is not None:
        fields["access_level"] = converged_access

    document = ControlledDocument(
        tenant_id=tenant_id,
        document_number=document_number,
        current_version="1.0",
        major_version=1,
        minor_version=0,
        status="draft",
        **fields,
    )

    db.add(document)
    await db.commit()
    await db.refresh(document)

    # Honest create: tip + version row both 1.0 draft (not 1.0 tip / 0.1 row theatre)
    version = document_version_service.build_initial_controlled_version(
        tenant_id=tenant_id,
        document_id=document.id,
        author_name=document_data.author_name,
        created_by_id=getattr(current_user, "id", None),
    )
    db.add(version)
    await db.commit()

    return {
        "id": document.id,
        "document_number": document_number,
        "current_version": document.current_version,
        "status": document.status,
        "version": document_version_service.serialize_controlled_version(version),
        "message": "Document created successfully",
    }


@router.get("/{document_id}/golden-thread", response_model=dict)
async def get_document_golden_thread(
    document_id: int,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Read the controlled-document → GKB evidence chain with honest FK state."""
    tenant_id = _tenant_id(current_user)
    document = (
        await db.execute(
            apply_tenant_filter(
                select(ControlledDocument).where(ControlledDocument.id == document_id),
                ControlledDocument,
                tenant_id,
            )
        )
    ).scalar_one_or_none()
    if not document:
        raise NotFoundError("Document not found")

    from src.domain.models.compliance_evidence import ComplianceEvidenceLink
    from src.domain.services.gkb_control_library_link import resolve_library_for_controlled

    library_doc, match = await resolve_library_for_controlled(db, document, tenant_id=tenant_id)
    hard_fk_present = match.relationship_state == "linked" and document.library_document_id is not None

    evidence_links: list[dict[str, Any]] = []
    if library_doc:
        evidence_result = await db.execute(
            select(ComplianceEvidenceLink)
            .where(
                ComplianceEvidenceLink.tenant_id == tenant_id,
                ComplianceEvidenceLink.entity_type == "document",
                ComplianceEvidenceLink.entity_id == str(library_doc.id),
                ComplianceEvidenceLink.deleted_at.is_(None),
            )
            .order_by(ComplianceEvidenceLink.created_at.desc())
        )
        evidence_links = [
            {
                "id": link.id,
                "clause_id": link.clause_id,
                "status": link.effective_status.value,
                "signal_type": link.signal_type or "evidence",
                "scheme": link.scheme,
                "confidence": link.confidence,
                "linked_by": link.linked_by.value if hasattr(link.linked_by, "value") else str(link.linked_by),
                "title": link.title,
                "rationale": link.rationale,
                "created_at": link.created_at.isoformat() if link.created_at else None,
            }
            for link in evidence_result.scalars().all()
        ]

    plan = decide_golden_thread_publish(
        GoldenThreadContext(
            tenant_id=tenant_id,
            controlled_document_id=document.id,
            library_document_id=library_doc.id if library_doc else None,
            hard_fk_present=hard_fk_present,
            publish_event_requested=False,
        )
    )

    library_payload = (
        {
            "id": library_doc.id,
            "reference_number": library_doc.reference_number,
            "title": library_doc.title,
            "version": library_doc.version,
            "status": library_doc.status.value if hasattr(library_doc.status, "value") else str(library_doc.status),
            "matching_fields": list(match.matching_fields),
        }
        if library_doc
        else None
    )

    if hard_fk_present:
        integrity_message = (
            "This controlled document is hard-linked to the library document below. "
            "Evidence links are recorded against the library row."
        )
    elif match.relationship_state == "unverified_candidate":
        integrity_message = (
            "The displayed library document is an unverified same-tenant candidate only — "
            "no hard link exists yet. Its evidence links are not controlled-document evidence."
        )
    elif match.relationship_state == "ambiguous":
        integrity_message = "More than one library document matches; no candidate or evidence links are displayed."
    else:
        integrity_message = "No library-document match exists for this controlled document."

    return {
        "controlled_document": {
            "id": document.id,
            "document_number": document.document_number,
            "title": document.title,
            "current_version": document.current_version,
            "status": document.status,
            "library_document_id": document.library_document_id,
        },
        "library_document": library_payload if hard_fk_present else None,
        "library_document_candidate": library_payload if match.relationship_state == "unverified_candidate" else None,
        "evidence_links": evidence_links,
        "integrity": {
            "relationship_state": match.relationship_state,
            "hard_fk_present": hard_fk_present,
            "message": integrity_message,
        },
        "publish_plan": {
            "should_run": plan.should_run,
            "denied": plan.denied,
            "deny_reason": plan.deny_reason.value if plan.deny_reason else None,
            "documents_hard_fk_gap": plan.documents_hard_fk_gap,
            "steps": [step.value for step in plan.steps],
        },
    }


@router.put("/{document_id}", response_model=dict)
async def update_document(
    document_id: int,
    document_data: DocumentUpdate,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    db: DbSession = None,
) -> dict[str, Any]:
    """Update document metadata (blocked when published/obsolete — revise first)."""
    result = await db.execute(
        _tenant_stmt(
            select(ControlledDocument).where(ControlledDocument.id == document_id),
            ControlledDocument,
            current_user,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document not found")

    # WC-1 / L-40 — freeze anchored Register rows before any metadata write.
    await assert_controlled_document_not_held(db, document, tenant_id=_tenant_id(current_user), action="edited")
    assert_document_metadata_editable(document.status)

    update_data = document_data.model_dump(exclude_unset=True)
    if "access_level" in update_data:
        register_level = (
            await _register_access_level(
                db,
                tenant_id=_tenant_id(current_user),
                library_document_id=document.library_document_id,
            )
            if document.library_document_id is not None
            else None
        )
        converged = _converged_access_level(update_data["access_level"], register_level=register_level)
        if converged is None:
            # An explicit `"access_level": null` with nothing to inherit is a
            # no-op, not a write of NULL into a NOT NULL column.
            update_data.pop("access_level")
        else:
            update_data["access_level"] = converged
    for key, value in update_data.items():
        setattr(document, key, value)

    document.updated_at = _utcnow()
    await db.commit()
    await db.refresh(document)

    return {"message": "Document updated successfully", "id": document.id}


# ============ Version Control Endpoints ============


@router.post("/{document_id}/versions", response_model=dict, status_code=201)
async def create_new_version(
    document_id: int,
    version_data: VersionCreate,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    db: DbSession = None,
) -> dict[str, Any]:
    """Open a revision draft. Prior published versions remain immutable."""
    tenant_id = _tenant_id(current_user)
    result = await db.execute(
        apply_tenant_filter(
            select(ControlledDocument).where(ControlledDocument.id == document_id),
            ControlledDocument,
            tenant_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document not found")

    version = await document_version_service.revise_controlled(
        db,
        document,
        tenant_id=tenant_id,
        change_summary=version_data.change_summary,
        change_reason=version_data.change_reason,
        change_type=version_data.change_type,
        is_major_version=version_data.is_major_version,
        created_by_id=getattr(current_user, "id", None),
        created_by_name=getattr(current_user, "full_name", None),
    )
    await db.commit()
    await db.refresh(version)

    new_version_number = version.version_number

    # ADR-0021 P0: opening a revise draft must NOT rematch evidence / mark quizzes
    # stale. Those hooks run on publish (see publish_document + gkb_publish_lifecycle).

    return {
        "id": version.id,
        "version_number": new_version_number,
        "status": version.status,
        "is_immutable": False,
        "read_only": False,
        "message": f"Version {new_version_number} created",
    }


@router.post("/{document_id}/publish", response_model=dict)
async def publish_document(
    document_id: int,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    db: DbSession = None,
    version_id: Optional[int] = Query(None),
) -> dict[str, Any]:
    """Publish the working draft; prior published tip becomes superseded (immutable)."""
    tenant_id = _tenant_id(current_user)
    result = await db.execute(
        apply_tenant_filter(
            select(ControlledDocument).where(ControlledDocument.id == document_id),
            ControlledDocument,
            tenant_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document not found")

    version = await document_version_service.publish_controlled(
        db,
        document,
        tenant_id=tenant_id,
        published_by_id=getattr(current_user, "id", None),
        published_by_name=getattr(current_user, "full_name", None),
        version_id=version_id,
    )
    await db.commit()
    await db.refresh(version)

    # ADR-0021 P0: rematch / quiz stale / quiz draft on publish (not revise draft).
    try:
        from src.domain.services.gkb_publish_lifecycle import run_controlled_publish_lifecycle

        result = await run_controlled_publish_lifecycle(
            db=db,
            controlled_document=document,
            new_version=version.version_number,
            user=current_user,
            tenant_id=tenant_id,
        )
        if result.rematch_invoked or result.quizzes_stale_invoked or result.quiz_draft_invoked:
            await db.commit()
    except Exception:
        logger.exception("Governed KB publish lifecycle failed for controlled doc %s", document_id)

    return {
        "id": document.id,
        "current_version": document.current_version,
        "status": document.status,
        "version": document_version_service.serialize_controlled_version(version),
        "message": f"Version {version.version_number} published",
    }


@router.get("/{document_id}/versions/{version_id}/diff", response_model=dict)
async def get_version_diff(
    document_id: int,
    version_id: int,
    current_user: CurrentUser,
    compare_to: Optional[int] = Query(None, description="Version ID to compare with"),
    db: DbSession = None,
) -> dict[str, Any]:
    """Get diff between versions"""
    tenant_id = _tenant_id(current_user)
    result = await db.execute(
        apply_tenant_filter(
            select(ControlledDocumentVersion).where(
                ControlledDocumentVersion.id == version_id,
                ControlledDocumentVersion.document_id == document_id,
            ),
            ControlledDocumentVersion,
            tenant_id,
        )
    )
    version = result.scalar_one_or_none()

    if not version:
        raise NotFoundError("Version not found")

    diff_result = {
        "version": {
            "id": version.id,
            "version_number": version.version_number,
            "change_summary": version.change_summary,
            "sections_changed": version.sections_changed,
        },
        "diff": version.diff_from_previous,
    }

    if compare_to:
        result = await db.execute(
            apply_tenant_filter(
                select(ControlledDocumentVersion).where(
                    ControlledDocumentVersion.id == compare_to,
                    ControlledDocumentVersion.document_id == document_id,
                ),
                ControlledDocumentVersion,
                tenant_id,
            )
        )
        compare_version = result.scalar_one_or_none()
        if compare_version:
            diff_result["compare_to"] = {
                "id": compare_version.id,
                "version_number": compare_version.version_number,
            }

    return diff_result


# ============ Approval Workflow Endpoints ============


@router.get("/workflows", response_model=list)
async def list_workflows(
    current_user: CurrentUser,
    db: DbSession = None,
) -> list[dict[str, Any]]:
    """List approval workflows, or report that none can be listed.

    An empty array here would say "this tenant has configured no approval
    workflows", which is a sentence a reader acts on by configuring one. While the
    table is absent that is not what is true, so the absence is reported instead.
    """
    await _refuse_read_if_unmeasurable(db, APPROVAL_WORKFLOW_TABLES, "Approval workflows")

    result = await db.execute(
        _tenant_stmt(
            select(DocumentApprovalWorkflow).where(DocumentApprovalWorkflow.is_active == True),
            DocumentApprovalWorkflow,
            current_user,
        )
    )
    workflows = result.scalars().all()

    return [
        {
            "id": w.id,
            "name": w.name,
            "description": w.description,
            "applicable_document_types": w.applicable_document_types,
            "workflow_steps": w.workflow_steps,
            "allow_parallel_approval": w.allow_parallel_approval,
        }
        for w in workflows
    ]


@router.post("/workflows", response_model=dict, status_code=201)
async def create_workflow(
    workflow_data: WorkflowCreate,
    current_user: Annotated[User, Depends(require_permission("document:create"))],
    db: DbSession = None,
) -> dict[str, Any]:
    """Create approval workflow"""
    await _refuse_write_if_unprovisioned(db, APPROVAL_WORKFLOW_TABLES, "An approval workflow")

    workflow = DocumentApprovalWorkflow(tenant_id=_tenant_id(current_user), **workflow_data.model_dump())
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)

    return {"id": workflow.id, "message": "Workflow created successfully"}


@router.post("/{document_id}/submit-for-approval", response_model=dict)
async def submit_for_approval(
    document_id: int,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    workflow_id: int = Query(...),
    db: DbSession = None,
) -> dict[str, Any]:
    """Submit document for approval.

    Checked before the document is touched, because the effect of not checking is
    not merely a bad error message: ``document.status`` is set to
    ``pending_approval`` in the same transaction as the approval instance, so a
    failing INSERT takes the status change down with it. A user would be told the
    submission failed while the register showed the document awaiting an approval
    that no table can hold.
    """
    tenant_id = _tenant_id(current_user)
    result = await db.execute(
        apply_tenant_filter(
            select(ControlledDocument).where(ControlledDocument.id == document_id),
            ControlledDocument,
            tenant_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document not found")

    # WC-1 / L-40 — refuse before status flips to pending_approval.
    await assert_controlled_document_not_held(db, document, tenant_id=tenant_id, action="submitted for approval")

    # After the 404, and still before both the first query against an absent
    # table and the status change staged alongside its INSERT.
    await _refuse_write_if_unprovisioned(
        db,
        APPROVAL_WORKFLOW_TABLES + APPROVAL_INSTANCE_TABLES,
        "A submission for approval",
    )

    result = await db.execute(
        apply_tenant_filter(
            select(DocumentApprovalWorkflow).where(DocumentApprovalWorkflow.id == workflow_id),
            DocumentApprovalWorkflow,
            tenant_id,
        )
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise NotFoundError("Workflow not found")

    # Create approval instance
    instance = DocumentApprovalInstance(
        tenant_id=tenant_id,
        document_id=document_id,
        workflow_id=workflow_id,
        current_step=1,
        status="pending",
    )

    # Set due date based on workflow
    if workflow.auto_escalate_after_days:
        instance.due_date = _utcnow() + timedelta(days=workflow.auto_escalate_after_days)

    document.status = "pending_approval"

    db.add(instance)
    await db.commit()
    await db.refresh(instance)

    return {
        "instance_id": instance.id,
        "message": "Document submitted for approval",
        "current_step": 1,
        "due_date": instance.due_date.isoformat() if instance.due_date else None,
    }


@router.post("/approvals/{instance_id}/action", response_model=dict)
async def take_approval_action(
    instance_id: int,
    action_request: ApprovalActionRequest,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    db: DbSession = None,
) -> dict[str, Any]:
    """Take action on an approval request"""
    await _refuse_write_if_unprovisioned(
        db,
        APPROVAL_INSTANCE_TABLES + APPROVAL_WORKFLOW_TABLES,
        "An approval decision",
    )

    tenant_id = _tenant_id(current_user)
    result = await db.execute(
        apply_tenant_filter(
            select(DocumentApprovalInstance).where(DocumentApprovalInstance.id == instance_id),
            DocumentApprovalInstance,
            tenant_id,
        )
    )
    instance = result.scalar_one_or_none()
    if not instance:
        raise NotFoundError("Approval instance not found")

    # Get workflow to determine next steps
    result = await db.execute(
        apply_tenant_filter(
            select(DocumentApprovalWorkflow).where(DocumentApprovalWorkflow.id == instance.workflow_id),
            DocumentApprovalWorkflow,
            tenant_id,
        )
    )
    workflow = result.scalar_one_or_none()
    if not workflow:
        raise HTTPException(status_code=404, detail="Approval workflow not found")

    result = await db.execute(
        apply_tenant_filter(
            select(ControlledDocument).where(ControlledDocument.id == instance.document_id),
            ControlledDocument,
            tenant_id,
        )
    )
    document = result.scalar_one_or_none()

    # WC-1 / L-40 — refuse before recording the decision or flipping status.
    if document is not None:
        await assert_controlled_document_not_held(
            db,
            document,
            tenant_id=tenant_id,
            action=f"approval-action:{action_request.action}",
        )

    # Record the action
    action = DocumentApprovalAction(
        tenant_id=tenant_id,
        instance_id=instance_id,
        workflow_step=instance.current_step,
        approver_id=current_user.id,
        approver_name=current_user.full_name,
        action=action_request.action,
        comments=action_request.comments,
        conditions=action_request.conditions,
        delegated_to=action_request.delegated_to,
    )
    db.add(action)

    if action_request.action == "approved":
        # Check if this was the last step
        if instance.current_step >= len(workflow.workflow_steps):
            instance.status = "approved"
            instance.completed_date = _utcnow()
            instance.final_decision = "approved"
            if document:
                document.status = "approved"
                document.approved_date = _utcnow()
                document.effective_date = _utcnow()
                document.next_review_date = _utcnow() + timedelta(
                    days=document.review_frequency_months * 30,
                )
        else:
            instance.current_step += 1

    elif action_request.action == "rejected":
        instance.status = "rejected"
        instance.completed_date = _utcnow()
        instance.final_decision = "rejected"
        instance.final_comments = action_request.comments
        if document:
            document.status = "draft"

    elif action_request.action == "returned":
        instance.status = "returned"
        instance.current_step = 1
        if document:
            document.status = "draft"

    await db.commit()

    return {
        "message": f"Action '{action_request.action}' recorded",
        "instance_status": instance.status,
        "current_step": instance.current_step,
    }


# ============ Distribution Endpoints ============


@router.post("/{document_id}/distribute", response_model=dict, status_code=201)
async def distribute_document(
    document_id: int,
    distribution: DistributionCreate,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    db: DbSession = None,
) -> dict[str, Any]:
    """Distribute document to recipients"""
    tenant_id = _tenant_id(current_user)
    result = await db.execute(
        apply_tenant_filter(
            select(ControlledDocument).where(ControlledDocument.id == document_id),
            ControlledDocument,
            tenant_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document not found")

    await _refuse_write_if_unprovisioned(db, DISTRIBUTION_TABLES, "A controlled-copy distribution")

    dist = DocumentDistribution(
        tenant_id=tenant_id,
        document_id=document_id,
        notified_date=_utcnow(),
        **distribution.model_dump(),
    )
    db.add(dist)
    await db.commit()
    await db.refresh(dist)

    # Future: dispatch notification email via Celery task

    return {
        "id": dist.id,
        "message": f"Document distributed to {distribution.recipient_name}",
        "copy_number": dist.copy_number,
    }


@router.post("/{document_id}/distributions/{distribution_id}/acknowledge", response_model=dict)
async def acknowledge_distribution(
    document_id: int,
    distribution_id: int,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    db: DbSession = None,
) -> dict[str, Any]:
    """Acknowledge receipt of document"""
    await _refuse_write_if_unprovisioned(db, DISTRIBUTION_TABLES, "A distribution acknowledgment")

    result = await db.execute(
        _tenant_stmt(
            select(DocumentDistribution).where(
                DocumentDistribution.id == distribution_id,
                DocumentDistribution.document_id == document_id,
            ),
            DocumentDistribution,
            current_user,
        )
    )
    dist = result.scalar_one_or_none()

    if not dist:
        raise NotFoundError("Distribution not found")

    dist.acknowledged = True
    dist.acknowledged_date = _utcnow()
    await db.commit()

    return {"message": "Acknowledgment recorded"}


# ============ Obsolete Document Handling ============


@router.post("/{document_id}/obsolete", response_model=dict)
async def mark_document_obsolete(
    document_id: int,
    obsolete_data: ObsoleteRequest,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    db: DbSession = None,
) -> dict[str, Any]:
    """Mark document as obsolete.

    Refused rather than partially applied. The retention record and the status
    change are one transaction on purpose: obsoleting a controlled document
    without recording its retention end date would satisfy the request and lose
    the reason the record exists. So while the retention table is absent, the
    honest outcome is that the document stays current and the caller is told why.
    """
    tenant_id = _tenant_id(current_user)
    result = await db.execute(
        apply_tenant_filter(
            select(ControlledDocument).where(ControlledDocument.id == document_id),
            ControlledDocument,
            tenant_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document not found")

    # After the 404, before the status change below.
    await _refuse_write_if_unprovisioned(db, OBSOLETE_RECORD_TABLES, "An obsolete-document record")
    await assert_controlled_document_not_held(db, document, tenant_id=tenant_id, action="marked obsolete")

    # Update document
    document.status = "obsolete"
    document.is_current = False
    document.obsolete_date = _utcnow()
    document.obsolete_reason = obsolete_data.obsolete_reason
    document.superseded_by = obsolete_data.superseded_by_id

    # Create obsolete record
    record = ObsoleteDocumentRecord(
        tenant_id=tenant_id,
        document_id=document_id,
        obsolete_date=_utcnow(),
        obsolete_reason=obsolete_data.obsolete_reason,
        superseded_by_id=obsolete_data.superseded_by_id,
        retention_required=True,
        retention_end_date=_utcnow() + timedelta(days=document.retention_period_years * 365),
    )
    db.add(record)
    await db.commit()

    return {
        "message": "Document marked as obsolete",
        "retention_end_date": (record.retention_end_date.isoformat() if record.retention_end_date else None),
    }


# ============ Access Logs ============


@router.get("/{document_id}/access-log", response_model=list)
async def get_access_log(
    document_id: int,
    current_user: CurrentUser,
    limit: int = Query(100, ge=1, le=500),
    db: DbSession = None,
) -> list[dict[str, Any]]:
    """Get document access log, or report that it cannot be read.

    An empty access log asserts that nobody has opened this document, which is an
    ISO-relevant claim and a stronger one than it looks. It must not be produced
    by a table that was never there to be read.
    """
    await _refuse_read_if_unmeasurable(db, ACCESS_LOG_TABLES, "The document access log")

    result = await db.execute(
        _tenant_stmt(
            select(DocumentAccessLog).where(DocumentAccessLog.document_id == document_id),
            DocumentAccessLog,
            current_user,
        )
        .order_by(DocumentAccessLog.timestamp.desc())
        .limit(limit)
    )
    logs = result.scalars().all()

    return [
        {
            "id": log.id,
            "user_name": log.user_name,
            "action": log.action,
            "timestamp": log.timestamp.isoformat() if log.timestamp else None,
            "ip_address": log.ip_address,
        }
        for log in logs
    ]


# ============ Summary Statistics ============


@router.get("/summary", response_model=dict)
async def get_document_summary(
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Get document control summary statistics, omitting any figure not measured.

    Seven of the eight figures aggregate ``controlled_documents``, which exists
    and holds rows. Only ``pending_acknowledgments`` reads
    ``document_distributions``, which does not exist — and because one query in a
    request is enough to abort the whole transaction, that single figure has been
    taking the other seven down with it and answering this endpoint with a 500.

    So the unmeasurable figure is omitted and named, rather than the measurable
    ones being discarded to protect it. Omitted rather than reported as ``0``:
    that substitution is the defect PR #1402 fixed on the acknowledgment
    dashboard, where "0% compliance" was read as an audit finding when it was
    only a table nobody could open. It is also omitted rather than sent as
    ``null``, because a client writing ``pending_acknowledgments ?? 0`` would
    reconstruct the same lie from a null.
    """
    tenant_id = _tenant_id(current_user)
    unmeasurable_ack_tables = await absent_tables(db, DISTRIBUTION_TABLES)
    result = await db.execute(
        apply_tenant_filter(
            select(func.count(ControlledDocument.id)).where(ControlledDocument.is_current == True),
            ControlledDocument,
            tenant_id,
        )
    )
    total = result.scalar()

    result = await db.execute(
        apply_tenant_filter(
            select(func.count(ControlledDocument.id)).where(
                ControlledDocument.status == "active",
                ControlledDocument.is_current == True,
            ),
            ControlledDocument,
            tenant_id,
        )
    )
    active = result.scalar()

    result = await db.execute(
        apply_tenant_filter(
            select(func.count(ControlledDocument.id)).where(
                ControlledDocument.status == "draft",
                ControlledDocument.is_current == True,
            ),
            ControlledDocument,
            tenant_id,
        )
    )
    draft = result.scalar()

    result = await db.execute(
        apply_tenant_filter(
            select(func.count(ControlledDocument.id)).where(
                ControlledDocument.status == "pending_approval",
                ControlledDocument.is_current == True,
            ),
            ControlledDocument,
            tenant_id,
        )
    )
    pending_approval = result.scalar()

    result = await db.execute(
        apply_tenant_filter(
            select(func.count(ControlledDocument.id)).where(
                ControlledDocument.next_review_date < _utcnow(),
                ControlledDocument.status == "active",
                ControlledDocument.is_current == True,
            ),
            ControlledDocument,
            tenant_id,
        )
    )
    overdue_review = result.scalar()

    result = await db.execute(
        apply_tenant_filter(
            select(func.count(ControlledDocument.id)).where(ControlledDocument.status == "obsolete"),
            ControlledDocument,
            tenant_id,
        )
    )
    obsolete = result.scalar()

    # Pending acknowledgments
    pending_ack: Optional[int] = None
    if not unmeasurable_ack_tables:
        result = await db.execute(
            apply_tenant_filter(
                select(func.count(DocumentDistribution.id)).where(
                    DocumentDistribution.acknowledged == False,
                    DocumentDistribution.acknowledgment_required == True,
                ),
                DocumentDistribution,
                tenant_id,
            )
        )
        pending_ack = result.scalar()

    # By type
    result = await db.execute(
        apply_tenant_filter(
            select(ControlledDocument.document_type, func.count(ControlledDocument.id)).where(
                ControlledDocument.is_current == True
            ),
            ControlledDocument,
            tenant_id,
        ).group_by(ControlledDocument.document_type)
    )
    by_type = result.all()

    summary: dict[str, Any] = {
        "total_documents": total,
        "active": active,
        "draft": draft,
        "pending_approval": pending_approval,
        "overdue_review": overdue_review,
        "obsolete": obsolete,
        "by_type": {dtype: count for dtype, count in by_type},
    }

    if unmeasurable_ack_tables:
        logger.error(
            "pending acknowledgments are unmeasurable — absent tables: %s",
            ", ".join(unmeasurable_ack_tables),
        )
        summary["unmeasurable"] = {
            "pending_acknowledgments": {
                "missing_tables": list(unmeasurable_ack_tables),
                "provisioning_state": "migration_pending",
                "reason": (
                    "Outstanding acknowledgments cannot be counted because "
                    f"{', '.join(unmeasurable_ack_tables)} is absent from this "
                    "database. This is not a count of zero."
                ),
            }
        }
    else:
        summary["pending_acknowledgments"] = pending_ack

    return summary


# ============ Single-segment catch-all — MUST stay last in this module ============
#
# ``GET /{document_id}`` matches any single path segment, so FastAPI's
# declaration-order routing makes it answer every sibling literal declared below
# it — ``/workflows`` and ``/summary`` both used to land here and get rejected
# with a 422 ``path -> document_id`` int-parsing error while still appearing in
# the OpenAPI document. Any new single-segment literal GET on this router must be
# declared ABOVE this route.
# ``tests/integration/test_route_shadowing_guard.py`` enforces this repo-wide.


@router.get("/{document_id}", response_model=dict)
async def get_document(
    document_id: int,
    current_user: CurrentUser,
    db: DbSession = None,
) -> dict[str, Any]:
    """Get detailed document information, disclosing any part that is unavailable.

    The document, its version history and its metadata all come from tables that
    exist and hold rows. Two subordinate reads do not: the distribution list, and
    the access-log row this endpoint writes on every view. Because a failed
    statement aborts the whole transaction on PostgreSQL, those two have been
    denying access to every controlled document's detail — and silently dropping
    the ``view_count`` increment staged in the same commit.

    So the readable part is served and the unreadable parts are named in an
    ``unavailable`` block. That block is the load-bearing half: ``distributions``
    still arrives as ``[]`` because the one consumer reads
    ``detail.distributions.length`` and a missing key would crash the page, and
    ``[]`` on its own is exactly the "no controlled copies issued" claim that must
    not be made here. The array is safe to render only because something beside it
    says it was never read; ``frontend/src/pages/DocumentControl.tsx`` is changed
    in the same commit to say so.

    The skipped access-log write is disclosed for the same reason it is skipped:
    no trail is recorded either way while the table is absent, so failing the read
    would buy no audit integrity and would hide the gap behind a generic 500. A
    human auditor needs to see it in the payload, not only in the logs.
    """
    tenant_id = _tenant_id(current_user)
    result = await db.execute(
        apply_tenant_filter(
            select(ControlledDocument).where(ControlledDocument.id == document_id),
            ControlledDocument,
            tenant_id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise NotFoundError("Document not found")

    # Asked after the document is known to exist and to belong to this tenant, so
    # a request for a document that is not there still answers 404 and spends no
    # catalog round-trip discovering what it could not have shown anyway.
    unavailable_reads = await absent_tables(db, DISTRIBUTION_TABLES + ACCESS_LOG_TABLES)
    distributions_unavailable = DocumentDistribution.__tablename__ in unavailable_reads
    access_log_unavailable = DocumentAccessLog.__tablename__ in unavailable_reads

    # Get version history
    result = await db.execute(
        apply_tenant_filter(
            select(ControlledDocumentVersion).where(ControlledDocumentVersion.document_id == document_id),
            ControlledDocumentVersion,
            tenant_id,
        ).order_by(ControlledDocumentVersion.created_at.desc())
    )
    versions = result.scalars().all()

    # Get distributions
    distributions: Any = []
    if not distributions_unavailable:
        result = await db.execute(
            apply_tenant_filter(
                select(DocumentDistribution).where(DocumentDistribution.document_id == document_id),
                DocumentDistribution,
                tenant_id,
            )
        )
        distributions = result.scalars().all()

    # Log access
    if not access_log_unavailable:
        log = DocumentAccessLog(
            tenant_id=tenant_id,
            document_id=document_id,
            user_name=current_user.full_name,
            action="view",
        )
        db.add(log)
    else:
        logger.error(
            "document %s viewed without an access-log entry — absent tables: %s",
            document_id,
            DocumentAccessLog.__tablename__,
        )
    document.view_count += 1
    await db.commit()

    detail: dict[str, Any] = {
        "id": document.id,
        "document_number": document.document_number,
        "title": document.title,
        "description": document.description,
        "document_type": document.document_type,
        "category": document.category,
        "subcategory": document.subcategory,
        "current_version": document.current_version,
        "status": document.status,
        "department": document.department,
        "author_name": document.author_name,
        "owner_name": document.owner_name,
        "approver_name": document.approver_name,
        "approved_date": (document.approved_date.isoformat() if document.approved_date else None),
        "effective_date": (document.effective_date.isoformat() if document.effective_date else None),
        "expiry_date": (document.expiry_date.isoformat() if document.expiry_date else None),
        "review_frequency_months": document.review_frequency_months,
        "next_review_date": (document.next_review_date.isoformat() if document.next_review_date else None),
        "last_review_date": (document.last_review_date.isoformat() if document.last_review_date else None),
        "file_name": document.file_name,
        "file_path": document.file_path,
        "file_size": document.file_size,
        "file_type": document.file_type,
        "relevant_standards": document.relevant_standards,
        "relevant_clauses": document.relevant_clauses,
        "access_level": document.access_level,
        "is_confidential": document.is_confidential,
        "training_required": document.training_required,
        "view_count": document.view_count,
        "download_count": document.download_count,
        "published_version": next(
            (v.version_number for v in versions if v.status in ("published", "approved", "effective", "active")),
            None,
        ),
        "working_version": next((v.version_number for v in versions if v.status == "draft"), None),
        "versions": [document_version_service.serialize_controlled_version(v) for v in versions],
        "distributions": [
            {
                "id": d.id,
                "recipient_name": d.recipient_name,
                "recipient_type": d.recipient_type,
                "distribution_type": d.distribution_type,
                "copy_number": d.copy_number,
                "acknowledged": d.acknowledged,
                "acknowledged_date": (d.acknowledged_date.isoformat() if d.acknowledged_date else None),
            }
            for d in distributions
        ],
    }

    unavailable_fields: dict[str, str] = {}
    if distributions_unavailable:
        unavailable_fields["distributions"] = (
            "The controlled-copy distribution list could not be read. The empty "
            "list beside this notice is not a record that no copies were issued."
        )
    if access_log_unavailable:
        unavailable_fields["access_log"] = (
            "This view was not recorded in the document access log, and the log "
            "cannot be read. Access history for this document is not being kept."
        )

    if unavailable_fields:
        detail["unavailable"] = {
            "fields": sorted(unavailable_fields),
            "missing_tables": list(unavailable_reads),
            "provisioning_state": "migration_pending",
            "reasons": unavailable_fields,
        }

    return detail
