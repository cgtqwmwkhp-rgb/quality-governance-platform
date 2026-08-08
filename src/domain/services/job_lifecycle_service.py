"""Job Lifecycle axis service (JL-1 / JL-3 / ADR-0022).

Editable Job Type / Lane / Step vocabulary, cell document membership, and
cell hyperlinks (app · external · audit_outcome). Axis identity is JL
``code`` — never LookupOption or free-text department. Link hrefs resolve
via ``href_registry`` only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Sequence
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.audit import AuditFinding
from src.domain.models.document import Document
from src.domain.models.job_lifecycle import (
    JOB_STEP_PDCA_PHASES,
    JobCell,
    JobCellDocument,
    JobCellLink,
    JobLane,
    JobStep,
    JobType,
)
from src.domain.services.href_registry import (
    audit_finding_href,
    href_for,
    job_type_href,
    registered_entity_types,
)


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


def serialize_cell_link(link: JobCellLink) -> dict[str, Any]:
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
        "sort_order": link.sort_order,
        "created_at": link.created_at,
        "updated_at": link.updated_at,
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

        # Dedupe preserving order
        seen: set[int] = set()
        ordered_ids: list[int] = []
        for doc_id in library_document_ids:
            if doc_id in seen:
                continue
            seen.add(doc_id)
            ordered_ids.append(int(doc_id))

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
            links = [serialize_cell_link(row) for row in link_result.scalars().all()]
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
        return [await self._cell_payload(cell, include_links=include_links) for cell in cells]

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
        return [serialize_cell_link(row) for row in result.scalars().all()]

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
        return serialize_cell_link(row)

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

    async def _require_cell(
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
            for nested_id in await self.nested_job_type_ids(
                tenant_id=tenant_id, job_type_id=current
            ):
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
    "JobLifecycleService",
    "list_link_entity_types",
    "resolve_cell_link_href",
    "serialize_cell_link",
]
