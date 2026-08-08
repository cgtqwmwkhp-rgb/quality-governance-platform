"""Job Lifecycle axis service (JL-1 / JL-3 / ADR-0022).

Editable Job Type / Lane / Step vocabulary, cell document membership, and
cell hyperlinks (app · external · audit_outcome). Axis identity is JL
``code`` — never LookupOption or free-text department. Link hrefs resolve
via ``href_registry`` only.

JL-UX-W3 adds read-only freshness: document control status is projected onto
the composer and obsolete documents are refused on attach. The Library and
Document Control tables stay the sole source of truth — nothing about a
document's status is stored on, or derived from, the job lifecycle tables.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable, Mapping, Optional, Sequence
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditFinding, AuditRun, AuditTemplate
from src.domain.models.document import Document
from src.domain.models.document_control import ControlledDocument
from src.domain.models.job_lifecycle import (
    JOB_STEP_PDCA_PHASES,
    JobCell,
    JobCellDocument,
    JobCellLink,
    JobLane,
    JobStep,
    JobType,
)
from src.domain.services.href_registry import audit_finding_href, href_for, job_type_href, registered_entity_types
from src.domain.services.job_lifecycle_freshness import (
    AuditLapseVerdict,
    classify_audit_lapse,
    classify_document_freshness,
    is_obsolete_controlled_status,
    normalise_status,
)

#: Ceiling on a single freshness lookup. The composer asks for the ids it can
#: actually see (a library page plus the attached refs), so this is a guard
#: against a hand-rolled request, not a paging mechanism.
MAX_FRESHNESS_DOCUMENT_IDS = 200


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalise_code(code: str) -> str:
    cleaned = code.strip()
    if not cleaned:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="code must be non-empty",
        )
    return cleaned


def _normalise_pdca_phase(value: Optional[str]) -> Optional[str]:
    """Validate a Deming phase. ``None``/blank clears it — an unset phase is valid."""
    if value is None:
        return None
    cleaned = value.strip().lower()
    if not cleaned:
        return None
    if cleaned not in JOB_STEP_PDCA_PHASES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"pdca_phase must be one of {list(JOB_STEP_PDCA_PHASES)}",
        )
    return cleaned


def list_link_entity_types() -> list[str]:
    """App-link entity types, straight from ``href_registry``.

    The composer dropdown reads this so it cannot offer a type that has no
    builder behind it. ``job_type`` is excluded: nesting is the ``job_cycle``
    kind with its own acyclic guard, not a free-form app link.
    """
    return sorted(t for t in registered_entity_types() if t != "job_type")


def resolve_cell_link_href(link: JobCellLink) -> str:
    """Resolve SPA/external href for a cell link via href_registry (or URL)."""
    kind = (link.kind or "").strip().lower()
    if kind == "app":
        if not link.entity_type or link.entity_id is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="app link missing entity_type/entity_id",
            )
        return href_for(link.entity_type, int(link.entity_id))
    if kind == "external":
        url = (link.external_url or "").strip()
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="external link missing absolute http(s) URL",
            )
        return url
    if kind == "audit_outcome":
        if link.audit_run_id is None:
            return "#"
        return audit_finding_href(
            run_id=int(link.audit_run_id),
            finding_id=int(link.audit_finding_id) if link.audit_finding_id is not None else None,
        )
    if kind == "job_cycle":
        target = getattr(link, "target_job_type_id", None)
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="job_cycle link missing target_job_type_id",
            )
        return job_type_href(int(target))
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=f"unknown cell link kind: {link.kind!r}",
    )


def serialize_cell_link(
    link: JobCellLink,
    *,
    audit_lapse_by_run: Optional[Mapping[int, AuditLapseVerdict]] = None,
) -> dict[str, Any]:
    """Serialize a cell link, attaching an audit-lapse cue where one is known.

    ``audit_lapse`` is populated only for ``audit_outcome`` links and only from
    a prefetched map, so serialization stays synchronous and callers cannot
    accidentally issue a query per link.
    """
    audit_lapse: Optional[dict[str, Any]] = None
    if (link.kind or "").strip().lower() == "audit_outcome" and link.audit_run_id is not None:
        verdict = (audit_lapse_by_run or {}).get(int(link.audit_run_id))
        if verdict is not None:
            audit_lapse = verdict.as_dict()
    return {
        "id": link.id,
        "tenant_id": link.tenant_id,
        "cell_id": link.cell_id,
        "kind": link.kind,
        "label": link.label,
        "entity_type": link.entity_type,
        "entity_id": link.entity_id,
        "external_url": link.external_url,
        "audit_run_id": link.audit_run_id,
        "audit_finding_id": link.audit_finding_id,
        "target_job_type_id": getattr(link, "target_job_type_id", None),
        "href": resolve_cell_link_href(link),
        "audit_lapse": audit_lapse,
        "sort_order": link.sort_order,
        "created_at": link.created_at,
        "updated_at": link.updated_at,
    }


def _dedupe_ids(values: Iterable[int]) -> list[int]:
    """Positive int ids, deduped, order preserved."""
    seen: set[int] = set()
    ordered: list[int] = []
    for value in values:
        as_int = int(value)
        if as_int in seen:
            continue
        seen.add(as_int)
        ordered.append(as_int)
    return ordered


def _controlled_is_stricter(candidate: ControlledDocument, current: ControlledDocument) -> bool:
    """Whether ``candidate`` should displace ``current`` as the doc-control view."""
    candidate_obsolete = is_obsolete_controlled_status(candidate.status)
    current_obsolete = is_obsolete_controlled_status(current.status)
    if candidate_obsolete != current_obsolete:
        return candidate_obsolete
    candidate_due = candidate.next_review_date
    current_due = current.next_review_date
    if candidate_due is None:
        return False
    if current_due is None:
        return True
    return candidate_due < current_due


def _audit_run_ids(links: Iterable[JobCellLink]) -> set[int]:
    """Distinct run ids of the ``audit_outcome`` links in ``links``."""
    return {
        int(link.audit_run_id)
        for link in links
        if (link.kind or "").strip().lower() == "audit_outcome" and link.audit_run_id is not None
    }


class JobLifecycleService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ------------------------------------------------------------------
    # Job types
    # ------------------------------------------------------------------

    async def list_job_types(self, *, tenant_id: int) -> list[JobType]:
        result = await self.db.execute(
            select(JobType)
            .where(JobType.tenant_id == tenant_id, JobType.deleted_at.is_(None))
            .order_by(JobType.sort_order, JobType.id)
        )
        return list(result.scalars().all())

    async def get_job_type(self, *, tenant_id: int, job_type_id: int) -> JobType:
        row = await self._get_live(JobType, tenant_id=tenant_id, row_id=job_type_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job type not found")
        return row

    async def create_job_type(
        self,
        *,
        tenant_id: int,
        code: str,
        name: str,
        description: Optional[str] = None,
        sort_order: int = 0,
        is_active: bool = True,
    ) -> JobType:
        code_n = _normalise_code(code)
        await self._assert_unique_type_code(tenant_id=tenant_id, code=code_n)
        row = JobType(
            tenant_id=tenant_id,
            code=code_n,
            name=name.strip(),
            description=description,
            sort_order=sort_order,
            is_active=is_active,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def update_job_type(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        sort_order: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> JobType:
        row = await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        if name is not None:
            row.name = name.strip()
        if description is not None:
            row.description = description
        if sort_order is not None:
            row.sort_order = sort_order
        if is_active is not None:
            row.is_active = is_active
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def soft_delete_job_type(self, *, tenant_id: int, job_type_id: int) -> None:
        row = await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        row.deleted_at = _utc_now()
        await self.db.commit()

    # ------------------------------------------------------------------
    # Lanes
    # ------------------------------------------------------------------

    async def list_lanes(self, *, tenant_id: int, job_type_id: int) -> list[JobLane]:
        await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        result = await self.db.execute(
            select(JobLane)
            .where(
                JobLane.tenant_id == tenant_id,
                JobLane.job_type_id == job_type_id,
                JobLane.deleted_at.is_(None),
            )
            .order_by(JobLane.sort_order, JobLane.id)
        )
        return list(result.scalars().all())

    async def create_lane(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        code: str,
        name: str,
        description: Optional[str] = None,
        sort_order: int = 0,
        is_active: bool = True,
    ) -> JobLane:
        await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        code_n = _normalise_code(code)
        await self._assert_unique_axis_code(
            model=JobLane,
            tenant_id=tenant_id,
            job_type_id=job_type_id,
            code=code_n,
            label="lane",
        )
        row = JobLane(
            tenant_id=tenant_id,
            job_type_id=job_type_id,
            code=code_n,
            name=name.strip(),
            description=description,
            sort_order=sort_order,
            is_active=is_active,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def update_lane(
        self,
        *,
        tenant_id: int,
        lane_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        sort_order: Optional[int] = None,
        is_active: Optional[bool] = None,
    ) -> JobLane:
        row = await self._get_live(JobLane, tenant_id=tenant_id, row_id=lane_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found")
        if name is not None:
            row.name = name.strip()
        if description is not None:
            row.description = description
        if sort_order is not None:
            row.sort_order = sort_order
        if is_active is not None:
            row.is_active = is_active
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def soft_delete_lane(self, *, tenant_id: int, lane_id: int) -> None:
        row = await self._get_live(JobLane, tenant_id=tenant_id, row_id=lane_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found")
        row.deleted_at = _utc_now()
        await self.db.commit()

    # ------------------------------------------------------------------
    # Steps
    # ------------------------------------------------------------------

    async def list_steps(self, *, tenant_id: int, job_type_id: int) -> list[JobStep]:
        await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        result = await self.db.execute(
            select(JobStep)
            .where(
                JobStep.tenant_id == tenant_id,
                JobStep.job_type_id == job_type_id,
                JobStep.deleted_at.is_(None),
            )
            .order_by(JobStep.sort_order, JobStep.id)
        )
        return list(result.scalars().all())

    async def create_step(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        code: str,
        name: str,
        description: Optional[str] = None,
        sort_order: int = 0,
        is_active: bool = True,
        pdca_phase: Optional[str] = None,
    ) -> JobStep:
        await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        code_n = _normalise_code(code)
        await self._assert_unique_axis_code(
            model=JobStep,
            tenant_id=tenant_id,
            job_type_id=job_type_id,
            code=code_n,
            label="step",
        )
        row = JobStep(
            tenant_id=tenant_id,
            job_type_id=job_type_id,
            code=code_n,
            name=name.strip(),
            description=description,
            sort_order=sort_order,
            is_active=is_active,
            pdca_phase=_normalise_pdca_phase(pdca_phase),
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def update_step(
        self,
        *,
        tenant_id: int,
        step_id: int,
        name: Optional[str] = None,
        description: Optional[str] = None,
        sort_order: Optional[int] = None,
        is_active: Optional[bool] = None,
        pdca_phase: Optional[str] = None,
        pdca_phase_set: bool = False,
    ) -> JobStep:
        row = await self._get_live(JobStep, tenant_id=tenant_id, row_id=step_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")
        if name is not None:
            row.name = name.strip()
        if description is not None:
            row.description = description
        if sort_order is not None:
            row.sort_order = sort_order
        if is_active is not None:
            row.is_active = is_active
        # A bare ``None`` on a PATCH means "not supplied"; clearing the phase
        # requires the explicit flag so the two intents stay distinguishable.
        if pdca_phase is not None or pdca_phase_set:
            row.pdca_phase = _normalise_pdca_phase(pdca_phase)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def soft_delete_step(self, *, tenant_id: int, step_id: int) -> None:
        row = await self._get_live(JobStep, tenant_id=tenant_id, row_id=step_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")
        row.deleted_at = _utc_now()
        await self.db.commit()

    # ------------------------------------------------------------------
    # Freshness (JL-UX-W3) — read-only projection of the document SSOT
    # ------------------------------------------------------------------

    async def document_freshness(
        self,
        *,
        tenant_id: int,
        library_document_ids: Sequence[int],
    ) -> list[dict[str, Any]]:
        """Freshness for the given library documents, in the order requested.

        An id the tenant cannot see is returned as ``unknown`` /
        ``document_not_found`` rather than omitted, so the composer can render
        an honest "unknown" chip instead of silently showing nothing.
        """
        ordered_ids = _dedupe_ids(library_document_ids)
        if len(ordered_ids) > MAX_FRESHNESS_DOCUMENT_IDS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"library_document_ids may not exceed {MAX_FRESHNESS_DOCUMENT_IDS} entries",
            )
        if not ordered_ids:
            return []

        docs_result = await self.db.execute(
            select(Document).where(
                Document.tenant_id == tenant_id,
                Document.id.in_(ordered_ids),
            )
        )
        docs_by_id = {int(doc.id): doc for doc in docs_result.scalars().all()}
        controlled_by_doc = await self._controlled_documents_by_library_id(
            tenant_id=tenant_id,
            library_document_ids=ordered_ids,
        )

        items: list[dict[str, Any]] = []
        for doc_id in ordered_ids:
            doc = docs_by_id.get(doc_id)
            controlled = controlled_by_doc.get(doc_id)
            verdict = classify_document_freshness(
                library_status=getattr(doc, "status", None),
                controlled_status=getattr(controlled, "status", None),
                library_review_date=getattr(doc, "review_date", None),
                controlled_next_review_date=getattr(controlled, "next_review_date", None),
                found=doc is not None,
            )
            items.append(
                {
                    "library_document_id": doc_id,
                    "found": doc is not None,
                    "title": getattr(doc, "title", None),
                    "reference": getattr(doc, "reference_number", None),
                    "library_status": normalise_status(getattr(doc, "status", None)),
                    "controlled_status": normalise_status(getattr(controlled, "status", None)),
                    **verdict.as_dict(),
                }
            )
        return items

    async def _controlled_documents_by_library_id(
        self,
        *,
        tenant_id: int,
        library_document_ids: Sequence[int],
    ) -> dict[int, ControlledDocument]:
        """One controlled document per library id, picking the strictest.

        ``controlled_documents.library_document_id`` is not unique, so a library
        document can carry more than one controlled record. An obsolete record
        wins outright — doc control having withdrawn *any* controlled copy is
        the answer that matters on attach — and otherwise the earliest
        ``next_review_date`` wins so the verdict is never softer than the SSOT.
        """
        if not library_document_ids:
            return {}
        result = await self.db.execute(
            select(ControlledDocument).where(
                ControlledDocument.tenant_id == tenant_id,
                ControlledDocument.library_document_id.in_(list(library_document_ids)),
            )
        )
        chosen: dict[int, ControlledDocument] = {}
        for row in result.scalars().all():
            key = int(row.library_document_id) if row.library_document_id is not None else None
            if key is None:
                continue
            current = chosen.get(key)
            if current is None or _controlled_is_stricter(row, current):
                chosen[key] = row
        return chosen

    async def _assert_no_obsolete_attachments(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        lane_id: int,
        step_id: int,
        requested_ids: Sequence[int],
    ) -> None:
        """Refuse to *add* an obsolete document reference to a cell.

        Only newly added ids are checked. A document that went obsolete after it
        was attached must stay removable: enforcing on the whole membership list
        would make every subsequent PUT on that cell fail, trapping the operator
        with the very reference they are trying to clear.
        """
        if not requested_ids:
            return
        cell = await self._find_cell(
            tenant_id=tenant_id,
            job_type_id=job_type_id,
            lane_id=lane_id,
            step_id=step_id,
        )
        already_attached: set[int] = set()
        if cell is not None:
            existing = await self.db.execute(
                select(JobCellDocument.library_document_id).where(
                    JobCellDocument.tenant_id == tenant_id,
                    JobCellDocument.cell_id == cell.id,
                )
            )
            already_attached = {int(r) for r in existing.scalars().all() if r is not None}

        added = [doc_id for doc_id in requested_ids if doc_id not in already_attached]
        if not added:
            return

        blocked: list[str] = []
        for item in await self.document_freshness(tenant_id=tenant_id, library_document_ids=added):
            if not item["is_obsolete"]:
                continue
            source = (
                item["controlled_status"] if item["reason"] == "obsolete_controlled_status" else item["library_status"]
            )
            blocked.append(f"{item['library_document_id']} ({source})")
        if blocked:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Obsolete documents cannot be attached — the Library / Document Control "
                    f"record is the source of truth: {', '.join(blocked)}"
                ),
            )

    async def _audit_lapse_map(
        self,
        *,
        tenant_id: int,
        run_ids: Sequence[int] | set[int],
    ) -> dict[int, AuditLapseVerdict]:
        """Lapse verdict per audit run, from the run's dates and template cadence."""
        ids = sorted({int(r) for r in run_ids})
        if not ids:
            return {}
        result = await self.db.execute(
            select(
                AuditRun.id,
                AuditRun.completed_at,
                AuditRun.due_date,
                AuditTemplate.frequency,
            )
            .join(AuditTemplate, AuditTemplate.id == AuditRun.template_id, isouter=True)
            .where(AuditRun.tenant_id == tenant_id, AuditRun.id.in_(ids))
        )
        verdicts: dict[int, AuditLapseVerdict] = {}
        for run_id, completed_at, due_date, frequency in result.all():
            verdicts[int(run_id)] = classify_audit_lapse(
                completed_at=completed_at,
                due_date=due_date,
                frequency=frequency,
            )
        return verdicts

    # ------------------------------------------------------------------
    # Cells + document membership
    # ------------------------------------------------------------------

    async def set_cell_documents(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        lane_id: int,
        step_id: int,
        library_document_ids: Sequence[int],
        include_links: bool = False,
    ) -> dict[str, Any]:
        await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        lane = await self._get_live(JobLane, tenant_id=tenant_id, row_id=lane_id)
        step = await self._get_live(JobStep, tenant_id=tenant_id, row_id=step_id)
        if lane is None or lane.job_type_id != job_type_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found for job type")
        if step is None or step.job_type_id != job_type_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found for job type")

        ordered_ids = _dedupe_ids(library_document_ids)

        if ordered_ids:
            docs = await self.db.execute(
                select(Document.id).where(
                    Document.tenant_id == tenant_id,
                    Document.id.in_(ordered_ids),
                )
            )
            found = {int(r) for r in docs.scalars().all()}
            missing = [i for i in ordered_ids if i not in found]
            if missing:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"library_document_ids not found in tenant: {missing}",
                )

        await self._assert_no_obsolete_attachments(
            tenant_id=tenant_id,
            job_type_id=job_type_id,
            lane_id=lane_id,
            step_id=step_id,
            requested_ids=ordered_ids,
        )

        cell = await self._get_or_create_cell(
            tenant_id=tenant_id,
            job_type_id=job_type_id,
            lane_id=lane_id,
            step_id=step_id,
        )

        existing = await self.db.execute(
            select(JobCellDocument).where(
                JobCellDocument.tenant_id == tenant_id,
                JobCellDocument.cell_id == cell.id,
            )
        )
        for row in existing.scalars().all():
            await self.db.delete(row)

        for idx, doc_id in enumerate(ordered_ids):
            self.db.add(
                JobCellDocument(
                    tenant_id=tenant_id,
                    cell_id=cell.id,
                    library_document_id=doc_id,
                    sort_order=idx,
                )
            )
        await self.db.commit()
        await self.db.refresh(cell)
        return await self._cell_payload(cell, include_links=include_links)

    async def _cell_payload(
        self,
        cell: JobCell,
        *,
        include_links: bool = False,
        audit_lapse_by_run: Optional[Mapping[int, AuditLapseVerdict]] = None,
    ) -> dict[str, Any]:
        result = await self.db.execute(
            select(JobCellDocument)
            .where(
                JobCellDocument.tenant_id == cell.tenant_id,
                JobCellDocument.cell_id == cell.id,
            )
            .order_by(JobCellDocument.sort_order, JobCellDocument.id)
        )
        docs = list(result.scalars().all())
        links: list[dict[str, Any]] = []
        if include_links:
            link_result = await self.db.execute(
                select(JobCellLink)
                .where(
                    JobCellLink.tenant_id == cell.tenant_id,
                    JobCellLink.cell_id == cell.id,
                )
                .order_by(JobCellLink.sort_order, JobCellLink.id)
            )
            link_rows = list(link_result.scalars().all())
            lapse_map = audit_lapse_by_run
            if lapse_map is None:
                lapse_map = await self._audit_lapse_map(
                    tenant_id=cell.tenant_id,
                    run_ids=_audit_run_ids(link_rows),
                )
            links = [serialize_cell_link(row, audit_lapse_by_run=lapse_map) for row in link_rows]
        return {
            "id": cell.id,
            "tenant_id": cell.tenant_id,
            "job_type_id": cell.job_type_id,
            "lane_id": cell.lane_id,
            "step_id": cell.step_id,
            "library_document_ids": [d.library_document_id for d in docs],
            "links": links,
            "created_at": cell.created_at,
            "updated_at": cell.updated_at,
        }

    async def list_cells(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        include_links: bool = False,
    ) -> list[dict[str, Any]]:
        await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        result = await self.db.execute(
            select(JobCell).where(
                JobCell.tenant_id == tenant_id,
                JobCell.job_type_id == job_type_id,
                JobCell.deleted_at.is_(None),
            )
        )
        cells = list(result.scalars().all())
        # Prefetch every audit-lapse verdict for the pack in one query; the
        # per-cell payload would otherwise add a third query per cell.
        lapse_map: Optional[Mapping[int, AuditLapseVerdict]] = None
        if include_links:
            run_result = await self.db.execute(
                select(JobCellLink.audit_run_id)
                .join(JobCell, JobCell.id == JobCellLink.cell_id)
                .where(
                    JobCellLink.tenant_id == tenant_id,
                    JobCellLink.kind == "audit_outcome",
                    JobCellLink.audit_run_id.is_not(None),
                    JobCell.tenant_id == tenant_id,
                    JobCell.job_type_id == job_type_id,
                    JobCell.deleted_at.is_(None),
                )
            )
            lapse_map = await self._audit_lapse_map(
                tenant_id=tenant_id,
                run_ids={int(r) for r in run_result.scalars().all() if r is not None},
            )
        return [
            await self._cell_payload(
                cell,
                include_links=include_links,
                audit_lapse_by_run=lapse_map,
            )
            for cell in cells
        ]

    async def list_cell_links(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        lane_id: int,
        step_id: int,
    ) -> list[dict[str, Any]]:
        cell = await self._require_cell(
            tenant_id=tenant_id,
            job_type_id=job_type_id,
            lane_id=lane_id,
            step_id=step_id,
        )
        result = await self.db.execute(
            select(JobCellLink)
            .where(
                JobCellLink.tenant_id == tenant_id,
                JobCellLink.cell_id == cell.id,
            )
            .order_by(JobCellLink.sort_order, JobCellLink.id)
        )
        rows = list(result.scalars().all())
        lapse_map = await self._audit_lapse_map(tenant_id=tenant_id, run_ids=_audit_run_ids(rows))
        return [serialize_cell_link(row, audit_lapse_by_run=lapse_map) for row in rows]

    async def create_cell_link(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        lane_id: int,
        step_id: int,
        kind: str,
        label: str,
        entity_type: Optional[str] = None,
        entity_id: Optional[int] = None,
        external_url: Optional[str] = None,
        audit_run_id: Optional[int] = None,
        audit_finding_id: Optional[int] = None,
        target_job_type_id: Optional[int] = None,
        sort_order: int = 0,
    ) -> dict[str, Any]:
        cell = await self._get_or_create_cell(
            tenant_id=tenant_id,
            job_type_id=job_type_id,
            lane_id=lane_id,
            step_id=step_id,
        )
        kind_n = kind.strip().lower()
        if kind_n == "job_cycle":
            await self._assert_nestable_job_cycle(
                tenant_id=tenant_id,
                source_job_type_id=job_type_id,
                target_job_type_id=target_job_type_id,
            )
            existing_nest = await self.db.execute(
                select(JobCellLink.id).where(
                    JobCellLink.tenant_id == tenant_id,
                    JobCellLink.cell_id == cell.id,
                    JobCellLink.target_job_type_id == target_job_type_id,
                )
            )
            if existing_nest.scalars().first() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="job_cycle link already exists for this target on the cell",
                )
        elif kind_n == "audit_outcome":
            await self._assert_audit_finding(
                tenant_id=tenant_id,
                audit_run_id=int(audit_run_id) if audit_run_id is not None else None,
                audit_finding_id=int(audit_finding_id) if audit_finding_id is not None else None,
            )
            # Unique (cell, finding) — reject duplicates early
            existing = await self.db.execute(
                select(JobCellLink.id).where(
                    JobCellLink.tenant_id == tenant_id,
                    JobCellLink.cell_id == cell.id,
                    JobCellLink.audit_finding_id == audit_finding_id,
                )
            )
            if existing.scalars().first() is not None:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="audit_outcome link already exists for this finding on the cell",
                )
        elif kind_n == "app":
            if not entity_type or entity_id is None:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="app links require entity_type and entity_id",
                )
            # Resolve once so unknown types still get a stable fallback href
            _ = href_for(entity_type, entity_id)
        row = JobCellLink(
            tenant_id=tenant_id,
            cell_id=cell.id,
            kind=kind_n,
            label=label.strip(),
            entity_type=entity_type,
            entity_id=entity_id,
            external_url=external_url,
            audit_run_id=audit_run_id,
            audit_finding_id=audit_finding_id,
            target_job_type_id=target_job_type_id,
            sort_order=sort_order,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        lapse_map = await self._audit_lapse_map(tenant_id=tenant_id, run_ids=_audit_run_ids([row]))
        return serialize_cell_link(row, audit_lapse_by_run=lapse_map)

    async def delete_cell_link(self, *, tenant_id: int, link_id: int) -> None:
        result = await self.db.execute(
            select(JobCellLink).where(
                JobCellLink.id == link_id,
                JobCellLink.tenant_id == tenant_id,
            )
        )
        row = result.scalars().first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Cell link not found")
        await self.db.delete(row)
        await self.db.commit()

    async def _find_cell(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        lane_id: int,
        step_id: int,
    ) -> Optional[JobCell]:
        """Read-only cell lookup — never creates, so a failed guard writes nothing."""
        result = await self.db.execute(
            select(JobCell).where(
                JobCell.tenant_id == tenant_id,
                JobCell.job_type_id == job_type_id,
                JobCell.lane_id == lane_id,
                JobCell.step_id == step_id,
                JobCell.deleted_at.is_(None),
            )
        )
        return result.scalars().first()

    async def _require_cell(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        lane_id: int,
        step_id: int,
    ) -> JobCell:
        cell = await self._find_cell(
            tenant_id=tenant_id,
            job_type_id=job_type_id,
            lane_id=lane_id,
            step_id=step_id,
        )
        if cell is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job cell not found")
        return cell

    # ------------------------------------------------------------------
    # Job cycle nesting (JL-UX-W2)
    # ------------------------------------------------------------------

    async def nested_job_type_ids(self, *, tenant_id: int, job_type_id: int) -> list[int]:
        """Job types nested directly inside ``job_type_id`` via ``job_cycle`` links."""
        result = await self.db.execute(
            select(JobCellLink.target_job_type_id)
            .join(JobCell, JobCell.id == JobCellLink.cell_id)
            .where(
                JobCellLink.tenant_id == tenant_id,
                JobCellLink.kind == "job_cycle",
                JobCellLink.target_job_type_id.is_not(None),
                JobCell.tenant_id == tenant_id,
                JobCell.job_type_id == job_type_id,
                JobCell.deleted_at.is_(None),
            )
        )
        seen: set[int] = set()
        ordered: list[int] = []
        for target in result.scalars().all():
            if target is None or int(target) in seen:
                continue
            seen.add(int(target))
            ordered.append(int(target))
        return ordered

    async def would_create_job_cycle_nest_cycle(
        self,
        *,
        tenant_id: int,
        source_job_type_id: int,
        target_job_type_id: int,
    ) -> bool:
        """True if nesting ``target`` inside ``source`` would close a cycle.

        Graph direction: a ``job_cycle`` link on a cell of job type ``source``
        means ``source`` nests ``target``. Adding it closes a cycle when
        ``target`` can already reach ``source`` by walking nest edges. Same BFS
        shape as ``DocumentGraphService.would_create_implements_cycle`` — and
        the same guarantee: read-then-write, so two concurrent inserts that each
        pass on their own can still form a cycle together.
        """
        if source_job_type_id == target_job_type_id:
            return True

        frontier = [target_job_type_id]
        seen: set[int] = {target_job_type_id}
        while frontier:
            current = frontier.pop()
            for nested_id in await self.nested_job_type_ids(tenant_id=tenant_id, job_type_id=current):
                if nested_id == source_job_type_id:
                    return True
                if nested_id not in seen:
                    seen.add(nested_id)
                    frontier.append(nested_id)
        return False

    async def _assert_nestable_job_cycle(
        self,
        *,
        tenant_id: int,
        source_job_type_id: int,
        target_job_type_id: Optional[int],
    ) -> None:
        if target_job_type_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="job_cycle links require target_job_type_id",
            )
        target = int(target_job_type_id)
        # Any JobType may nest any other JobType — the only rules are tenancy,
        # liveness and acyclicity. No pair of packs is privileged.
        if await self._get_live(JobType, tenant_id=tenant_id, row_id=target) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target job type not found",
            )
        if target == int(source_job_type_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="A job cycle cannot nest itself",
            )
        if await self.would_create_job_cycle_nest_cycle(
            tenant_id=tenant_id,
            source_job_type_id=int(source_job_type_id),
            target_job_type_id=target,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="job_cycle link would create a nesting cycle",
            )

    async def _assert_audit_finding(
        self,
        *,
        tenant_id: int,
        audit_run_id: Optional[int],
        audit_finding_id: Optional[int],
    ) -> None:
        if audit_run_id is None or audit_finding_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="audit_outcome links require audit_run_id and audit_finding_id",
            )
        result = await self.db.execute(
            select(AuditFinding).where(
                AuditFinding.id == audit_finding_id,
                AuditFinding.tenant_id == tenant_id,
            )
        )
        finding = result.scalars().first()
        if finding is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Audit finding not found",
            )
        if int(finding.run_id) != int(audit_run_id):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="audit_finding_id does not belong to audit_run_id",
            )

    async def _get_or_create_cell(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        lane_id: int,
        step_id: int,
    ) -> JobCell:
        result = await self.db.execute(
            select(JobCell).where(
                JobCell.tenant_id == tenant_id,
                JobCell.job_type_id == job_type_id,
                JobCell.lane_id == lane_id,
                JobCell.step_id == step_id,
                JobCell.deleted_at.is_(None),
            )
        )
        cell = result.scalars().first()
        if cell is not None:
            return cell
        # Validate axes belong to the job type before creating the cell.
        lane = await self._get_live(JobLane, tenant_id=tenant_id, row_id=lane_id)
        step = await self._get_live(JobStep, tenant_id=tenant_id, row_id=step_id)
        if lane is None or step is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lane or step not found")
        if lane.job_type_id != job_type_id or step.job_type_id != job_type_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Lane and step must belong to the job type",
            )
        cell = JobCell(
            tenant_id=tenant_id,
            job_type_id=job_type_id,
            lane_id=lane_id,
            step_id=step_id,
        )
        self.db.add(cell)
        await self.db.flush()
        return cell

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    async def _get_live(self, model: type[Any], *, tenant_id: int, row_id: int) -> Optional[Any]:
        result = await self.db.execute(
            select(model).where(
                model.id == row_id,
                model.tenant_id == tenant_id,
                model.deleted_at.is_(None),
            )
        )
        return result.scalars().first()

    async def _assert_unique_type_code(self, *, tenant_id: int, code: str) -> None:
        result = await self.db.execute(
            select(JobType.id).where(
                JobType.tenant_id == tenant_id,
                JobType.code == code,
                JobType.deleted_at.is_(None),
            )
        )
        if result.scalars().first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job type code already exists: {code}",
            )

    async def _assert_unique_axis_code(
        self,
        *,
        model: type[Any],
        tenant_id: int,
        job_type_id: int,
        code: str,
        label: str,
    ) -> None:
        result = await self.db.execute(
            select(model.id).where(
                model.tenant_id == tenant_id,
                model.job_type_id == job_type_id,
                model.code == code,
                model.deleted_at.is_(None),
            )
        )
        if result.scalars().first() is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Job {label} code already exists: {code}",
            )


__all__ = [
    "MAX_FRESHNESS_DOCUMENT_IDS",
    "JobLifecycleService",
    "list_link_entity_types",
    "resolve_cell_link_href",
    "serialize_cell_link",
]
