"""Digital Signature API response schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel

# ============================================================================
# Signing Page Schemas
# ============================================================================


class SigningRequestInfo(BaseModel):
    id: int
    reference: str
    title: str
    description: Optional[str] = None
    document_type: str
    status: str


class SigningSignerInfo(BaseModel):
    id: int
    name: str
    email: str
    role: str
    status: str


class SigningPageResponse(BaseModel):
    request: SigningRequestInfo
    signer: SigningSignerInfo
    legal_statement: str
    can_sign: bool = False


# ============================================================================
# Action Response Schemas
# ============================================================================


class SendRequestResponse(BaseModel):
    status: str
    reference: str


class VoidRequestResponse(BaseModel):
    status: str
    reference: str


class SignDocumentResponse(BaseModel):
    status: str
    signature_id: int
    signed_at: str
    request_status: str


class DeclineSigningResponse(BaseModel):
    status: str
    declined_at: str


# ============================================================================
# Template Use Response
# ============================================================================


class TemplateUseSignerItem(BaseModel):
    id: int
    email: str
    name: str
    role: str
    order: int
    status: str
    signed_at: Optional[str] = None
    declined_at: Optional[str] = None


class TemplateUseResponse(BaseModel):
    id: int
    reference_number: str
    title: str
    description: Optional[str] = None
    document_type: str
    workflow_type: str
    status: str
    expires_at: Optional[datetime] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    signers: list[TemplateUseSignerItem] = []


# ============================================================================
# Statistics Schemas
# ============================================================================


class SignatureStatsResponse(BaseModel):
    requests_by_status: dict[str, int] = {}
    total_signatures: int = 0
    requests_this_month: int = 0


# ============================================================================
# Admin Schemas
# ============================================================================


class SendRemindersResponse(BaseModel):
    reminders_sent: int = 0


class ExpireOldResponse(BaseModel):
    expired_count: int = 0


# ============================================================================
# Pending Requests (returns list, but endpoint declares response_model=dict)
# ============================================================================


class PendingRequestItem(BaseModel):
    id: int
    reference_number: str
    title: str
    description: Optional[str] = None
    document_type: str
    workflow_type: str
    status: str
    expires_at: Optional[datetime] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    signers: list[TemplateUseSignerItem] = []
