"""OCR provider ops meta endpoints (Path-to-10 W4/R5 — configuration honesty only).

Reports whether Mistral, Gemini, and Azure DI environment variables are present.
R5 adds OCR artifact dispute/ack stubs and capability flags.
Never returns secrets or dials live OCR providers.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, status

from src.api.dependencies import CurrentUser, DbSession
from src.api.schemas.ocr_artifact import (
    OCRArtifactAckRequest,
    OCRArtifactDisputeRequest,
    OCRArtifactOverrideResponse,
    OCRArtifactResponse,
)
from src.domain.services.ocr_artifact_service import OCRArtifactService
from src.infrastructure.upstream.ai_status import get_ocr_ops_capabilities, get_ocr_providers_readiness

router = APIRouter(tags=["Meta"])


@router.get("/ocr-providers", response_model=dict[str, Any])
async def get_ocr_providers_meta() -> dict[str, Any]:
    """Return OCR provider configuration flags and capability notes (no secrets)."""
    payload = get_ocr_providers_readiness()
    payload["as_of"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload["endpoint"] = "/api/v1/meta/ocr-providers"
    payload["canonical_endpoint"] = "/api/v1/meta/ocr-providers"
    payload["legacy_endpoint"] = "/api/v1/health/meta/ocr-providers"
    if not payload.get("note"):
        payload["note"] = "Configuration-only meta; live OCR calls occur on import/analysis paths only."
    return payload


@router.get("/ocr-capabilities", response_model=dict[str, Any])
async def get_ocr_capabilities_meta() -> dict[str, Any]:
    """Return R5 OCR ops capability flags (artifacts, consensus persist, dispute stubs)."""
    payload = get_ocr_ops_capabilities()
    payload["as_of"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    payload["endpoint"] = "/api/v1/meta/ocr-capabilities"
    payload["legacy_endpoint"] = "/api/v1/health/meta/ocr-capabilities"
    return payload


@router.post("/ocr-artifacts/dispute", response_model=OCRArtifactOverrideResponse)
async def dispute_ocr_artifact(
    body: OCRArtifactDisputeRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> OCRArtifactOverrideResponse:
    """Record human dispute on an OCR artifact — stub only, never dials providers.

    Auth required: previously public POST allowed unauthenticated writes.
    """
    actor = current_user.email or body.actor or f"user:{current_user.id}"
    service = OCRArtifactService(db)
    artifact = await service.record_dispute(
        artifact_id=body.artifact_id,
        note=body.note,
        actor=actor,
    )
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OCR artifact not found")
    await db.commit()
    return OCRArtifactOverrideResponse(
        artifact=OCRArtifactResponse.model_validate(artifact),
        message="Human dispute recorded; OCR providers were not contacted.",
    )


@router.post("/ocr-artifacts/ack", response_model=OCRArtifactOverrideResponse)
async def acknowledge_ocr_artifact(
    body: OCRArtifactAckRequest,
    db: DbSession,
    current_user: CurrentUser,
) -> OCRArtifactOverrideResponse:
    """Record human acknowledgement on an OCR artifact — stub only, never dials providers.

    Auth required: previously public POST allowed unauthenticated writes.
    """
    actor = current_user.email or body.actor or f"user:{current_user.id}"
    service = OCRArtifactService(db)
    artifact = await service.record_ack(
        artifact_id=body.artifact_id,
        note=body.note,
        actor=actor,
    )
    if artifact is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OCR artifact not found")
    await db.commit()
    return OCRArtifactOverrideResponse(
        artifact=OCRArtifactResponse.model_validate(artifact),
        message="Human acknowledgement recorded; OCR providers were not contacted.",
    )
