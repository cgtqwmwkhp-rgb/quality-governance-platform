"""Case-link + CAPA Entity360 producer (risk / case / finding / capa).

X-1: reverse case↔risk + audit finding→risk upstream.
X-3: CAPA source_type/source_id bi-links + audit_finding subject (flag-gated
by ``entity_360_satellites``). Treatments land as risk downstream CAPAs.
"""

from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select

from src.core.config import settings
from src.domain.models.audit import AuditFinding, audit_finding_risks
from src.domain.models.capa import CAPAAction, CAPASource
from src.domain.models.complaint import Complaint
from src.domain.models.incident import Incident
from src.domain.models.near_miss import NearMiss
from src.domain.models.rta import RoadTrafficCollision
from src.domain.services.case_risk_links import list_case_links_for_risk
from src.domain.services.entity_360.types import ProducerResult, make_hop
from src.domain.services.href_registry import audit_finding_href, case_type_href, href_for, risk_href

# CAPA source types that map to int-keyed Entity360 subjects with href builders.
_CAPA_SOURCE_TO_ENTITY = {
    CAPASource.INCIDENT: "incident",
    CAPASource.NEAR_MISS: "near_miss",
    CAPASource.RTA: "rta",
    CAPASource.COMPLAINT: "complaint",
    CAPASource.RISK: "risk",
    CAPASource.AUDIT_FINDING: "audit_finding",
}

_CASE_TO_CAPA_SOURCE = {
    "incident": CAPASource.INCIDENT,
    "near_miss": CAPASource.NEAR_MISS,
    "rta": CAPASource.RTA,
    "complaint": CAPASource.COMPLAINT,
}


