"""Response schemas for Document Control endpoints."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel

# ============ Nested Sub-schemas ============


class DocumentVersionResponse(BaseModel):
    id: int
    version_number: str
    change_summary: str
    change_type: str
    status: str
    created_by_name: Optional[str] = None
    created_at: Optional[datetime] = None
    approved_by_name: Optional[str] = None
    approved_date: Optional[datetime] = None

    class Config:
        from_attributes = True


class DocumentDistributionResponse(BaseModel):
    id: int
    recipient_name: str
    recipient_type: str
    distribution_type: str
    copy_number: Optional[str] = None
    acknowledged: bool
    acknowledged_date: Optional[datetime] = None

    class Config:
        from_attributes = True


# ============ Document List Item ============


class DocumentListItemResponse(BaseModel):
    id: int
    document_number: str
    title: str
    document_type: str
    category: str
    current_version: str
    status: str
    department: Optional[str] = None
    owner_name: Optional[str] = None
    effective_date: Optional[str] = None
    next_review_date: Optional[str] = None
    is_overdue: bool

    class Config:
        from_attributes = True


class DocumentListResponse(BaseModel):
    items: list[DocumentListItemResponse]
    total: int
    page: int
    page_size: int
    pages: int


# ============ Document Detail ============


class ControlledDocumentResponse(BaseModel):
    id: int
    document_number: str
    title: str
    description: Optional[str] = None
    document_type: str
    category: str
    subcategory: Optional[str] = None
    current_version: str
    status: str
    department: Optional[str] = None
    author_name: Optional[str] = None
    owner_name: Optional[str] = None
    approver_name: Optional[str] = None
    approved_date: Optional[str] = None
    effective_date: Optional[str] = None
    expiry_date: Optional[str] = None
    review_frequency_months: int
    next_review_date: Optional[str] = None
    last_review_date: Optional[str] = None
    file_name: Optional[str] = None
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    file_type: Optional[str] = None
    relevant_standards: Optional[list] = None
    relevant_clauses: Optional[list] = None
    access_level: str
    is_confidential: bool
    training_required: bool
    view_count: int
    download_count: int
    versions: list[DocumentVersionResponse]
    distributions: list[DocumentDistributionResponse]

    class Config:
        from_attributes = True


# ============ Approval Workflow ============


class DocumentApprovalWorkflowResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    applicable_document_types: list
    workflow_steps: list
    allow_parallel_approval: bool

    class Config:
        from_attributes = True


# ============ Summary ============


class DocumentSummaryResponse(BaseModel):
    total_documents: int
    active: int
    draft: int
    pending_approval: int
    overdue_review: int
    obsolete: int
    pending_acknowledgments: int
    by_type: dict[str, int]


# ============ Access Log ============


class DocumentAccessLogResponse(BaseModel):
    id: int
    user_name: str
    action: str
    timestamp: Optional[str] = None
    ip_address: Optional[str] = None

    class Config:
        from_attributes = True


# ============ Version Diff ============


class VersionInfoResponse(BaseModel):
    id: int
    version_number: str
    change_summary: Optional[str] = None
    sections_changed: Optional[list] = None


class CompareToResponse(BaseModel):
    id: int
    version_number: str


class VersionDiffResponse(BaseModel):
    version: VersionInfoResponse
    diff: Optional[str] = None
    compare_to: Optional[CompareToResponse] = None


# ============ Mutation Responses ============


class DocumentCreateResponse(BaseModel):
    id: int
    document_number: str
    message: str


class DocumentUpdateResponse(BaseModel):
    message: str
    id: int


class VersionCreateResponse(BaseModel):
    id: int
    version_number: str
    message: str


class WorkflowCreateResponse(BaseModel):
    id: int
    message: str


class SubmitApprovalResponse(BaseModel):
    instance_id: int
    message: str
    current_step: int
    due_date: Optional[str] = None


class ApprovalActionResponse(BaseModel):
    message: str
    instance_status: str
    current_step: int


class DistributeResponse(BaseModel):
    id: int
    message: str
    copy_number: Optional[str] = None


class AcknowledgmentResponse(BaseModel):
    message: str


class ObsoleteResponse(BaseModel):
    message: str
    retention_end_date: Optional[str] = None
