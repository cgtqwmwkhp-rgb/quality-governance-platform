#!/usr/bin/env python3
"""Inventory helpers for human-ops backlog items (read-only).

Covers:
  PX-157  never-reviewed / unassessed risks
  PX-264  untriaged audit-import risks (unassigned)
  PX-246  Planet Mark YE2025 still Draft
  PX-273  open HSEQ policy-campaign questions
  PX-271  HS reporting hours anomaly (2024 vs later years)

These are inventory / evidence tools — they never mutate. Use the runbook to
drive human follow-up (assess, triage, certify, answer, correct hours).

Usage:
  python -m scripts.ops.run021.inventory_ops_backlog
  python -m scripts.ops.run021.inventory_ops_backlog --json --tenant-id 1
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any, Optional

from sqlalchemy import func, or_, select

from scripts.ops.run021._common import (
    add_safety_args,
    emit_report,
    enforce_apply_safety,
    open_session,
    truncate,
)


async def _collect(*, tenant_id: Optional[int], limit: int) -> dict[str, Any]:
    from src.domain.models.document import Document
    from src.domain.models.governed_knowledge import DiscussionThreadStatus, DocumentDiscussionThread
    from src.domain.models.hs_reporting_period import HsReportingPeriod
    from src.domain.models.planet_mark import CarbonReportingYear
    from src.domain.models.risk_register import EnterpriseRisk

    out: dict[str, Any] = {
        "PX-157": {"count": 0, "sample": []},
        "PX-264": {"count": 0, "sample": []},
        "PX-246": {"count": 0, "sample": []},
        "PX-273": {"count": 0, "sample": []},
        "PX-271": {"years": [], "anomaly": None},
    }

    async with await open_session() as db:
        # PX-157 — never reviewed (last_review_date IS NULL)
        q = select(
            EnterpriseRisk.id,
            EnterpriseRisk.title,
            EnterpriseRisk.reference,
            EnterpriseRisk.last_review_date,
            EnterpriseRisk.tenant_id,
        ).where(EnterpriseRisk.last_review_date.is_(None))
        if tenant_id is not None:
            q = q.where(EnterpriseRisk.tenant_id == tenant_id)
        rows = (await db.execute(q.limit(limit))).all()
        cq = select(func.count()).select_from(EnterpriseRisk).where(EnterpriseRisk.last_review_date.is_(None))
        if tenant_id is not None:
            cq = cq.where(EnterpriseRisk.tenant_id == tenant_id)
        out["PX-157"]["count"] = int((await db.execute(cq)).scalar() or 0)
        out["PX-157"]["sample"] = [
            {
                "px": "PX-157",
                "id": r.id,
                "title": r.title,
                "reference": r.reference,
                "reason": "last_review_date is NULL",
            }
            for r in rows
        ]

        # PX-264 — audit-import triage backlog / unassigned owners
        triage_open = EnterpriseRisk.suggestion_triage_status.in_(
            ["pending", "suggested", "unassigned", "awaiting_triage"]
        )
        unassigned = EnterpriseRisk.risk_owner_id.is_(None)
        filters = [
            EnterpriseRisk.suggestion_triage_status.is_not(None),
            or_(triage_open, unassigned),
        ]
        q = select(
            EnterpriseRisk.id,
            EnterpriseRisk.title,
            EnterpriseRisk.suggestion_triage_status,
            EnterpriseRisk.risk_owner_id,
            EnterpriseRisk.tenant_id,
        ).where(*filters)
        if tenant_id is not None:
            q = q.where(EnterpriseRisk.tenant_id == tenant_id)
        rows = (await db.execute(q.limit(limit))).all()
        cq = select(func.count()).select_from(EnterpriseRisk).where(*filters)
        if tenant_id is not None:
            cq = cq.where(EnterpriseRisk.tenant_id == tenant_id)
        out["PX-264"]["count"] = int((await db.execute(cq)).scalar() or 0)
        out["PX-264"]["sample"] = [
            {
                "px": "PX-264",
                "id": r.id,
                "title": r.title,
                "status": r.suggestion_triage_status,
                "risk_owner_id": r.risk_owner_id,
                "reason": "audit-import triage backlog / unassigned",
            }
            for r in rows
        ]

        # PX-246 — Planet Mark YE2025 draft
        q = select(
            CarbonReportingYear.id,
            CarbonReportingYear.year_label,
            CarbonReportingYear.certification_status,
            CarbonReportingYear.tenant_id,
        ).where(
            or_(
                CarbonReportingYear.year_label.ilike("%2025%"),
                CarbonReportingYear.year_label.ilike("YE2025"),
            )
        )
        if tenant_id is not None:
            q = q.where(CarbonReportingYear.tenant_id == tenant_id)
        rows = (await db.execute(q)).all()
        sample = []
        for r in rows:
            status = (r.certification_status or "").lower()
            if status in {"draft", "submitted", ""}:
                sample.append(
                    {
                        "px": "PX-246",
                        "id": r.id,
                        "year_label": r.year_label,
                        "status": r.certification_status,
                        "reason": "certification not Certified — needs evidence / assessor update",
                    }
                )
        out["PX-246"]["count"] = len(sample)
        out["PX-246"]["sample"] = truncate(sample, limit)

        # PX-273 — open HSEQ discussion threads on campaign documents
        from src.domain.models.document_campaign import DocumentCampaign

        campaign_docs = select(DocumentCampaign.document_id).distinct()
        if tenant_id is not None:
            campaign_docs = campaign_docs.where(DocumentCampaign.tenant_id == tenant_id)
        q = (
            select(
                DocumentDiscussionThread.id,
                DocumentDiscussionThread.title,
                DocumentDiscussionThread.document_id,
                DocumentDiscussionThread.created_at,
                Document.title,
            )
            .join(Document, Document.id == DocumentDiscussionThread.document_id)
            .where(
                DocumentDiscussionThread.status == DiscussionThreadStatus.OPEN,
                DocumentDiscussionThread.document_id.in_(campaign_docs),
            )
            .order_by(DocumentDiscussionThread.created_at.desc())
            .limit(limit)
        )
        if tenant_id is not None:
            q = q.where(DocumentDiscussionThread.tenant_id == tenant_id)
        rows = (await db.execute(q)).all()
        cq = (
            select(func.count())
            .select_from(DocumentDiscussionThread)
            .where(
                DocumentDiscussionThread.status == DiscussionThreadStatus.OPEN,
                DocumentDiscussionThread.document_id.in_(campaign_docs),
            )
        )
        if tenant_id is not None:
            cq = cq.where(DocumentDiscussionThread.tenant_id == tenant_id)
        out["PX-273"]["count"] = int((await db.execute(cq)).scalar() or 0)
        out["PX-273"]["sample"] = [
            {
                "px": "PX-273",
                "thread_id": r.id,
                "thread_title": r.title,
                "document_id": r.document_id,
                "document_title": r[4],
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "reason": "open HSEQ inbox question — human answer required",
            }
            for r in rows
        ]

        # PX-271 — hours anomaly
        q = select(
            HsReportingPeriod.reporting_year,
            HsReportingPeriod.manual_hours,
            HsReportingPeriod.average_fte,
            HsReportingPeriod.hours_per_fte_year,
            HsReportingPeriod.tenant_id,
        ).order_by(HsReportingPeriod.reporting_year.asc())
        if tenant_id is not None:
            q = q.where(HsReportingPeriod.tenant_id == tenant_id)
        years = []
        for r in (await db.execute(q)).all():
            derived = float(r.average_fte or 0) * float(r.hours_per_fte_year or 0)
            hours = float(r.manual_hours) if r.manual_hours is not None else derived
            years.append(
                {
                    "year": r.reporting_year,
                    "hours": hours,
                    "manual_hours": r.manual_hours,
                    "average_fte": r.average_fte,
                    "source": "manual" if r.manual_hours is not None else "fte_derived",
                }
            )
        out["PX-271"]["years"] = years
        by_year = {y["year"]: y["hours"] for y in years}
        h2024 = by_year.get(2024)
        peers = [by_year[y] for y in (2025, 2026) if y in by_year and by_year[y]]
        if h2024 and peers:
            avg_peer = sum(peers) / len(peers)
            ratio = (avg_peer / h2024) if h2024 else None
            out["PX-271"]["anomaly"] = {
                "hours_2024": h2024,
                "peer_avg": avg_peer,
                "peer_over_2024_ratio": round(ratio, 2) if ratio else None,
                "reason": (
                    "2024 hours look ~4x lower than later years — AFR denominator suspect; "
                    "correct via Admin HS reporting hours after human review"
                ),
            }

    return out


async def _amain(args: argparse.Namespace) -> int:
    if args.apply:
        print(
            "inventory_ops_backlog is read-only. Human follow-up is required per RUN021_OPS_PARK.md.",
            file=sys.stderr,
        )
        return 2
    mode = enforce_apply_safety(apply=False, i_understand_prod=False)
    data = await _collect(tenant_id=args.tenant_id, limit=args.limit)
    payload = {
        "script": "inventory_ops_backlog",
        "mode": mode,
        "buckets": data,
        "safety": "Read-only inventory. No --apply path. Human ops required for remediation.",
    }
    emit_report(payload, as_json=args.json)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_safety_args(parser)
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
