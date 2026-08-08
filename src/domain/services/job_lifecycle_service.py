"""Job Lifecycle axis service (JL-1 / ADR-0022).

Editable Job Type / Lane / Step vocabulary and cell document membership.
Axis identity is JL ``code`` — never LookupOption or free-text department.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional, Sequence

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.document import Document
from src.domain.models.job_lifecycle import JobCell, JobCellDocument, JobLane, JobStep, JobType


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

    async def list_cells(self, *, tenant_id: int, job_type_id: int) -> list[dict[str, Any]]:
        await self.get_job_type(tenant_id=tenant_id, job_type_id=job_type_id)
        result = await self.db.execute(
            select(JobCell).where(
                JobCell.tenant_id == tenant_id,
                JobCell.job_type_id == job_type_id,
                JobCell.deleted_at.is_(None),
            )
        )
        cells = list(result.scalars().all())
        return [await self._cell_payload(cell) for cell in cells]

    async def set_cell_documents(
        self,
        *,
        tenant_id: int,
        job_type_id: int,
        lane_id: int,
        step_id: int,
        library_document_ids: Sequence[int],
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
        return await self._cell_payload(cell)

    async def _cell_payload(self, cell: JobCell) -> dict[str, Any]:
        result = await self.db.execute(
            select(JobCellDocument)
            .where(
                JobCellDocument.tenant_id == cell.tenant_id,
                JobCellDocument.cell_id == cell.id,
            )
            .order_by(JobCellDocument.sort_order, JobCellDocument.id)
        )
        docs = list(result.scalars().all())
        return {
            "id": cell.id,
            "tenant_id": cell.tenant_id,
            "job_type_id": cell.job_type_id,
            "lane_id": cell.lane_id,
            "step_id": cell.step_id,
            "library_document_ids": [d.library_document_id for d in docs],
            "created_at": cell.created_at,
            "updated_at": cell.updated_at,
        }

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


__all__ = ["JobLifecycleService"]
