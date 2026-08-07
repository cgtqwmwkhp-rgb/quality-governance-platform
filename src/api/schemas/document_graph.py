"""Pydantic schemas for Doc Graph (ADR-0021 Wave 0)."""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.api.schemas.validators import sanitize_field
from src.domain.models.document_graph import DocumentEdgeMethod, DocumentEdgeStatus, DocumentEdgeType


class DocumentEdgeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    src_document_id: int = Field(..., ge=1)
    dst_document_id: int = Field(..., ge=1)
    edge_type: DocumentEdgeType
    is_primary_parent: bool = False
    status: Optional[DocumentEdgeStatus] = None
    created_method: DocumentEdgeMethod = DocumentEdgeMethod.MANUAL
    confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    rationale: Optional[str] = None
    src_pel_doc_ref: Optional[str] = Field(None, max_length=30)
    dst_pel_doc_ref: Optional[str] = Field(None, max_length=30)
    cited_document_version_id: Optional[int] = Field(None, ge=1)
    chunk_id: Optional[int] = Field(None, ge=1)
    char_start: Optional[int] = Field(None, ge=0)
    char_end: Optional[int] = Field(None, ge=0)
    quote_hash: Optional[str] = Field(None, max_length=64)
    citation_text: Optional[str] = None
    cited_version: Optional[str] = Field(None, max_length=50)

    @field_validator("rationale", "citation_text", "src_pel_doc_ref", "dst_pel_doc_ref", "cited_version", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)

    @model_validator(mode="after")
    def _validate_pair(self) -> "DocumentEdgeCreate":
        if self.src_document_id == self.dst_document_id:
            raise ValueError("src_document_id and dst_document_id must differ")
        if self.is_primary_parent and self.edge_type != DocumentEdgeType.IMPLEMENTS:
            raise ValueError("is_primary_parent is only valid for implements edges")
        return self


class DocumentEdgeRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rationale: Optional[str] = None

    @field_validator("rationale", mode="before")
    @classmethod
    def _sanitize(cls, v):
        return sanitize_field(v)


class DocumentEdgeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: int
    tenant_id: int
    src_document_id: int
    dst_document_id: int
    src_pel_doc_ref: Optional[str] = None
    dst_pel_doc_ref: Optional[str] = None
    edge_type: DocumentEdgeType
    is_primary_parent: bool
    status: DocumentEdgeStatus
    created_method: DocumentEdgeMethod
    confidence: Optional[float] = None
    rationale: Optional[str] = None
    confirmed_by_id: Optional[int] = None
    confirmed_at: Optional[datetime] = None
    cited_document_version_id: Optional[int] = None
    chunk_id: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
    quote_hash: Optional[str] = None
    citation_text: Optional[str] = None
    cited_version: Optional[str] = None
    deleted_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime


class DocumentEdgeListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[DocumentEdgeResponse]
    total: int


class DocumentThreadHop(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: int
    edge_id: int
    depth: int
    direction: str


class DocumentThreadResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    document_id: int
    ancestors: List[DocumentThreadHop]
    descendants: List[DocumentThreadHop]
    max_depth: int


class HeuristicProposeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    created: List[DocumentEdgeResponse]
    created_count: int
    skipped_existing: int
    skipped_unresolved: int
    sources: dict[str, int]


class CitationStalenessResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    edge_id: int
    status: str
    quote_hash: Optional[str] = None
    chunk_id: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None
