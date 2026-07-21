"""Governance Library Wave W3 — review packs + horizons API."""

from __future__ import annotations

import logging
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Query

from src.api.dependencies import DbSession, require_permission
from src.api.schemas.library_review import (
    DashboardSummaryResponse,
    DependencyMapResponse,
    DispositionRequest,
    FindingResponse,
    HorizonScanResponse,
    HorizonsResponse,
    OpenPackRequest,
    PackListResponse,
    PackResponse,
)
from src.api.utils.tenant import require_tenant_id
from src.domain.models.user import User
from src.domain.services import library_review_service as review_service

router = APIRouter()
logger = logging.getLogger(__name__)


def _finding_response(finding) -> FindingResponse:
    return FindingResponse(
        id=finding.id,
        pack_id=finding.pack_id,
        provider=finding.provider,
        external_id=finding.external_id,
        title=finding.title,
        summary=finding.summary,
        source_url=finding.source_url,
        disposition=(finding.disposition.value if hasattr(finding.disposition, "value") else str(finding.disposition)),
        dispositioned_by_id=finding.dispositioned_by_id,
        dispositioned_at=finding.dispositioned_at,
        disposition_notes=finding.disposition_notes,
        created_at=getattr(finding, "created_at", None),
    )


def _pack_response(pack) -> PackResponse:
    findings = getattr(pack, "findings", None) or []
    return PackResponse(
        id=pack.id,
        tenant_id=pack.tenant_id,
        document_id=pack.document_id,
        status=pack.status.value if hasattr(pack.status, "value") else str(pack.status),
        window_days=pack.window_days,
        window_start=pack.window_start,
        window_end=pack.window_end,
        opened_at=pack.opened_at,
        opened_by_id=pack.opened_by_id,
        closed_at=pack.closed_at,
        closed_by_id=pack.closed_by_id,
        internal_inputs=pack.internal_inputs,
        findings=[_finding_response(f) for f in findings],
    )


@router.get("/dashboard-summary", response_model=DashboardSummaryResponse)
async def get_dashboard_summary(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:read"))],
) -> DashboardSummaryResponse:
    """Return statutory, overdue-review, and open-pack counts for Library / HSEQ tiles."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    data = await review_service.dashboard_summary(db, tenant_id=tenant_id)
    return DashboardSummaryResponse(**data)


@router.get("/dependencies/{pel_doc_ref}", response_model=DependencyMapResponse)
async def get_dependency_map(
    pel_doc_ref: str,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:read"))],
) -> DependencyMapResponse:
    """Return the current document tip plus its immutable superseded history."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    data = await review_service.dependency_map(db, tenant_id=tenant_id, pel_doc_ref=pel_doc_ref)
    return DependencyMapResponse(**data)


@router.get("/horizons", response_model=HorizonsResponse)
async def get_horizons(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:read"))],
    months: int = Query(3, description="Horizon months: 3, 6, or 12"),
) -> HorizonsResponse:
    """Bucket filed documents by review_date for the selected month horizon."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    data = await review_service.horizons(db, tenant_id=tenant_id, months=months)
    return HorizonsResponse(**data)


@router.get("/packs", response_model=PackListResponse)
async def list_packs(
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:read"))],
    status: Optional[str] = Query(None, description="Filter: open|closed"),
) -> PackListResponse:
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    packs = await review_service.list_packs(db, tenant_id=tenant_id, status=status)
    items = [_pack_response(p) for p in packs]
    return PackListResponse(items=items, total=len(items))


@router.post("/packs/open", response_model=PackResponse)
async def open_pack(
    body: OpenPackRequest,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
) -> PackResponse:
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    pack = await review_service.open_pack(
        db,
        tenant_id=tenant_id,
        document_id=body.document_id,
        opened_by_id=current_user.id,
    )
    return _pack_response(pack)


@router.get("/packs/{pack_id}", response_model=PackResponse)
async def get_pack(
    pack_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:read"))],
) -> PackResponse:
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    pack = await review_service.get_pack(db, tenant_id=tenant_id, pack_id=pack_id)
    return _pack_response(pack)


@router.post("/packs/{pack_id}/findings/{finding_id}/confirm", response_model=FindingResponse)
async def confirm_finding(
    pack_id: int,
    finding_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    body: Optional[DispositionRequest] = None,
) -> FindingResponse:
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    finding = await review_service.confirm_finding(
        db,
        tenant_id=tenant_id,
        pack_id=pack_id,
        finding_id=finding_id,
        user_id=current_user.id,
        notes=body.notes if body else None,
    )
    return _finding_response(finding)


@router.post("/packs/{pack_id}/findings/{finding_id}/reject", response_model=FindingResponse)
async def reject_finding(
    pack_id: int,
    finding_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
    body: Optional[DispositionRequest] = None,
) -> FindingResponse:
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    finding = await review_service.reject_finding(
        db,
        tenant_id=tenant_id,
        pack_id=pack_id,
        finding_id=finding_id,
        user_id=current_user.id,
        notes=body.notes if body else None,
    )
    return _finding_response(finding)


@router.post("/packs/{pack_id}/close", response_model=PackResponse)
async def close_pack(
    pack_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
) -> PackResponse:
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    pack = await review_service.close_pack(
        db,
        tenant_id=tenant_id,
        pack_id=pack_id,
        closed_by_id=current_user.id,
    )
    return _pack_response(pack)


@router.post("/packs/{pack_id}/horizon-scan", response_model=HorizonScanResponse)
async def horizon_scan(
    pack_id: int,
    db: DbSession,
    current_user: Annotated[User, Depends(require_permission("document:update"))],
) -> HorizonScanResponse:
    """Run the configured horizon provider (default stub) and persist findings."""
    tenant_id = require_tenant_id(getattr(current_user, "tenant_id", None))
    findings = await review_service.run_horizon_scan(db, tenant_id=tenant_id, pack_id=pack_id)
    return HorizonScanResponse(
        pack_id=pack_id,
        findings_created=len(findings),
        findings=[_finding_response(f) for f in findings],
    )
