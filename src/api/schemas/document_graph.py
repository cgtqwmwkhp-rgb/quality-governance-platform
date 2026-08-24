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


class PendingEdgeEndpoint(BaseModel):
    """One end of a queued edge, enriched so the queue avoids N+1 document reads.

    ``readable`` is false when the library ACL would refuse this operator the
    document by id; ``title`` is then withheld rather than guessed at.
    """

    model_config = ConfigDict(extra="forbid")

    document_id: int
    title: Optional[str] = None
    reference: Optional[str] = None
    href: str
    readable: bool


class PendingDocumentEdgeItem(BaseModel):
    """A proposed / needs_review Doc Graph edge awaiting operator confirmation."""

    model_config = ConfigDict(extra="forbid")

    edge_id: int
    edge_type: DocumentEdgeType
    status: DocumentEdgeStatus
    created_method: DocumentEdgeMethod
    is_primary_parent: bool
    # True when confirming this edge can drive publish impact (ADR-0021).
    impact_driving: bool
    confidence: Optional[float] = None
    rationale: Optional[str] = None
    created_at: datetime
    src: PendingEdgeEndpoint
    dst: PendingEdgeEndpoint


class PendingDocumentEdgeListResponse(BaseModel):
    """One page of the Doc Graph confirm queue — never a global facet total."""

    model_config = ConfigDict(extra="forbid")

    items: List[PendingDocumentEdgeItem]
    returned: int
    limit: int
    truncated: bool


class DocumentThreadHop(BaseModel):
    """One hop on a Doc Graph primary-implements thread (ambient-renderable).

    Enriched so the UI can render without N+1 document fetches. Aligns with
    RiskUpstreamItem spirit (title / reference / href) for document-centric hops.
    Doc Graph is not the Golden Thread.
    """

    model_config = ConfigDict(extra="forbid")

    document_id: int
    edge_id: int
    depth: int
    direction: str
    title: Optional[str] = None
    reference: Optional[str] = None
    href: str
    origin: str = "graph"
    status: str


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


class ClauseDocumentFreshnessItem(BaseModel):
    """One library document evidencing a clause, with CEL tip freshness."""

    model_config = ConfigDict(extra="forbid")

    document_id: Optional[int] = None
    title: Optional[str] = None
    evidence_link_id: int
    link_status: Optional[str] = None
    pinned_document_version_id: Optional[int] = None
    tip_document_version_id: Optional[int] = None
    tip_version_number: Optional[str] = None
    freshness: str


class ClauseDocumentsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clause_id: str
    documents: List[ClauseDocumentFreshnessItem]
    total: int


class ImSeedDocumentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    document_id: int
    title: str
    created: bool


class ImSeedEdgeItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    src_role: str
    dst_role: str
    edge_type: str
    edge_id: int
    created: bool


class ImSeedResponse(BaseModel):
    """Outcome of the Incident Management Doc Graph demo seed."""

    model_config = ConfigDict(extra="forbid")

    documents: List[ImSeedDocumentItem]
    edges: List[ImSeedEdgeItem]
    documents_created: int
    documents_reused: int
    edges_created: int
    edges_reused: int


class CascadeDocumentItem(BaseModel):
    """One active library document in the estate cascade aggregate (NS-EXP / W8).

    Titles are omitted when the library ACL would refuse the by-id route for the
    same operator — the Structure map never invents a second ACL.
    """

    model_config = ConfigDict(extra="forbid")

    document_id: int
    title: Optional[str] = None
    reference: Optional[str] = None
    pel_doc_ref: Optional[str] = None
    cascade_level: Optional[int] = Field(None, ge=1, le=5)
    document_type: Optional[str] = None
    href: str
    readable: bool
    parent_document_id: Optional[int] = None
    parent_pel: Optional[str] = None


class CascadeBandSummary(BaseModel):
    """Count of readable documents at one cascade level (or unset)."""

    model_config = ConfigDict(extra="forbid")

    level: Optional[int] = Field(None, ge=1, le=5)
    label: str
    count: int = Field(..., ge=0)


class CascadeOrphanSummary(BaseModel):
    """Workbook orphan types among readable documents (CAS-3 honesty counts).

    Ids are listable so the Structure map can surface them without a twin
    orphan board page. Counts match the id lists — never a facet total over
    documents the operator cannot read.
    """

    model_config = ConfigDict(extra="forbid")

    unimplemented_policy_ids: List[int]
    unparented_ids: List[int]
    uncontrolled_record_ids: List[int]
    unimplemented_policy_count: int = Field(..., ge=0)
    unparented_count: int = Field(..., ge=0)
    uncontrolled_record_count: int = Field(..., ge=0)


class CascadeAggregateResponse(BaseModel):
    """Whole-estate cascade payload for Structure map L1–L5 bands (one request).

    Confirmed ``implements`` edges only — proposed stay out of the explorer.
    Replaces the Structure map's previous 1+N per-document edge fetches.
    """

    model_config = ConfigDict(extra="forbid")

    documents: List[CascadeDocumentItem]
    edges: List[DocumentEdgeResponse]
    bands: List[CascadeBandSummary]
    orphans: CascadeOrphanSummary
    returned_documents: int = Field(..., ge=0)
    returned_edges: int = Field(..., ge=0)
