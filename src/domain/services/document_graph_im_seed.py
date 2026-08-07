"""Doc Graph Wave 1 — Incident Management demo vertical seed (ADR-0021).

Idempotently finds-or-creates library documents for the IM spine and confirms
the authored edges operators expect to see in a bake:

  Policy --implements--> Procedure --implements--> SOP
  Policy --requires_record--> Incident report form
  Policy --requires_record--> Risk register doc
  Policy --related_to--> Risk Management Policy

Never invents tenants. Operates inside the caller's tenant only. Safe to re-run:
existing title matches are reused; live edges are skipped.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.document import Document, FileType, SensitivityLevel
from src.domain.models.document_graph import DocumentEdgeMethod, DocumentEdgeStatus, DocumentEdgeType
from src.domain.models.enums import DocumentStatus, DocumentType
from src.domain.services.document_graph_service import DocumentGraphService
from src.domain.services.reference_number import ReferenceNumberService

logger = logging.getLogger(__name__)

SEED_MARKER = "doc-graph-im-seed"
SEED_RATIONALE = "Doc Graph Wave 1 Incident Management demo vertical seed"


@dataclass(frozen=True)
class ImSeedDocSpec:
    role: str
    title: str
    document_type: DocumentType
    description: str


# Stable demo titles — prefer matching an existing library row so bake tenants
# that already filed these documents keep their real ids.
IM_SEED_DOC_SPECS: tuple[ImSeedDocSpec, ...] = (
    ImSeedDocSpec(
        role="im_policy",
        title="Incident Management Policy",
        document_type=DocumentType.POLICY,
        description=(f"[{SEED_MARKER}] Policy governing how incidents are reported, " "investigated, and closed."),
    ),
    ImSeedDocSpec(
        role="im_procedure",
        title="Incident Management Procedure",
        document_type=DocumentType.PROCEDURE,
        description=(f"[{SEED_MARKER}] Procedure implementing the Incident Management Policy."),
    ),
    ImSeedDocSpec(
        role="im_sop",
        title="Incident Reporting SOP",
        document_type=DocumentType.SOP,
        description=(f"[{SEED_MARKER}] SOP for first-line incident reporting."),
    ),
    ImSeedDocSpec(
        role="im_form",
        title="Incident Report Form",
        document_type=DocumentType.FORM,
        description=(f"[{SEED_MARKER}] Form required by the Incident Management Policy."),
    ),
    ImSeedDocSpec(
        role="risk_register",
        title="Risk Register",
        document_type=DocumentType.REGISTER,
        description=(f"[{SEED_MARKER}] Risk register document required by IM policy."),
    ),
    ImSeedDocSpec(
        role="risk_policy",
        title="Risk Management Policy",
        document_type=DocumentType.POLICY,
        description=(f"[{SEED_MARKER}] Peer policy related to Incident Management."),
    ),
)


@dataclass(frozen=True)
class ImSeedEdgeSpec:
    src_role: str
    dst_role: str
    edge_type: DocumentEdgeType
    is_primary_parent: bool = False


IM_SEED_EDGE_SPECS: tuple[ImSeedEdgeSpec, ...] = (
    ImSeedEdgeSpec("im_policy", "im_procedure", DocumentEdgeType.IMPLEMENTS, True),
    ImSeedEdgeSpec("im_procedure", "im_sop", DocumentEdgeType.IMPLEMENTS, True),
    ImSeedEdgeSpec("im_policy", "im_form", DocumentEdgeType.REQUIRES_RECORD),
    ImSeedEdgeSpec("im_policy", "risk_register", DocumentEdgeType.REQUIRES_RECORD),
    ImSeedEdgeSpec("im_policy", "risk_policy", DocumentEdgeType.RELATED_TO),
)


@dataclass
class ImSeedDocumentResult:
    role: str
    document_id: int
    title: str
    created: bool


@dataclass
class ImSeedEdgeResult:
    src_role: str
    dst_role: str
    edge_type: str
    edge_id: int
    created: bool


@dataclass
class ImSeedResult:
    documents: list[ImSeedDocumentResult] = field(default_factory=list)
    edges: list[ImSeedEdgeResult] = field(default_factory=list)
    documents_created: int = 0
    documents_reused: int = 0
    edges_created: int = 0
    edges_reused: int = 0


class DocumentGraphImSeedService:
    """Tenant-scoped idempotent IM vertical seed for Doc Graph demos."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.graph = DocumentGraphService(db)

    async def seed(
        self,
        *,
        tenant_id: int,
        actor_id: Optional[int] = None,
        create_missing_documents: bool = True,
    ) -> ImSeedResult:
        result = ImSeedResult()
        role_to_id: dict[str, int] = {}

        for spec in IM_SEED_DOC_SPECS:
            doc, created = await self._find_or_create_document(
                tenant_id=tenant_id,
                actor_id=actor_id,
                spec=spec,
                create_missing=create_missing_documents,
            )
            if doc is None:
                logger.warning(
                    "doc_graph.im_seed missing document role=%s title=%r tenant_id=%s",
                    spec.role,
                    spec.title,
                    tenant_id,
                )
                continue
            role_to_id[spec.role] = doc.id
            result.documents.append(
                ImSeedDocumentResult(
                    role=spec.role,
                    document_id=doc.id,
                    title=doc.title,
                    created=created,
                )
            )
            if created:
                result.documents_created += 1
            else:
                result.documents_reused += 1

        for edge_spec in IM_SEED_EDGE_SPECS:
            src_id = role_to_id.get(edge_spec.src_role)
            dst_id = role_to_id.get(edge_spec.dst_role)
            if src_id is None or dst_id is None:
                logger.warning(
                    "doc_graph.im_seed skip edge %s→%s (%s) — role unresolved",
                    edge_spec.src_role,
                    edge_spec.dst_role,
                    edge_spec.edge_type.value,
                )
                continue

            edge_id, created = await self._ensure_confirmed_edge(
                tenant_id=tenant_id,
                actor_id=actor_id,
                src_document_id=src_id,
                dst_document_id=dst_id,
                edge_type=edge_spec.edge_type,
                is_primary_parent=edge_spec.is_primary_parent,
            )
            result.edges.append(
                ImSeedEdgeResult(
                    src_role=edge_spec.src_role,
                    dst_role=edge_spec.dst_role,
                    edge_type=edge_spec.edge_type.value,
                    edge_id=edge_id,
                    created=created,
                )
            )
            if created:
                result.edges_created += 1
            else:
                result.edges_reused += 1

        await self.db.commit()
        return result

    async def _find_or_create_document(
        self,
        *,
        tenant_id: int,
        actor_id: Optional[int],
        spec: ImSeedDocSpec,
        create_missing: bool,
    ) -> tuple[Optional[Document], bool]:
        existing = await self._find_by_title(tenant_id=tenant_id, title=spec.title)
        if existing is not None:
            return existing, False
        if not create_missing:
            return None, False
        return (
            await self._create_stub_document(
                tenant_id=tenant_id,
                actor_id=actor_id,
                spec=spec,
            ),
            True,
        )

    async def _find_by_title(self, *, tenant_id: int, title: str) -> Optional[Document]:
        # Prefer latest/active rows so superseded copies are not re-linked.
        result = await self.db.execute(
            select(Document)
            .where(
                Document.tenant_id == tenant_id,
                func.lower(Document.title) == title.lower(),
            )
            .order_by(Document.is_latest.desc(), Document.id.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _create_stub_document(
        self,
        *,
        tenant_id: int,
        actor_id: Optional[int],
        spec: ImSeedDocSpec,
    ) -> Document:
        reference_number = await ReferenceNumberService.generate(self.db, "document", Document)
        stub_name = f"{SEED_MARKER}-{spec.role}.md"
        doc = Document(
            tenant_id=tenant_id,
            title=spec.title,
            description=spec.description,
            file_name=stub_name,
            file_type=FileType.MD,
            file_size=0,
            file_path=f"seed/{SEED_MARKER}/{tenant_id}/{stub_name}",
            mime_type="text/markdown",
            document_type=spec.document_type,
            sensitivity=SensitivityLevel.INTERNAL,
            status=DocumentStatus.DRAFT,
            version="1.0",
            is_active=True,
            is_latest=True,
            reference_number=reference_number,
            created_by_id=actor_id,
            ai_tags=[SEED_MARKER, "incident_management"],
        )
        self.db.add(doc)
        await self.db.flush()
        return doc

    async def _ensure_confirmed_edge(
        self,
        *,
        tenant_id: int,
        actor_id: Optional[int],
        src_document_id: int,
        dst_document_id: int,
        edge_type: DocumentEdgeType,
        is_primary_parent: bool,
    ) -> tuple[int, bool]:
        from src.domain.services.document_graph_service import canonicalize_endpoints

        canon_src, canon_dst = canonicalize_endpoints(edge_type, src_document_id, dst_document_id)
        existing_id = await self.graph._find_live_edge_id(  # noqa: SLF001 — seed shares tenant slot
            tenant_id=tenant_id,
            src_document_id=canon_src,
            dst_document_id=canon_dst,
            edge_type=edge_type,
        )
        if existing_id is not None:
            existing = await self.graph._get_edge_or_404(  # noqa: SLF001 — seed shares tenant slot
                tenant_id=tenant_id,
                edge_id=existing_id,
            )
            if existing.status == DocumentEdgeStatus.CONFIRMED:
                return existing_id, False
            if existing.status == DocumentEdgeStatus.REJECTED:
                # Rejected rows still hold the unique slot — free it, then create.
                await self.graph.soft_delete(
                    tenant_id=tenant_id,
                    edge_id=existing_id,
                    commit=False,
                )
            else:
                # proposed / needs_review → confirm so the demo spine is actually confirmed.
                confirmed = await self.graph.confirm(
                    tenant_id=tenant_id,
                    edge_id=existing_id,
                    actor_id=actor_id or 0,
                    commit=False,
                )
                return confirmed.id, True

        edge = await self.graph.create_edge(
            tenant_id=tenant_id,
            src_document_id=src_document_id,
            dst_document_id=dst_document_id,
            edge_type=edge_type,
            actor_id=actor_id,
            is_primary_parent=is_primary_parent,
            status=DocumentEdgeStatus.CONFIRMED,
            created_method=DocumentEdgeMethod.AUTO,
            rationale=SEED_RATIONALE,
            commit=False,
        )
        return edge.id, True
