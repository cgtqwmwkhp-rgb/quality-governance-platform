"""Pydantic schemas for OCR artifact ops and dispute/ack stubs."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.domain.models.ocr_artifact import OCRArtifactOverrideStatus, OCRArtifactTier


class OCRArtifactResponse(BaseModel):
    """Serialized OCR artifact row."""

    id: int
    tenant_id: Optional[int] = None
    provider: str
    page_number: int
    content_hash: str
    confidence: Optional[float] = None
    pipeline_version: str
    job_ref: Optional[str] = None
    draft_ref: Optional[str] = None
    tier: OCRArtifactTier
    override_status: OCRArtifactOverrideStatus
    override_note: Optional[str] = None
    overridden_by: Optional[str] = None
    overridden_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class OCRArtifactDisputeRequest(BaseModel):
    """Record a human dispute on an OCR artifact (stub — no provider dial)."""

    artifact_id: int
    note: str = Field(..., min_length=1, max_length=2000)
    actor: str = Field(..., min_length=1, max_length=128)


class OCRArtifactAckRequest(BaseModel):
    """Record human acknowledgement of an OCR artifact (stub — no provider dial)."""

    artifact_id: int
    note: Optional[str] = Field(default=None, max_length=2000)
    actor: str = Field(..., min_length=1, max_length=128)


class OCRArtifactOverrideResponse(BaseModel):
    """Outcome of a dispute or ack stub."""

    artifact: OCRArtifactResponse
    stub: bool = True
    provider_dialed: bool = False
    message: str