class CaseLinkProducer:
    """Reverse case↔risk + audit finding links + satellite CAPA bi-links.

    Bidirectional day one:
    - For ``risk``: upstream = cases/findings that cite the risk;
      downstream = CAPAs sourced from the risk when satellites flag is on.
    - For case types: upstream = []; downstream = linked risks (+ CAPAs when on).
    - For ``audit_finding`` (satellites on): upstream = [];
      downstream = linked risks + CAPAs.
    - For ``capa`` (satellites on): upstream = source entity; downstream = [].
    """

    origin = "case_link"

    _CASE_TYPES = frozenset({"incident", "near_miss", "rta", "complaint"})
    _SUPPORTED = frozenset({"risk", "audit_finding", "capa"}) | _CASE_TYPES

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
                return await self._for_case(db=db, tenant_id=tenant_id, case_type=key, case_id=entity_id)
            if key == "audit_finding":
                if not settings.entity_360_satellites_enabled:
                    # Identical to pre-X-3 fall-through (supports claimed finding but skipped).
                    return ProducerResult(origin=self.origin, status="skipped", reason="unsupported")
                return await self._for_audit_finding(db=db, tenant_id=tenant_id, finding_id=entity_id)
            if key == "capa":
                if not settings.entity_360_satellites_enabled:
                    return ProducerResult(
                        origin=self.origin,
                        status="skipped",
                        reason="entity_360_satellites disabled",
                    )
                return await self._for_capa(db=db, tenant_id=tenant_id, capa_id=entity_id)
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
            result = await db.execute(
                select(model).where(
                    model.__table__.c.id.in_(ids),
                    model.__table__.c.tenant_id == tenant_id,
                )
            )
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
                )
            )
            # Preserve audit_run_id for RiskUpstreamItem narrowing (non-contract field
            # stripped before Entity360 API response).
            upstream[-1]["_audit_run_id"] = finding.run_id

        downstream: list[dict[str, Any]] = []
        if settings.entity_360_satellites_enabled:
            downstream = await self._capa_hops_for_source(
                db=db,
                tenant_id=tenant_id,
                source=CAPASource.RISK,
                source_id=risk_id,
                relation="risk_treatment",
            )

        return ProducerResult(
            origin=self.origin,
            status="ok",
            upstream=upstream,
            downstream=downstream,
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
                    reference=getattr(risk, "reference", None) if risk is not None else None,
                    href=risk_href(link.risk_id),
                    direction="downstream",
                    relation="linked_risk",
                    depth=1,
                    origin="case_link",
                    status="confirmed",
                )
            )

        if settings.entity_360_satellites_enabled:
            capa_source = _CASE_TO_CAPA_SOURCE.get(case_type)
            if capa_source is not None:
                downstream.extend(
                    await self._capa_hops_for_source(
                        db=db,
                        tenant_id=tenant_id,
                        source=capa_source,
                        source_id=case_id,
                        relation="capa_source",
                    )
                )

        return ProducerResult(
            origin=self.origin,
            status="ok",
            upstream=[],
            downstream=downstream,
        )

    async def _for_audit_finding(self, *, db: Any, tenant_id: int, finding_id: int) -> ProducerResult:
        from src.domain.models.risk_register import EnterpriseRisk

        result = await db.execute(
            select(EnterpriseRisk)
            .join(
                audit_finding_risks,
                audit_finding_risks.c.risk_id == EnterpriseRisk.id,
            )
            .where(
                audit_finding_risks.c.audit_finding_id == finding_id,
                EnterpriseRisk.tenant_id == tenant_id,
            )
            .order_by(EnterpriseRisk.id.desc())
        )
        downstream: list[dict[str, Any]] = []
        for risk in result.scalars().all():
            downstream.append(
                make_hop(
                    source_type="risk",
                    source_id=risk.id,
                    title=getattr(risk, "title", None),
                    reference=getattr(risk, "reference", None),
                    href=risk_href(risk.id),
                    direction="downstream",
                    relation="audit_finding_risk",
                    depth=1,
                    origin="case_link",
                    status="confirmed",
                )
            )

        downstream.extend(
            await self._capa_hops_for_source(
                db=db,
                tenant_id=tenant_id,
                source=CAPASource.AUDIT_FINDING,
                source_id=finding_id,
                relation="capa_source",
            )
        )

        return ProducerResult(
            origin=self.origin,
            status="ok",
            upstream=[],
            downstream=downstream,
        )

    async def _for_capa(self, *, db: Any, tenant_id: int, capa_id: int) -> ProducerResult:
        result = await db.execute(
            select(CAPAAction).where(
                CAPAAction.tenant_id == tenant_id,
                CAPAAction.id == capa_id,
            )
        )
        capa = result.scalar_one_or_none()
        if capa is None:
            return ProducerResult(origin=self.origin, status="ok", upstream=[], downstream=[])

        upstream: list[dict[str, Any]] = []
        source = capa.source_type
        source_id = capa.source_id
        if source is not None and source_id is not None:
            source_enum = source if isinstance(source, CAPASource) else CAPASource(str(source))
            entity_type = _CAPA_SOURCE_TO_ENTITY.get(source_enum)
            if entity_type is not None:
                hop = await self._source_hop(
                    db=db,
                    tenant_id=tenant_id,
                    entity_type=entity_type,
                    entity_id=int(source_id),
                )
                if hop is not None:
                    upstream.append(hop)

        return ProducerResult(
            origin=self.origin,
            status="ok",
            upstream=upstream,
            downstream=[],
        )

    async def _capa_hops_for_source(
        self,
        *,
        db: Any,
        tenant_id: int,
        source: CAPASource,
        source_id: int,
        relation: str,
    ) -> list[dict[str, Any]]:
        result = await db.execute(
            select(CAPAAction)
            .where(
                CAPAAction.tenant_id == tenant_id,
                CAPAAction.source_type == source,
                CAPAAction.source_id == source_id,
            )
            .order_by(CAPAAction.id.desc())
        )
        hops: list[dict[str, Any]] = []
        for capa in result.scalars().all():
            hops.append(
                make_hop(
                    source_type="capa",
                    source_id=int(capa.id),
                    title=capa.title,
                    reference=capa.reference_number,
                    href=href_for("capa", int(capa.id)),
                    direction="downstream",
                    relation=relation,
                    depth=1,
                    origin="case_link",
                    status=capa.status.value if hasattr(capa.status, "value") else str(capa.status),
                )
            )
        return hops

    async def _source_hop(
        self,
        *,
        db: Any,
        tenant_id: int,
        entity_type: str,
        entity_id: int,
    ) -> Optional[dict[str, Any]]:
        if entity_type == "risk":
            from src.domain.models.risk_register import EnterpriseRisk

            result = await db.execute(
                select(EnterpriseRisk).where(
                    EnterpriseRisk.tenant_id == tenant_id,
                    EnterpriseRisk.id == entity_id,
                )
            )
            risk = result.scalar_one_or_none()
            return make_hop(
                source_type="risk",
                source_id=entity_id,
                title=getattr(risk, "title", None) if risk is not None else None,
                reference=getattr(risk, "reference", None) if risk is not None else None,
                href=risk_href(entity_id),
                direction="upstream",
                relation="risk_treatment",
                depth=1,
                origin="case_link",
                status="confirmed",
            )

        if entity_type == "audit_finding":
            result = await db.execute(
                select(AuditFinding).where(
                    AuditFinding.tenant_id == tenant_id,
                    AuditFinding.id == entity_id,
                )
            )
            finding = result.scalar_one_or_none()
            if finding is None:
                return make_hop(
                    source_type="audit_finding",
                    source_id=entity_id,
                    title=None,
                    reference=None,
                    href=href_for("audit_finding", entity_id),
                    direction="upstream",
                    relation="capa_source",
                    depth=1,
                    origin="case_link",
                    status="confirmed",
                )
            return make_hop(
                source_type="audit_finding",
                source_id=entity_id,
                title=finding.title,
                reference=finding.reference_number,
                href=audit_finding_href(run_id=finding.run_id, finding_id=finding.id),
                direction="upstream",
                relation="capa_source",
                depth=1,
                origin="case_link",
                status="confirmed",
            )

        model_by_type = {
            "incident": Incident,
            "near_miss": NearMiss,
            "rta": RoadTrafficCollision,
            "complaint": Complaint,
        }
        model = model_by_type.get(entity_type)
        if model is None:
            return None
        result = await db.execute(
            select(model).where(
                model.__table__.c.id == entity_id,
                model.__table__.c.tenant_id == tenant_id,
            )
        )
        row = result.scalar_one_or_none()
        title = getattr(row, "title", None) if row is not None else None
        if not title and entity_type == "near_miss" and row is not None:
            desc = getattr(row, "description", None) or ""
            title = (desc[:80] + "…") if len(desc) > 80 else (desc or None)
        reference = getattr(row, "reference_number", None) if row is not None else None
        return make_hop(
            source_type=entity_type,
            source_id=entity_id,
            title=title,
            reference=reference,
            href=case_type_href(entity_type, entity_id),
            direction="upstream",
            relation="capa_source",
            depth=1,
            origin="case_link",
            status="confirmed",
        )


__all__ = ["CaseLinkProducer"]
