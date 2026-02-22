"""Document Control API routes.

Thin controller layer — all business logic lives in DocumentControlService.
"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.dependencies import CurrentUser, DbSession, require_permission
from src.api.schemas.document_control import (
    AcknowledgmentResponse,
    ApprovalActionResponse,
    ControlledDocumentResponse,
    DistributeResponse,
    DocumentAccessLogResponse,
    DocumentApprovalWorkflowResponse,
    DocumentCreateResponse,
    DocumentListResponse,
    DocumentSummaryResponse,
    DocumentUpdateResponse,
    ObsoleteResponse,
    SubmitApprovalResponse,
    VersionCreateResponse,
    VersionDiffResponse,
    WorkflowCreateResponse,
)
from src.api.utils.pagination import PaginationParams
from src.domain.exceptions import NotFoundError
from src.domain.models.user import User
from src.domain.services.document_control_service import DocumentControlService

try:
    from opentelemetry import trace

    tracer = trace.get_tracer(__name__)
except ImportError:
    tracer = None  # type: ignore[assignment]  # TYPE-IGNORE: optional-dependency

router = APIRouter()


# ============ Pydantic Schemas ============


class DocumentCreate(BaseModel):
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
    access_level: str = Field(default="internal")
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
    obsolete_reason: str = Field(..., min_length=10)
    superseded_by_id: Optional[int] = None


# ============ Document CRUD Endpoints ============


@router.get("/", response_model=DocumentListResponse)
async def list_documents(
    db: DbSession,
    current_user: CurrentUser,
    params: PaginationParams = Depends(),
    document_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    department: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
) -> dict[str, Any]:
    """List controlled documents with filtering."""
    service = DocumentControlService(db)
    return await service.list_documents(
        tenant_id=current_user.tenant_id,
        params=params,
        document_type=document_type,
        category=category,
        department=department,
        status_filter=status,
        search=search,
    )


@router.post("/", response_model=DocumentCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_document(
    document_data: DocumentCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:create"))],
) -> dict[str, Any]:
    """Create a new controlled document."""
    _span = tracer.start_span("create_document") if tracer else None
    service = DocumentControlService(db)
    result = await service.create_document(document_data, tenant_id=current_user.tenant_id)
    if _span:
        _span.end()
    return result


# ============ Approval Workflow Endpoints ============


@router.get("/workflows", response_model=list[DocumentApprovalWorkflowResponse])
async def list_workflows(
    db: DbSession,
    current_user: CurrentUser,
) -> list[dict[str, Any]]:
    """List approval workflows."""
    service = DocumentControlService(db)
    return await service.list_workflows(tenant_id=current_user.tenant_id)


@router.post("/workflows", response_model=WorkflowCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_workflow(
    workflow_data: WorkflowCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:create"))],
) -> dict[str, Any]:
    """Create approval workflow."""
    service = DocumentControlService(db)
    return await service.create_workflow(workflow_data, tenant_id=current_user.tenant_id)


# ============ Summary Statistics ============


@router.get("/summary", response_model=DocumentSummaryResponse)
async def get_document_summary(
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get document control summary statistics."""
    service = DocumentControlService(db)
    return await service.get_summary(tenant_id=current_user.tenant_id)


# ============ Document Detail (after literal path routes) ============


@router.get("/{document_id}", response_model=ControlledDocumentResponse)
async def get_document(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
) -> dict[str, Any]:
    """Get detailed document information."""
    service = DocumentControlService(db)
    try:
        return await service.get_document(document_id, tenant_id=current_user.tenant_id)
    except LookupError:
        raise NotFoundError("Document not found")


@router.put("/{document_id}", response_model=DocumentUpdateResponse)
async def update_document(
    document_id: int,
    document_data: DocumentUpdate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
) -> dict[str, Any]:
    """Update document metadata."""
    service = DocumentControlService(db)
    try:
        return await service.update_document(document_id, document_data, tenant_id=current_user.tenant_id)
    except LookupError:
        raise NotFoundError("Document not found")


