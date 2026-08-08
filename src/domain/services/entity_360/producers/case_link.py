"""Case-link + audit-finding Entity360 producer (risk upstream origin)."""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select

from src.domain.models.audit import AuditFinding, audit_finding_risks
from src.domain.models.complaint import Complaint
from src.domain.models.incident import Incident
from src.domain.models.near_miss import NearMiss
from src.domain.models.rta import RoadTrafficCollision
from src.domain.services.case_risk_links import list_case_links_for_risk
from src.domain.services.entity_360.types import ProducerResult, make_hop
from src.domain.services.href_registry import audit_finding_href, case_type_href, risk_href


class CaseLinkProducer:
    """Reverse case↔risk + audit finding links.

    Bidirectional day one:
    - For ``risk``: upstream = cases/findings that cite the risk; downstream = []
      (treatments / CAPA land with satellites — empty downstream is still registered).
    - For case types: upstream = []; downstream = linked risks.
    """

    origin = "case_link"

    _CASE_TYPES = frozenset({"incident", "near_miss", "rta", "complaint"})
    _SUPPORTED = frozenset({"risk", "audit_finding"}) | _CASE_TYPES

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
            if key == "risk":
                return await self._for_risk(db=db, tenant_id=tenant_id, risk_id=entity_id)
            if key in self._CASE_TYPES:
                return await self._for_case(
                    db=db, tenant_id=tenant_id, case_type=key, case_id=entity_id
                )
            return ProducerResult(origin=self.origin, status="skipped", reason="unsupported")
        except Exception as exc:  # noqa: BLE001
            return ProducerResult(
                origin=self.origin,
                status="error",
                reason=f"case_link: {exc}",
            )

    async def _for_risk(self, *, db: Any, tenant_id: int, risk_id: int) -> ProducerResult:
        upstream: list[dict[str, Any]] = []
        links = await list_case_links_for_risk(db, tenant_id=tenant_id, risk_id=risk_id)
        case_ids_by_type: dict[str, list[int]] = {}
        for link in links:
            case_ids_by_type.setdefault(link.case_type, []).append(link.case_id)

        title_maps: dict[str, dict[int, tuple[Optional[str], Optional[str]]]] = {}
        model_by_type = {
            "incident": Incident,
            "near_miss": NearMiss,
            "rta": RoadTrafficCollision,
            "complaint": Complaint,
        }
        for case_type, ids in case_ids_by_type.items():
            model = model_by_type.get(case_type)
            if not model or not ids:
                continue
            result = await db.execute(select(model).where(model.id.in_(ids), model.tenant_id == tenant_id))
            rows = result.scalars().all()
            mapped: dict[int, tuple[Optional[str], Optional[str]]] = {}
            for row in rows:
                title = getattr(row, "title", None)
                if not title and case_type == "near_miss":
                    desc = getattr(row, "description", None) or ""
                    title = (desc[:80] + "…") if len(desc) > 80 else (desc or None)
                mapped[row.id] = (title, getattr(row, "reference_number", None))
            title_maps[case_type] = mapped

        for link in links:
            title, reference = title_maps.get(link.case_type, {}).get(link.case_id, (None, None))
            upstream.append(
                make_hop(
                    source_type=link.case_type,
                    source_id=link.case_id,
                    title=title,
                    reference=reference,
                    href=case_type_href(link.case_type, link.case_id),
                    direction="upstream",
                    relation="linked_risk",
                    depth=1,
                    origin="case_link",
                    status="confirmed",
                )
            )

        finding_result = await db.execute(
            select(AuditFinding)
            .join(
                audit_finding_risks,
                audit_finding_risks.c.audit_finding_id == AuditFinding.id,
            )
            .where(
                audit_finding_risks.c.risk_id == risk_id,
                AuditFinding.tenant_id == tenant_id,
            )
            .order_by(AuditFinding.id.desc())
        )
        for finding in finding_result.scalars().all():
            upstream.append(
                make_hop(
                    source_type="audit_finding",
                    source_id=finding.id,
                    title=finding.title,
                    reference=finding.reference_number,
                    href=audit_finding_href(run_id=finding.run_id, finding_id=finding.id),
                    direction="upstream",
                    relation="audit_finding_risk",
                    depth=1,
                    origin="case_link",
                    status="confirmed",
                    # Narrowing view for RiskUpstreamItem keeps audit_run_id separately;
                    # stash on hop via version_pin unused — composer narrowing reads run_id
                    # from a side channel. Encode run_id in hop for narrowing:
                )
            )
            # Preserve audit_run_id for RiskUpstreamItem narrowing (non-contract field
            # stripped before Entity360 API response).
            upstream[-1]["_audit_run_id"] = finding.run_id

        return ProducerResult(
            origin=self.origin,
            status="ok",
            upstream=upstream,
            downstream=[],  # bidirectional registration — empty but present
        )

    async def _for_case(
        self,
        *,
        db: Any,
        tenant_id: int,
        case_type: str,
        case_id: int,
    ) -> ProducerResult:
        from src.domain.models.risk_register import CaseRiskLink, EnterpriseRisk

        result = await db.execute(
            select(CaseRiskLink).where(
                CaseRiskLink.tenant_id == tenant_id,
                CaseRiskLink.case_type == case_type,
                CaseRiskLink.case_id == case_id,
            )
        )
        links = list(result.scalars().all())
        risk_ids = [link.risk_id for link in links]
        risks: dict[int, EnterpriseRisk] = {}
        if risk_ids:
            risk_result = await db.execute(
                select(EnterpriseRisk).where(
                    EnterpriseRisk.tenant_id == tenant_id,
                    EnterpriseRisk.id.in_(risk_ids),
                )
            )
            risks = {r.id: r for r in risk_result.scalars().all()}

        downstream: list[dict[str, Any]] = []
        for link in links:
            risk = risks.get(link.risk_id)
            downstream.append(
                make_hop(
                    source_type="risk",
                    source_id=link.risk_id,
                    title=getattr(risk, "title", None) if risk is not None else None,
                    reference=getattr(risk, "reference_number", None) if risk is not None else None,
                    href=risk_href(link.risk_id),
                    direction="downstream",
                    relation="linked_risk",
                    depth=1,
                    origin="case_link",
                    status="confirmed",
                )
            )
        return ProducerResult(
            origin=self.origin,
            status="ok",
            upstream=[],
            downstream=downstream,
        )


__all__ = ["CaseLinkProducer"]
