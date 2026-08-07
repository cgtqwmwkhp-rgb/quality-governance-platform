"""ISO reverse surface: clause → library documents with CEL version freshness.

Doc Graph Wave 1 PR-F. Flag-gated at the route layer via
``document_graph_enabled``. CEL remains the write path for clause links;
this service only composes a reverse read model.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.compliance_evidence import ComplianceEvidenceLink
from src.domain.models.document import Document
from src.domain.services.cel_version_freshness import classify_cel_version_freshness
from src.domain.services.cel_version_pin import parse_document_entity_id
from src.domain.services.document_version_service import document_version_service


class DocumentGraphIsoReverseService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_documents_for_clause(
        self,
        *,
        tenant_id: int,
        clause_id: str,
    ) -> dict[str, Any]:
        """Return library documents evidencing ``clause_id`` with tip freshness."""
        result = await self.db.execute(
            select(ComplianceEvidenceLink)
            .where(
                ComplianceEvidenceLink.deleted_at.is_(None),
                ComplianceEvidenceLink.tenant_id == tenant_id,
                ComplianceEvidenceLink.clause_id == clause_id,
                ComplianceEvidenceLink.entity_type == "document",
            )
            .order_by(ComplianceEvidenceLink.created_at.desc(), ComplianceEvidenceLink.id.desc())
        )
        links = list(result.scalars().all())

        document_ids: list[int] = []
        parsed_links: list[tuple[ComplianceEvidenceLink, Optional[int]]] = []
        for link in links:
            doc_id = parse_document_entity_id(link.entity_id)
            parsed_links.append((link, doc_id))
            if doc_id is not None:
                document_ids.append(doc_id)

        titles = await self._titles_for(tenant_id=tenant_id, document_ids=document_ids)
        tip_cache: dict[int, tuple[Optional[int], Optional[str]]] = {}

        documents: list[dict[str, Any]] = []
        for link, doc_id in parsed_links:
            tip_id: Optional[int] = None
            tip_version_number: Optional[str] = None
            if doc_id is not None:
                if doc_id not in tip_cache:
                    tip = await document_version_service.resolve_tip_library_version(
                        self.db,
                        document_id=doc_id,
                        tenant_id=tenant_id,
                    )
                    if tip is None:
                        tip_cache[doc_id] = (None, None)
                    else:
                        tip_cache[doc_id] = (int(tip.id), str(tip.version_number))
                tip_id, tip_version_number = tip_cache[doc_id]

            pinned = getattr(link, "document_version_id", None)
            pinned_id = int(pinned) if pinned is not None else None
            freshness = classify_cel_version_freshness(
                pinned_document_version_id=pinned_id,
                tip_document_version_id=tip_id,
            )
            status = link.status
            if status is None:
                status_val = None
            elif hasattr(status, "value"):
                status_val = status.value
            else:
                status_val = status
            documents.append(
                {
                    "document_id": doc_id,
                    "title": titles.get(doc_id) if doc_id is not None else (link.title or None),
                    "evidence_link_id": int(link.id),
                    "link_status": str(status_val) if status_val is not None else None,
                    "pinned_document_version_id": pinned_id,
                    "tip_document_version_id": tip_id,
                    "tip_version_number": tip_version_number,
                    "freshness": freshness,
                }
            )

        return {"clause_id": clause_id, "documents": documents, "total": len(documents)}

    async def _titles_for(
        self,
        *,
        tenant_id: int,
        document_ids: list[int],
    ) -> dict[int, str]:
        unique = sorted(set(document_ids))
        if not unique:
            return {}
        result = await self.db.execute(
            select(Document.id, Document.title).where(
                Document.tenant_id == tenant_id,
                Document.id.in_(unique),
            )
        )
        return {int(doc_id): str(title) for doc_id, title in result.all()}
