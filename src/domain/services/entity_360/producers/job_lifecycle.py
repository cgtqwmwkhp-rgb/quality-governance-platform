"""Job Lifecycle Entity360 producer — bidirectional on day one (JL-1).

Origin ``job``. Links library documents ↔ job steps via cell memberships.
Empty lists are always present; never a one-way silo.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select

from src.domain.models.document import Document
from src.domain.models.job_lifecycle import JobCell, JobCellDocument, JobStep
from src.domain.services.entity_360.types import ProducerResult, make_hop
from src.domain.services.href_registry import document_href, href_for


class JobLifecycleProducer:
    """Emits document ↔ job_step hops from live cell document memberships.

    Bidirectional registration contract:
    - ``document``: upstream = job steps that cite the document; downstream = []
    - ``job_step``: upstream = []; downstream = library documents in cells on the step
    """

    origin = "job"

    _SUPPORTED = frozenset({"document", "job_step"})

    def supports(self, entity_type: str) -> bool:
        return entity_type.strip().lower() in self._SUPPORTED

    async def produce(
        self,
        *,
        db: Any,
        tenant_id: int,
        entity_type: str,
        entity_id: int,
        user: Any,
    ) -> ProducerResult:
        _ = user
        key = entity_type.strip().lower()
        try:
            if key == "document":
                return await self._for_document(db=db, tenant_id=tenant_id, document_id=entity_id)
            if key == "job_step":
                return await self._for_job_step(db=db, tenant_id=tenant_id, step_id=entity_id)
            return ProducerResult(origin=self.origin, status="skipped", reason="unsupported")
        except Exception as exc:  # noqa: BLE001 — producer isolation
            return ProducerResult(
                origin=self.origin,
                status="error",
                reason=f"job_lifecycle: {exc}",
            )

    async def _for_document(self, *, db: Any, tenant_id: int, document_id: int) -> ProducerResult:
        result = await db.execute(
            select(JobCellDocument, JobCell, JobStep)
            .join(JobCell, JobCell.id == JobCellDocument.cell_id)
            .join(JobStep, JobStep.id == JobCell.step_id)
            .where(
                JobCellDocument.tenant_id == tenant_id,
                JobCellDocument.library_document_id == document_id,
                JobCell.deleted_at.is_(None),
                JobStep.deleted_at.is_(None),
            )
        )
        rows = list(result.all())
        upstream: list[dict[str, Any]] = []
        seen_steps: set[int] = set()
        for _membership, _cell, step in rows:
            if step.id in seen_steps:
                continue
            seen_steps.add(step.id)
            upstream.append(
                make_hop(
                    source_type="job_step",
                    source_id=step.id,
                    title=step.name,
                    reference=step.code,
                    href=href_for("job_step", step.id),
                    direction="upstream",
                    relation="job_cell",
                    depth=1,
                    origin="job",
                    status="active" if step.is_active else "inactive",
                )
            )
        upstream.sort(key=lambda h: (h.get("reference") or "", h.get("source_id") or 0))
        return ProducerResult(
            origin=self.origin,
            status="ok",
            upstream=upstream,
            downstream=[],
        )

    async def _for_job_step(self, *, db: Any, tenant_id: int, step_id: int) -> ProducerResult:
        result = await db.execute(
            select(JobCellDocument, Document)
            .join(JobCell, JobCell.id == JobCellDocument.cell_id)
            .join(Document, Document.id == JobCellDocument.library_document_id)
            .where(
                JobCellDocument.tenant_id == tenant_id,
                JobCell.tenant_id == tenant_id,
                JobCell.step_id == step_id,
                JobCell.deleted_at.is_(None),
                Document.tenant_id == tenant_id,
            )
            .order_by(JobCellDocument.sort_order, JobCellDocument.id)
        )
        rows = list(result.all())
        downstream: list[dict[str, Any]] = []
        seen_docs: set[int] = set()
        for _membership, doc in rows:
            if doc.id in seen_docs:
                continue
            seen_docs.add(doc.id)
            downstream.append(
                make_hop(
                    source_type="document",
                    source_id=doc.id,
                    title=getattr(doc, "title", None),
                    reference=_document_reference(doc),
                    href=document_href(doc.id),
                    direction="downstream",
                    relation="job_cell",
                    depth=1,
                    origin="job",
                    status=None,
                )
            )
        return ProducerResult(
            origin=self.origin,
            status="ok",
            upstream=[],
            downstream=downstream,
        )


def _document_reference(doc: Optional[Document]) -> Optional[str]:
    if doc is None:
        return None
    pel = getattr(doc, "pel_doc_ref", None)
    if pel:
        return str(pel)
    ref = getattr(doc, "reference_number", None)
    return str(ref) if ref else None


__all__ = ["JobLifecycleProducer"]
