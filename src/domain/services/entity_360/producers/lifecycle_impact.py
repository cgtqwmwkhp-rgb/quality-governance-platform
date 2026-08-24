"""Lifecycle / campaign impact producer for document publish ImpactBundle."""

from __future__ import annotations

from typing import Any

from sqlalchemy import select

from src.domain.services.entity_360.types import ProducerResult, make_hop
from src.domain.services.href_registry import href_for


class LifecycleImpactProducer:
    """Reading-campaign / lifecycle signals for library documents.

    Emits downstream hops for active campaigns. Failures mark ``error`` so
    ImpactBundle ``complete=false`` and publish is blocked.
    """

    origin = "lifecycle"

    def supports(self, entity_type: str) -> bool:
        return entity_type.strip().lower() == "document"

    async def produce(
        self,
        *,
        db: Any,
        tenant_id: int,
        entity_type: str,
        entity_id: int,
        user: Any,
    ) -> ProducerResult:
        _ = (entity_type, user)
        try:
            from src.domain.models.document_campaign import DocumentCampaign

            result = await db.execute(
                select(DocumentCampaign).where(
                    DocumentCampaign.tenant_id == tenant_id,
                    DocumentCampaign.document_id == entity_id,
                )
            )
            campaigns = list(result.scalars().all())
        except Exception as exc:  # noqa: BLE001 — missing model / query failure
            # If campaigns table is unavailable, degrade honestly rather than skip
            # silently — publish must not proceed on incomplete impact.
            return ProducerResult(
                origin=self.origin,
                status="error",
                reason=f"lifecycle campaigns: {exc}",
            )

        downstream: list[dict[str, Any]] = []
        # document_campaigns: draft | active | closed — treat non-closed as impactful
        active_statuses = {"active", "draft"}
        for camp in campaigns:
            raw_status = getattr(camp, "status", "")
            status = raw_status.value if hasattr(raw_status, "value") else str(raw_status or "")
            status = status.lower()
            if status not in active_statuses:
                continue
            camp_id = int(camp.id)
            title = getattr(camp, "title", None) or f"Campaign #{camp_id}"
            downstream.append(
                make_hop(
                    source_type="document",  # campaign surfaces via document campaigns UI
                    source_id=camp_id,
                    title=title,
                    reference=None,
                    href=href_for("document", entity_id),  # document page hosts campaign UX
                    direction="downstream",
                    relation="reading_campaign",
                    depth=1,
                    origin="lifecycle",
                    status=status,
                )
            )

        return ProducerResult(
            origin=self.origin,
            status="ok",
            upstream=[],
            downstream=downstream,
        )


__all__ = ["LifecycleImpactProducer"]
