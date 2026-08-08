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
    JobTypeBaseline,
)
from src.domain.services.href_registry import audit_finding_href, href_for, job_type_href, registered_entity_types
from src.domain.services.job_lifecycle_baseline import build_snapshot, diff_snapshots, viewing_baseline_banner
from src.domain.services.job_lifecycle_concurrency import if_match_matches, job_lifecycle_etag
from src.domain.services.job_lifecycle_freshness import (
    AuditLapseVerdict,
    classify_audit_lapse,
    classify_document_freshness,
    is_obsolete_controlled_status,
    normalise_status,
)
from src.domain.services.job_lifecycle_graph import (
    CellReadinessVerdict,
    JobGraphBuilder,
    JobGraphEdge,
    JobGraphNode,
    clamp_audit_trail_limit,
    clamp_cycle_graph_depth,
    classify_cell_readiness,
    edge_key,
    node_key,
    select_trail_cells,
    summarise_readiness,
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


def _document_label(document: Any, document_id: int) -> str:
    """Reference · title when the library has both; never a bare id if avoidable."""
    if document is None:
        return f"Document #{document_id}"
    title = (getattr(document, "title", None) or "").strip()
    reference = (getattr(document, "reference_number", None) or "").strip()
    if reference and title:
        return f"{reference} · {title}"
    return title or reference or f"Document #{document_id}"


def _trail_link_edge_kind(link: JobCellLink) -> str:
    """Edge vocabulary for a cell link, shared with the interaction map."""
    kind = (link.kind or "").strip().lower()
    if kind == "job_cycle":
        return "nests"
    if kind == "audit_outcome":
        return "audits"
    return "references"


def _trail_link_node(link: JobCellLink, nested_names: Mapping[int, str]) -> Optional[JobGraphNode]:
    """Node a cell link points at, or ``None`` when the link cannot resolve.

    A link with no usable target is skipped rather than drawn as a dead end:
    the trail is meant to be walkable, and an edge to nothing is worse than a
    missing edge because it reads as evidence that exists.
    """
    kind = (link.kind or "").strip().lower()
    if kind == "job_cycle":
        target = getattr(link, "target_job_type_id", None)
        if target is None:
            return None
        target_id = int(target)
        return JobGraphNode(
            key=node_key("job_type", target_id),
            kind="job_type",
            ref_id=target_id,
            label=nested_names.get(target_id) or link.label or f"Job cycle #{target_id}",
            href=job_type_href(target_id),
            detail=None if target_id in nested_names else "unavailable",
        )
    if kind == "audit_outcome":
        if link.audit_run_id is None:
            return None
        ref_id = int(link.audit_finding_id) if link.audit_finding_id is not None else int(link.audit_run_id)
        return JobGraphNode(
            key=node_key("audit_finding", ref_id),
            kind="audit_finding",
            ref_id=ref_id,
            label=link.label,
            href=audit_finding_href(
                run_id=int(link.audit_run_id),
                finding_id=int(link.audit_finding_id) if link.audit_finding_id is not None else None,
            ),
            detail=f"audit run #{int(link.audit_run_id)}",
        )
    if kind == "app":
        if not link.entity_type or link.entity_id is None:
            return None
        return JobGraphNode(
            key=node_key("app", int(link.id)),
            kind="app",
            ref_id=int(link.id),
            label=link.label,
            href=href_for(link.entity_type, int(link.entity_id)),
            detail=link.entity_type,
        )
    if kind == "external":
        url = (link.external_url or "").strip()
        if not url:
            return None
        return JobGraphNode(
            key=node_key("external", int(link.id)),
            kind="external",
            ref_id=int(link.id),
            label=link.label,
            href=url,
            detail="external",
        )
    return None


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
        if_match: Optional[str] = None,
    ) -> JobType:
        row = await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        self._assert_if_match(row, if_match, label="Job cycle")
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

    def _assert_if_match(self, row: Any, if_match: Optional[str], *, label: str) -> None:
        """Refuse a stale edit (JL-UX-W4).

        Opt-in: no header means the caller did not read a version to compare,
        so the write proceeds as it always has. A malformed header is a 400
        rather than a silent pass — a precondition that cannot be evaluated
        must not be treated as satisfied.
        """
        if if_match is None:
            return
        try:
            matched = if_match_matches(if_match=if_match, updated_at=getattr(row, "updated_at", None))
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"If-Match must carry the updated_at value that was read ({exc})",
            ) from exc
        if not matched:
            current = job_lifecycle_etag(getattr(row, "updated_at", None))
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"{label} was changed by someone else since you loaded it. "
                    f"Reload before saving — current updated_at is {current}."
                ),
            )

    async def clone_job_type(
        self,
        *,
        tenant_id: int,
        source_job_type_id: int,
        code: str,
        name: str,
        description: Optional[str] = None,
        include_inactive: bool = True,
    ) -> dict[str, Any]:
        """Copy a pack's **axes** into a new job cycle. Cells stay empty.

        Deliberately not a deep copy. Cloning cells would clone
        ``library_document_id`` references, and a reference is a governance
        claim that *this* pack is evidenced by that document — a claim the act
        of copying a template cannot make on the new pack's behalf. Links are
        left behind for the same reason, and no document is ever duplicated:
        the library remains the single copy of any document.
        """
        source = await self.get_job_type(tenant_id=tenant_id, job_type_id=source_job_type_id)
        code_n = _normalise_code(code)
        await self._assert_unique_type_code(tenant_id=tenant_id, code=code_n)

        lanes = await self.list_lanes(tenant_id=tenant_id, job_type_id=source_job_type_id)
        steps = await self.list_steps(tenant_id=tenant_id, job_type_id=source_job_type_id)
        if not include_inactive:
            lanes = [lane for lane in lanes if lane.is_active]
            steps = [step for step in steps if step.is_active]

        clone = JobType(
            tenant_id=tenant_id,
            code=code_n,
            name=name.strip(),
            description=description if description is not None else source.description,
            sort_order=source.sort_order,
            is_active=True,
        )
        self.db.add(clone)
        await self.db.flush()

        for lane in lanes:
            self.db.add(
                JobLane(
                    tenant_id=tenant_id,
                    job_type_id=clone.id,
                    code=lane.code,
                    name=lane.name,
                    description=lane.description,
                    sort_order=lane.sort_order,
                    is_active=lane.is_active,
                )
            )
        for step in steps:
            self.db.add(
                JobStep(
                    tenant_id=tenant_id,
                    job_type_id=clone.id,
                    code=step.code,
                    name=step.name,
                    description=step.description,
                    sort_order=step.sort_order,
                    is_active=step.is_active,
                    pdca_phase=step.pdca_phase,
                )
            )
        await self.db.commit()
        await self.db.refresh(clone)
        return {
            "job_type": clone,
            "source_job_type_id": int(source_job_type_id),
            "cloned_lane_count": len(lanes),
            "cloned_step_count": len(steps),
            "cloned_cell_count": 0,
            "cloned_document_count": 0,
        }

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
        if_match: Optional[str] = None,
    ) -> JobLane:
        row = await self._get_live(JobLane, tenant_id=tenant_id, row_id=lane_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lane not found")
        self._assert_if_match(row, if_match, label="Lane")
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
        if_match: Optional[str] = None,
    ) -> JobStep:
        row = await self._get_live(JobStep, tenant_id=tenant_id, row_id=step_id)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")
        self._assert_if_match(row, if_match, label="Step")
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
            "requires_evidence": bool(getattr(cell, "requires_evidence", False)),
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

    async def set_cell_requirement(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        lane_id: int,
        step_id: int,
        requires_evidence: bool,
        include_links: bool = False,
    ) -> dict[str, Any]:
        """Mark (or unmark) a lane × step intersection as owing evidence.

        Creates the cell when it does not exist yet, because marking an *empty*
        cell mandatory is the whole point: that is how a gap becomes visible
        rather than reading as a deliberate blank.
        """
        await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        cell = await self._get_or_create_cell(
            tenant_id=tenant_id,
            job_type_id=job_type_id,
            lane_id=lane_id,
            step_id=step_id,
        )
        cell.requires_evidence = bool(requires_evidence)
        await self.db.commit()
        await self.db.refresh(cell)
        return await self._cell_payload(cell, include_links=include_links)

    # ------------------------------------------------------------------
    # Evidence readiness (JL-UX-W4) — derived, never stored
    # ------------------------------------------------------------------

    async def _freshness_by_document_id(
        self,
        *,
        tenant_id: int,
        document_ids: Sequence[int],
    ) -> dict[int, dict[str, Any]]:
        """Freshness verdicts keyed by document id, chunked under the id cap."""
        ordered = _dedupe_ids(document_ids)
        index: dict[int, dict[str, Any]] = {}
        for start in range(0, len(ordered), MAX_FRESHNESS_DOCUMENT_IDS):
            chunk = ordered[start : start + MAX_FRESHNESS_DOCUMENT_IDS]
            for item in await self.document_freshness(tenant_id=tenant_id, library_document_ids=chunk):
                index[int(item["library_document_id"])] = item
        return index

    @staticmethod
    def _obsolete_and_unresolved(
        freshness: Mapping[int, Mapping[str, Any]],
    ) -> tuple[set[int], set[int]]:
        """Split a freshness index into withdrawn ids and ids we could not read."""
        obsolete = {doc_id for doc_id, item in freshness.items() if item.get("is_obsolete")}
        unresolved = {doc_id for doc_id, item in freshness.items() if not item.get("found")}
        return obsolete, unresolved

    async def _cells_with_axis_context(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
    ) -> list[dict[str, Any]]:
        """Live cells of a pack with their lane / step names, in pack order."""
        result = await self.db.execute(
            select(
                JobCell.id,
                JobCell.lane_id,
                JobCell.step_id,
                JobCell.requires_evidence,
                JobLane.name,
                JobStep.name,
            )
            .join(JobLane, JobLane.id == JobCell.lane_id)
            .join(JobStep, JobStep.id == JobCell.step_id)
            .where(
                JobCell.tenant_id == tenant_id,
                JobCell.job_type_id == job_type_id,
                JobCell.deleted_at.is_(None),
            )
            .order_by(JobLane.sort_order, JobLane.id, JobStep.sort_order, JobStep.id)
        )
        return [
            {
                "cell_id": int(cell_id),
                "lane_id": int(lane_id),
                "step_id": int(step_id),
                "requires_evidence": bool(requires_evidence),
                "lane_name": lane_name,
                "step_name": step_name,
            }
            for cell_id, lane_id, step_id, requires_evidence, lane_name, step_name in result.all()
        ]

    async def _documents_by_cell(
        self,
        *,
        tenant_id: int,
        cell_ids: Sequence[int],
    ) -> dict[int, list[int]]:
        """Attached ``library_document_id`` per cell, in the operator's order."""
        if not cell_ids:
            return {}
        result = await self.db.execute(
            select(JobCellDocument.cell_id, JobCellDocument.library_document_id)
            .where(
                JobCellDocument.tenant_id == tenant_id,
                JobCellDocument.cell_id.in_(list(cell_ids)),
            )
            .order_by(JobCellDocument.cell_id, JobCellDocument.sort_order, JobCellDocument.id)
        )
        by_cell: dict[int, list[int]] = {}
        for cell_id, document_id in result.all():
            by_cell.setdefault(int(cell_id), []).append(int(document_id))
        return by_cell

    async def _links_by_cell(
        self,
        *,
        tenant_id: int,
        cell_ids: Sequence[int],
    ) -> dict[int, list[JobCellLink]]:
        if not cell_ids:
            return {}
        result = await self.db.execute(
            select(JobCellLink)
            .where(
                JobCellLink.tenant_id == tenant_id,
                JobCellLink.cell_id.in_(list(cell_ids)),
            )
            .order_by(JobCellLink.cell_id, JobCellLink.sort_order, JobCellLink.id)
        )
        by_cell: dict[int, list[JobCellLink]] = {}
        for row in result.scalars().all():
            by_cell.setdefault(int(row.cell_id), []).append(row)
        return by_cell

    async def _documents_by_id(
        self,
        *,
        tenant_id: int,
        document_ids: Sequence[int],
    ) -> dict[int, Any]:
        if not document_ids:
            return {}
        result = await self.db.execute(
            select(Document).where(
                Document.tenant_id == tenant_id,
                Document.id.in_(_dedupe_ids(document_ids)),
            )
        )
        return {int(doc.id): doc for doc in result.scalars().all()}

    async def evidence_readiness(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        assure: bool = False,
    ) -> dict[str, Any]:
        """Readiness of every cell in the pack that requires evidence.

        Nothing here is stored. With ``assure`` off this reports presence only,
        which is all the composer can claim without reading the document SSOT;
        with it on, a withdrawn attachment fails the cell and a document that
        cannot be read reports ``unknown`` rather than passing.
        """
        await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        cells = await self._cells_with_axis_context(tenant_id=tenant_id, job_type_id=job_type_id)
        mandatory = [c for c in cells if c["requires_evidence"]]
        docs_by_cell = await self._documents_by_cell(
            tenant_id=tenant_id,
            cell_ids=[c["cell_id"] for c in mandatory],
        )
        obsolete_ids: set[int] = set()
        unresolved_ids: set[int] = set()
        if assure and mandatory:
            every_id = [doc_id for cell in mandatory for doc_id in docs_by_cell.get(cell["cell_id"], [])]
            freshness = await self._freshness_by_document_id(tenant_id=tenant_id, document_ids=every_id)
            obsolete_ids, unresolved_ids = self._obsolete_and_unresolved(freshness)

        items: list[dict[str, Any]] = []
        verdicts: list[CellReadinessVerdict] = []
        for cell in mandatory:
            document_ids = docs_by_cell.get(cell["cell_id"], [])
            verdict = classify_cell_readiness(
                requires_evidence=True,
                document_ids=document_ids,
                obsolete_ids=obsolete_ids,
                unresolved_ids=unresolved_ids,
                assure=assure,
            )
            verdicts.append(verdict)
            items.append({**cell, "library_document_ids": document_ids, **verdict.as_dict()})
        return {
            "job_type_id": int(job_type_id),
            "assure": bool(assure),
            "items": items,
            "total": len(items),
            "summary": summarise_readiness(verdicts),
        }

    # ------------------------------------------------------------------
    # Process interaction map + audit trail (JL-UX-W4) — one edge model
    # ------------------------------------------------------------------

    async def _nest_link_rows(
        self,
        *,
        tenant_id: int,
        source_job_type_ids: Sequence[int],
    ) -> list[dict[str, Any]]:
        """``job_cycle`` links leaving the given packs, with their source cell."""
        ids = [int(i) for i in source_job_type_ids]
        if not ids:
            return []
        result = await self.db.execute(
            select(
                JobCellLink.id,
                JobCellLink.label,
                JobCellLink.target_job_type_id,
                JobCell.id,
                JobCell.job_type_id,
                JobCell.lane_id,
                JobCell.step_id,
            )
            .join(JobCell, JobCell.id == JobCellLink.cell_id)
            .where(
                JobCellLink.tenant_id == tenant_id,
                JobCellLink.kind == "job_cycle",
                JobCellLink.target_job_type_id.is_not(None),
                JobCell.tenant_id == tenant_id,
                JobCell.job_type_id.in_(ids),
                JobCell.deleted_at.is_(None),
            )
            .order_by(JobCell.lane_id, JobCell.step_id, JobCellLink.sort_order, JobCellLink.id)
        )
        return [
            {
                "link_id": int(link_id),
                "label": label,
                "target_job_type_id": int(target_job_type_id),
                "cell_id": int(cell_id),
                "source_job_type_id": int(source_job_type_id),
                "lane_id": int(lane_id),
                "step_id": int(step_id),
            }
            for link_id, label, target_job_type_id, cell_id, source_job_type_id, lane_id, step_id in result.all()
            if target_job_type_id is not None
        ]

    async def _live_job_type_names(
        self,
        *,
        tenant_id: int,
        job_type_ids: Iterable[int],
    ) -> dict[int, str]:
        ids = _dedupe_ids(job_type_ids)
        if not ids:
            return {}
        result = await self.db.execute(
            select(JobType.id, JobType.name).where(
                JobType.tenant_id == tenant_id,
                JobType.id.in_(ids),
                JobType.deleted_at.is_(None),
            )
        )
        return {int(row_id): name for row_id, name in result.all()}

    async def cycle_graph(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        depth: Optional[int] = None,
    ) -> dict[str, Any]:
        """Process interaction map: job cycles and the nest links between them.

        A **view**, not a second source of truth. Every edge is one
        ``job_cycle`` cell link — delete the link in the composer and the line
        disappears, because there is nowhere else for it to be recorded. Two
        packs nested through two different cells draw two edges for the same
        reason.
        """
        root = await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        max_depth = clamp_cycle_graph_depth(depth)

        builder = JobGraphBuilder()
        builder.add_node(
            JobGraphNode(
                key=node_key("job_type", int(root.id)),
                kind="job_type",
                ref_id=int(root.id),
                label=root.name,
                href=job_type_href(int(root.id)),
                detail="root",
            )
        )

        frontier = [int(root.id)]
        visited: set[int] = {int(root.id)}
        for _level in range(max_depth):
            rows = await self._nest_link_rows(tenant_id=tenant_id, source_job_type_ids=frontier)
            if not rows:
                frontier = []
                break
            names = await self._live_job_type_names(
                tenant_id=tenant_id,
                job_type_ids=[row["target_job_type_id"] for row in rows],
            )
            next_frontier: list[int] = []
            for row in rows:
                target = row["target_job_type_id"]
                live = target in names
                target_key = builder.add_node(
                    JobGraphNode(
                        key=node_key("job_type", target),
                        kind="job_type",
                        ref_id=target,
                        label=names.get(target) or row["label"] or f"Job cycle #{target}",
                        href=job_type_href(target),
                        # A soft-deleted target still has a link in a cell, so
                        # dropping the edge would hide something the operator
                        # can see. Say it is gone instead.
                        detail=None if live else "unavailable",
                    )
                )
                source_key = node_key("job_type", row["source_job_type_id"])
                builder.add_edge(
                    JobGraphEdge(
                        key=edge_key("nests", source_key, target_key, via=row["cell_id"]),
                        kind="nests",
                        source=source_key,
                        target=target_key,
                        label=row["label"],
                        href=job_type_href(target),
                        cell_id=row["cell_id"],
                        lane_id=row["lane_id"],
                        step_id=row["step_id"],
                    )
                )
                if live and target not in visited:
                    visited.add(target)
                    next_frontier.append(target)
            frontier = next_frontier
            if not frontier:
                break

        # Only ask about the boundary when the walk actually stopped at it.
        truncated = bool(frontier) and bool(
            await self._nest_link_rows(tenant_id=tenant_id, source_job_type_ids=frontier)
        )
        return {
            "root_job_type_id": int(root.id),
            "depth": max_depth,
            "truncated": truncated,
            **builder.as_dict(),
        }

    async def audit_trail(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        limit: Optional[int] = None,
        assure: bool = False,
        include_links: bool = False,
    ) -> dict[str, Any]:
        """Sample path walk an auditor can follow: pack → cell → evidence.

        Shares the map's node/edge vocabulary, so a ``nests`` edge means the
        same thing in both and the two views can be drawn by one renderer. The
        walk is a *sample*: mandatory cells first, then cells that hold
        something, capped — and the response says how many candidates existed
        so a truncated walk never reads as a complete one.
        """
        root = await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        max_paths = clamp_audit_trail_limit(limit)

        cells = await self._cells_with_axis_context(tenant_id=tenant_id, job_type_id=job_type_id)
        cell_ids = [c["cell_id"] for c in cells]
        docs_by_cell = await self._documents_by_cell(tenant_id=tenant_id, cell_ids=cell_ids)
        # Link edges follow the same gate as the composer's cells: with
        # ``job_cell_links`` closed the trail must not surface links the
        # composer itself is hiding.
        links_by_cell = await self._links_by_cell(tenant_id=tenant_id, cell_ids=cell_ids) if include_links else {}

        candidates = [
            {
                **cell,
                "has_content": bool(docs_by_cell.get(cell["cell_id"])) or bool(links_by_cell.get(cell["cell_id"])),
            }
            for cell in cells
        ]
        selected, total_candidates = select_trail_cells(candidates, limit=max_paths)

        walked_doc_ids = [doc_id for cell in selected for doc_id in docs_by_cell.get(cell["cell_id"], [])]
        documents = await self._documents_by_id(tenant_id=tenant_id, document_ids=walked_doc_ids)
        freshness: dict[int, dict[str, Any]] = {}
        obsolete_ids: set[int] = set()
        unresolved_ids: set[int] = set()
        if assure and walked_doc_ids:
            freshness = await self._freshness_by_document_id(tenant_id=tenant_id, document_ids=walked_doc_ids)
            obsolete_ids, unresolved_ids = self._obsolete_and_unresolved(freshness)

        nested_names = await self._live_job_type_names(
            tenant_id=tenant_id,
            job_type_ids=[
                int(link.target_job_type_id)
                for cell in selected
                for link in links_by_cell.get(cell["cell_id"], [])
                if link.kind == "job_cycle" and link.target_job_type_id is not None
            ],
        )

        builder = JobGraphBuilder()
        root_key = builder.add_node(
            JobGraphNode(
                key=node_key("job_type", int(root.id)),
                kind="job_type",
                ref_id=int(root.id),
                label=root.name,
                href=job_type_href(int(root.id)),
                detail="root",
            )
        )

        paths: list[dict[str, Any]] = []
        verdicts: list[CellReadinessVerdict] = []
        for cell in selected:
            cell_id = cell["cell_id"]
            document_ids = docs_by_cell.get(cell_id, [])
            cell_key = builder.add_node(
                JobGraphNode(
                    key=node_key("cell", cell_id),
                    kind="cell",
                    ref_id=cell_id,
                    label=f"{cell['lane_name']} × {cell['step_name']}",
                    href=href_for("job_step", int(cell["step_id"])),
                    detail="requires evidence" if cell["requires_evidence"] else None,
                )
            )
            edge_keys = [
                builder.add_edge(
                    JobGraphEdge(
                        key=edge_key("contains", root_key, cell_key, via=cell_id),
                        kind="contains",
                        source=root_key,
                        target=cell_key,
                        label=f"{cell['lane_name']} × {cell['step_name']}",
                        href=href_for("job_step", int(cell["step_id"])),
                        cell_id=cell_id,
                        lane_id=cell["lane_id"],
                        step_id=cell["step_id"],
                    )
                )
            ]
            node_keys = [root_key, cell_key]

            for document_id in document_ids:
                doc = documents.get(document_id)
                verdict = freshness.get(document_id)
                doc_key = builder.add_node(
                    JobGraphNode(
                        key=node_key("document", document_id),
                        kind="document",
                        ref_id=document_id,
                        label=_document_label(doc, document_id),
                        href=href_for("document", document_id),
                        detail=str(verdict["state"]) if verdict else None,
                    )
                )
                node_keys.append(doc_key)
                edge_keys.append(
                    builder.add_edge(
                        JobGraphEdge(
                            key=edge_key("evidences", cell_key, doc_key, via=cell_id),
                            kind="evidences",
                            source=cell_key,
                            target=doc_key,
                            label=_document_label(doc, document_id),
                            href=href_for("document", document_id),
                            cell_id=cell_id,
                            lane_id=cell["lane_id"],
                            step_id=cell["step_id"],
                        )
                    )
                )

            for link in links_by_cell.get(cell_id, []):
                target_node = _trail_link_node(link, nested_names)
                if target_node is None:
                    continue
                target_key = builder.add_node(target_node)
                node_keys.append(target_key)
                edge_keys.append(
                    builder.add_edge(
                        JobGraphEdge(
                            key=edge_key(_trail_link_edge_kind(link), cell_key, target_key, via=cell_id),
                            kind=_trail_link_edge_kind(link),
                            source=cell_key,
                            target=target_key,
                            label=link.label,
                            href=target_node.href,
                            cell_id=cell_id,
                            lane_id=cell["lane_id"],
                            step_id=cell["step_id"],
                        )
                    )
                )

            readiness = classify_cell_readiness(
                requires_evidence=bool(cell["requires_evidence"]),
                document_ids=document_ids,
                obsolete_ids=obsolete_ids,
                unresolved_ids=unresolved_ids,
                assure=assure,
            )
            verdicts.append(readiness)
            paths.append(
                {
                    "cell_id": cell_id,
                    "lane_id": cell["lane_id"],
                    "lane_name": cell["lane_name"],
                    "step_id": cell["step_id"],
                    "step_name": cell["step_name"],
                    "requires_evidence": bool(cell["requires_evidence"]),
                    "library_document_ids": document_ids,
                    "node_keys": node_keys,
                    "edge_keys": edge_keys,
                    "readiness": readiness.as_dict(),
                }
            )

        return {
            "root_job_type_id": int(root.id),
            "assure": bool(assure),
            "limit": max_paths,
            "total_candidates": total_candidates,
            "truncated": total_candidates > len(selected),
            "paths": paths,
            "summary": summarise_readiness(verdicts),
            **builder.as_dict(),
        }

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

    # ------------------------------------------------------------------
    # Baselines (JL-UX-W5) — snapshots, never forks
    # ------------------------------------------------------------------

    async def capture_live_snapshot(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
    ) -> dict[str, Any]:
        """Build the current axes + nest-edge snapshot for a live pack."""
        job_type = await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        lanes = await self.list_lanes(tenant_id=tenant_id, job_type_id=job_type_id)
        steps = await self.list_steps(tenant_id=tenant_id, job_type_id=job_type_id)
        lane_by_id = {int(lane.id): lane for lane in lanes}
        step_by_id = {int(step.id): step for step in steps}

        cell_result = await self.db.execute(
            select(JobCell).where(
                JobCell.tenant_id == tenant_id,
                JobCell.job_type_id == job_type_id,
                JobCell.deleted_at.is_(None),
            )
        )
        cells = list(cell_result.scalars().all())
        cell_rows: list[dict[str, Any]] = []
        for cell in cells:
            lane = lane_by_id.get(int(cell.lane_id))
            step = step_by_id.get(int(cell.step_id))
            if lane is None or step is None:
                continue
            cell_rows.append(
                {
                    "lane_code": lane.code,
                    "step_code": step.code,
                    "requires_evidence": bool(cell.requires_evidence),
                }
            )

        nest_rows = await self._nest_link_rows(tenant_id=tenant_id, source_job_type_ids=[job_type_id])
        target_ids = [row["target_job_type_id"] for row in nest_rows]
        target_codes: dict[int, str] = {}
        if target_ids:
            code_result = await self.db.execute(
                select(JobType.id, JobType.code).where(
                    JobType.tenant_id == tenant_id,
                    JobType.id.in_(target_ids),
                    JobType.deleted_at.is_(None),
                )
            )
            target_codes = {int(row_id): code for row_id, code in code_result.all()}

        nest_edges: list[dict[str, Any]] = []
        for row in nest_rows:
            lane = lane_by_id.get(int(row["lane_id"]))
            step = step_by_id.get(int(row["step_id"]))
            target_code = target_codes.get(int(row["target_job_type_id"]))
            if lane is None or step is None or target_code is None:
                continue
            nest_edges.append(
                {
                    "lane_code": lane.code,
                    "step_code": step.code,
                    "target_job_type_code": target_code,
                    "label": row["label"],
                }
            )

        return build_snapshot(
            job_type={
                "code": job_type.code,
                "name": job_type.name,
                "description": job_type.description,
                "is_active": job_type.is_active,
                "sort_order": job_type.sort_order,
            },
            lanes=[
                {
                    "code": lane.code,
                    "name": lane.name,
                    "description": lane.description,
                    "sort_order": lane.sort_order,
                    "is_active": lane.is_active,
                }
                for lane in lanes
            ],
            steps=[
                {
                    "code": step.code,
                    "name": step.name,
                    "description": step.description,
                    "sort_order": step.sort_order,
                    "is_active": step.is_active,
                    "pdca_phase": step.pdca_phase,
                }
                for step in steps
            ],
            cells=cell_rows,
            nest_edges=nest_edges,
        )

    async def create_baseline(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        label: Optional[str] = None,
        note: Optional[str] = None,
        created_by_id: Optional[int] = None,
    ) -> JobTypeBaseline:
        """Freeze the live tip as an immutable snapshot artefact."""
        await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        snapshot = await self.capture_live_snapshot(tenant_id=tenant_id, job_type_id=job_type_id)
        row = JobTypeBaseline(
            tenant_id=tenant_id,
            job_type_id=job_type_id,
            label=(label.strip() if label else None) or None,
            note=(note.strip() if note else None) or None,
            created_by_id=created_by_id,
            snapshot=snapshot,
        )
        self.db.add(row)
        await self.db.commit()
        await self.db.refresh(row)
        return row

    async def list_baselines(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
    ) -> list[JobTypeBaseline]:
        await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        result = await self.db.execute(
            select(JobTypeBaseline)
            .where(
                JobTypeBaseline.tenant_id == tenant_id,
                JobTypeBaseline.job_type_id == job_type_id,
            )
            .order_by(JobTypeBaseline.created_at.desc(), JobTypeBaseline.id.desc())
        )
        return list(result.scalars().all())

    async def get_baseline(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        baseline_id: int,
    ) -> JobTypeBaseline:
        await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        result = await self.db.execute(
            select(JobTypeBaseline).where(
                JobTypeBaseline.tenant_id == tenant_id,
                JobTypeBaseline.job_type_id == job_type_id,
                JobTypeBaseline.id == baseline_id,
            )
        )
        row = result.scalars().first()
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Baseline not found")
        return row

    def serialize_baseline(
        self,
        row: JobTypeBaseline,
        *,
        include_snapshot: bool = True,
        viewing: bool = False,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": int(row.id),
            "tenant_id": int(row.tenant_id),
            "job_type_id": int(row.job_type_id),
            "label": row.label,
            "note": row.note,
            "created_by_id": int(row.created_by_id) if row.created_by_id is not None else None,
            "created_at": row.created_at,
            "updated_at": row.updated_at,
            "is_snapshot": True,
            "edit_targets_live": True,
        }
        if include_snapshot:
            payload["snapshot"] = dict(row.snapshot or {})
        if viewing:
            payload["viewing_baseline"] = True
            payload["banner"] = viewing_baseline_banner(baseline_id=int(row.id), label=row.label)
        return payload

    async def diff_baseline(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        baseline_id: int,
    ) -> dict[str, Any]:
        """Diff a stored snapshot against the live tip (live remains SoT)."""
        row = await self.get_baseline(tenant_id=tenant_id, job_type_id=job_type_id, baseline_id=baseline_id)
        live = await self.capture_live_snapshot(tenant_id=tenant_id, job_type_id=job_type_id)
        diff = diff_snapshots(row.snapshot or {}, live)
        return {
            "baseline_id": int(row.id),
            "job_type_id": int(job_type_id),
            "viewing_baseline": True,
            "edit_targets_live": True,
            "banner": viewing_baseline_banner(baseline_id=int(row.id), label=row.label),
            "baseline_created_at": row.created_at,
            "baseline_label": row.label,
            **diff,
        }

    # ------------------------------------------------------------------
    # Portal nested-cycle read (JL-UX-W5) — job:read only surface
    # ------------------------------------------------------------------

    async def portal_nested_cycle(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        include_links: bool = True,
        include_cycle_graph: bool = True,
        depth: Optional[int] = None,
    ) -> dict[str, Any]:
        """Nest-aware read DTO for field/portal. No write affordances."""
        job_type = await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        lanes = await self.list_lanes(tenant_id=tenant_id, job_type_id=job_type_id)
        steps = await self.list_steps(tenant_id=tenant_id, job_type_id=job_type_id)
        cells = await self.list_cells(
            tenant_id=tenant_id,
            job_type_id=job_type_id,
            include_links=include_links,
        )
        # Portal only needs nest links + document refs — strip author-side kinds
        # that would tempt a field client into offering write chrome.
        portal_cells: list[dict[str, Any]] = []
        for cell in cells:
            nest_links = [link for link in (cell.get("links") or []) if link.get("kind") == "job_cycle"]
            portal_cells.append(
                {
                    "id": cell["id"],
                    "lane_id": cell["lane_id"],
                    "step_id": cell["step_id"],
                    "requires_evidence": bool(cell.get("requires_evidence", False)),
                    "library_document_ids": list(cell.get("library_document_ids") or []),
                    "nest_links": nest_links,
                }
            )

        graph: Optional[dict[str, Any]] = None
        if include_cycle_graph and include_links:
            graph = await self.cycle_graph(
                tenant_id=tenant_id,
                job_type_id=job_type_id,
                depth=depth,
            )

        return {
            "job_type": job_type,
            "lanes": lanes,
            "steps": steps,
            "cells": portal_cells,
            "cycle_graph": graph,
            "read_only": True,
            "can_author": False,
        }


__all__ = [
    "MAX_FRESHNESS_DOCUMENT_IDS",
    "JobLifecycleService",
    "list_link_entity_types",
    "resolve_cell_link_href",
    "serialize_cell_link",
]