# ============ Version Control Endpoints ============


@router.post("/{document_id}/versions", response_model=VersionCreateResponse, status_code=status.HTTP_201_CREATED)
async def create_new_version(
    document_id: int,
    version_data: VersionCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:create"))],
) -> dict[str, Any]:
    """Create a new version of the document."""
    service = DocumentControlService(db)
    try:
        return await service.create_version(document_id, version_data, tenant_id=current_user.tenant_id)
    except LookupError:
        raise NotFoundError("Document not found")


@router.get("/{document_id}/versions/{version_id}/diff", response_model=VersionDiffResponse)
async def get_version_diff(
    document_id: int,
    version_id: int,
    db: DbSession,
    current_user: CurrentUser,
    compare_to: Optional[int] = Query(None, description="Version ID to compare with"),
) -> dict[str, Any]:
    """Get diff between versions."""
    service = DocumentControlService(db)
    try:
        return await service.get_version_diff(document_id, version_id, compare_to=compare_to)
    except LookupError:
        raise NotFoundError("Version not found")


# ============ Approval Submission & Actions ============


@router.post("/{document_id}/submit-for-approval", response_model=SubmitApprovalResponse)
async def submit_for_approval(
    document_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    workflow_id: int = Query(...),
) -> dict[str, Any]:
    """Submit document for approval."""
    service = DocumentControlService(db)
    try:
        return await service.submit_for_approval(document_id, workflow_id, tenant_id=current_user.tenant_id)
    except LookupError:
        raise NotFoundError("Document or workflow not found")


@router.post("/approvals/{instance_id}/action", response_model=ApprovalActionResponse)
async def take_approval_action(
    instance_id: int,
    action_request: ApprovalActionRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
) -> dict[str, Any]:
    """Take action on an approval request."""
    service = DocumentControlService(db)
    try:
        return await service.take_approval_action(instance_id, action_request, tenant_id=current_user.tenant_id)
    except LookupError:
        raise NotFoundError("Approval instance not found")


# ============ Distribution Endpoints ============


@router.post("/{document_id}/distribute", response_model=DistributeResponse, status_code=status.HTTP_201_CREATED)
async def distribute_document(
    document_id: int,
    distribution: DistributionCreate,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:create"))],
) -> dict[str, Any]:
    """Distribute document to recipients."""
    service = DocumentControlService(db)
    try:
        return await service.distribute_document(document_id, distribution, tenant_id=current_user.tenant_id)
    except LookupError:
        raise NotFoundError("Document not found")


@router.post("/{document_id}/distributions/{distribution_id}/acknowledge", response_model=AcknowledgmentResponse)
async def acknowledge_distribution(
    document_id: int,
    distribution_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
) -> dict[str, Any]:
    """Acknowledge receipt of document."""
    service = DocumentControlService(db)
    try:
        return await service.acknowledge_distribution(document_id, distribution_id)
    except LookupError:
        raise NotFoundError("Distribution not found")


# ============ Obsolete Document Handling ============


@router.post("/{document_id}/obsolete", response_model=ObsoleteResponse)
async def mark_document_obsolete(
    document_id: int,
    obsolete_data: ObsoleteRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
) -> dict[str, Any]:
    """Mark document as obsolete."""
    service = DocumentControlService(db)
    try:
        return await service.mark_obsolete(document_id, obsolete_data, tenant_id=current_user.tenant_id)
    except LookupError:
        raise NotFoundError("Document not found")


# ============ Access Logs ============


@router.get("/{document_id}/access-log", response_model=list[DocumentAccessLogResponse])
async def get_access_log(
    document_id: int,
    db: DbSession,
    current_user: CurrentUser,
    limit: int = Query(100, ge=1, le=500),
) -> list[dict[str, Any]]:
    """Get document access log."""
    service = DocumentControlService(db)
    return await service.get_access_log(document_id, limit=limit)
