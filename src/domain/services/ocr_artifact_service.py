"""OCR artifact persistence and human override stubs (R5 — no provider dial)."""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.ocr_artifact import OCRArtifact, OCRArtifactOverrideStatus, OCRArtifactTier
from src.domain.services.ocr_consensus import (
    OCRPageConsensus,
    OCRPageSource,
    build_page_consensus,
    hash_ocr_text,
    normalize_ocr_text,
)

logger = logging.getLogger(__name__)

DEFAULT_PIPELINE_VERSION = "2026.07.r5"


def artifact_confidence(*, tier: OCRArtifactTier, agreement: float, candidate_count: int) -> float:
    """Derive a 0–1 confidence score from consensus agreement and tier."""
    if tier == OCRArtifactTier.CANONICAL:
        return round(agreement, 4)
    if candidate_count <= 1:
        return 0.5
    return round(max(0.0, agreement - (1.0 / candidate_count)), 4)


class OCRArtifactService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_artifact(self, artifact_id: int) -> Optional[OCRArtifact]:
        result = await self.db.execute(select(OCRArtifact).where(OCRArtifact.id == artifact_id))
        return result.scalar_one_or_none()

    async def persist_page_consensus(
        self,
        candidates: Sequence[OCRPageSource],
        *,
        job_ref: str | None = None,
        draft_ref: str | None = None,
        tenant_id: int | None = None,
        pipeline_version: str = DEFAULT_PIPELINE_VERSION,
        reference_text: str | None = None,
    ) -> tuple[OCRPageConsensus, list[OCRArtifact]]:
        """Build page consensus and persist canonical + advisory artifact rows."""
        consensus = build_page_consensus(candidates, reference_text=reference_text)
        artifacts = await self._persist_consensus_artifacts(
            consensus,
            candidates,
            job_ref=job_ref,
            draft_ref=draft_ref,
            tenant_id=tenant_id,
            pipeline_version=pipeline_version,
        )
        return consensus, artifacts

    async def _persist_consensus_artifacts(
        self,
        consensus: OCRPageConsensus,
        candidates: Sequence[OCRPageSource],
        *,
        job_ref: str | None,
        draft_ref: str | None,
        tenant_id: int | None,
        pipeline_version: str,
    ) -> list[OCRArtifact]:
        saved: list[OCRArtifact] = []
        candidate_count = len(candidates)

        for candidate in candidates:
            tier = (
                OCRArtifactTier.CANONICAL
                if candidate.provider == consensus.selected_provider
                and normalize_ocr_text(candidate.text) == normalize_ocr_text(consensus.selected_text)
                else OCRArtifactTier.ADVISORY
            )
            artifact = OCRArtifact(
                tenant_id=tenant_id,
                provider=candidate.provider,
                page_number=candidate.page_number,
                content_hash=hash_ocr_text(candidate.text),
                confidence=artifact_confidence(
                    tier=tier,
                    agreement=consensus.agreement,
                    candidate_count=candidate_count,
                ),
                pipeline_version=pipeline_version,
                job_ref=job_ref,
                draft_ref=draft_ref,
                tier=tier,
            )
            self.db.add(artifact)
            saved.append(artifact)

        await self.db.flush()
        logger.info(
            "ocr_page_consensus_persisted",
            extra={
                "page_number": consensus.page_number,
                "selected_provider": consensus.selected_provider,
                "artifact_count": len(saved),
                "job_ref": job_ref,
                "draft_ref": draft_ref,
            },
        )
        return saved

    async def record_dispute(
        self,
        *,
        artifact_id: int,
        note: str,
        actor: str,
    ) -> Optional[OCRArtifact]:
        """Record human dispute override — never dials OCR providers."""
        artifact = await self.get_artifact(artifact_id)
        if artifact is None:
            return None
        artifact.override_status = OCRArtifactOverrideStatus.DISPUTED
        artifact.override_note = note
        artifact.overridden_by = actor
        artifact.overridden_at = datetime.now(timezone.utc)
        await self.db.flush()
        logger.info(
            "ocr_artifact_disputed",
            extra={"artifact_id": artifact_id, "provider": artifact.provider, "actor": actor},
        )
        return artifact

    async def record_ack(
        self,
        *,
        artifact_id: int,
        note: str | None,
        actor: str,
    ) -> Optional[OCRArtifact]:
        """Record human acknowledgement — never dials OCR providers."""
        artifact = await self.get_artifact(artifact_id)
        if artifact is None:
            return None
        artifact.override_status = OCRArtifactOverrideStatus.ACKNOWLEDGED
        artifact.override_note = note
        artifact.overridden_by = actor
        artifact.overridden_at = datetime.now(timezone.utc)
        await self.db.flush()
        logger.info(
            "ocr_artifact_acknowledged",
            extra={"artifact_id": artifact_id, "provider": artifact.provider, "actor": actor},
        )
        return artifact


async def persist_page_consensus_hook(
    db: AsyncSession,
    consensus: OCRPageConsensus,
    candidates: Sequence[OCRPageSource],
    *,
    job_ref: str | None = None,
    draft_ref: str | None = None,
    tenant_id: int | None = None,
    pipeline_version: str = DEFAULT_PIPELINE_VERSION,
) -> list[OCRArtifact]:
    """Hook invoked from ``build_page_consensus`` when persistence is requested."""
    service = OCRArtifactService(db)
    return await service._persist_consensus_artifacts(
        consensus,
        candidates,
        job_ref=job_ref,
        draft_ref=draft_ref,
        tenant_id=tenant_id,
        pipeline_version=pipeline_version,
    )


__all__ = [
    "DEFAULT_PIPELINE_VERSION",
    "OCRArtifactService",
    "artifact_confidence",
    "persist_page_consensus_hook",
]
