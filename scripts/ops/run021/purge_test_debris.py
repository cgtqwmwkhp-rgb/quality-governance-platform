#!/usr/bin/env python3
"""Dry-run (default) purge planner for Run021 test debris.

Covers the same PX set as ``inventory_test_debris``:
  PX-125, PX-192, PX-197, PX-239, PX-221, PX-266, PX-275

Safety:
  - Default dry-run prints a plan; nothing is written.
  - ``--apply`` requires human approval (see RUN021_OPS_PARK.md).
  - Production additionally requires ``--i-understand-prod``.
  - Users (PX-197): deactivate + clear superuser; never hard-delete by default.
  - Audit templates (PX-266): archive / unpublish; ``--hard-delete-fixtures``
    required for physical delete of Playwright fixtures.
  - Register rows: soft-close where a status exists; prefix titles with
    ``[PURGED-RUN021]`` rather than hard-delete (FK safety).

Usage:
  python -m scripts.ops.run021.purge_test_debris
  python -m scripts.ops.run021.purge_test_debris --apply --i-understand-prod
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from scripts.ops.run021._common import (
    add_safety_args,
    emit_report,
    enforce_apply_safety,
    open_session,
    summarise_counts,
    truncate,
)
from scripts.ops.run021.inventory_test_debris import _collect

PURGE_PREFIX = "[PURGED-RUN021] "


def _prefix(value: Optional[str]) -> str:
    text = value or ""
    if text.startswith(PURGE_PREFIX):
        return text
    return f"{PURGE_PREFIX}{text}"


async def _apply_plan(hits: list[dict[str, Any]], *, hard_delete_fixtures: bool) -> dict[str, int]:
    from src.domain.models.audit_template import AuditTemplate, TemplateStatus
    from src.domain.models.complaint import Complaint, ComplaintStatus
    from src.domain.models.document_campaign import CampaignStatus, DocumentCampaign, EngineerGroup
    from src.domain.models.engineer import Engineer
    from src.domain.models.incident import Incident, IncidentStatus
    from src.domain.models.user import User

    applied: dict[str, int] = {}
    now = datetime.now(timezone.utc)

    async with await open_session() as db:
        for hit in hits:
            px = hit["px"]
            table = hit["table"]
            row_id = hit["id"]

            if table == "users":
                user = await db.get(User, row_id)
                if user is None:
                    continue
                user.is_active = False
                user.is_superuser = False
                applied[px] = applied.get(px, 0) + 1
            elif table == "incidents":
                incident = await db.get(Incident, row_id)
                if incident is None:
                    continue
                incident.status = IncidentStatus.CLOSED
                incident.closed_at = now
                incident.closure_notes = "Run021 ops park purge (PX-125); human-approved."
                incident.title = _prefix(incident.title)
                applied[px] = applied.get(px, 0) + 1
            elif table == "complaints":
                complaint = await db.get(Complaint, row_id)
                if complaint is None:
                    continue
                complaint.status = ComplaintStatus.CLOSED
                complaint.closed_at = now
                complaint.closure_notes = "Run021 ops park purge (PX-192); human-approved."
                complaint.title = _prefix(complaint.title)
                applied[px] = applied.get(px, 0) + 1
            elif table == "engineers":
                engineer = await db.get(Engineer, row_id)
                if engineer is None:
                    continue
                engineer.is_active = False
                applied[px] = applied.get(px, 0) + 1
            elif table == "document_campaigns":
                campaign = await db.get(DocumentCampaign, row_id)
                if campaign is None:
                    continue
                campaign.status = CampaignStatus.CLOSED
                campaign.title = _prefix(campaign.title)
                applied[px] = applied.get(px, 0) + 1
            elif table == "audit_builder_templates":
                template = await db.get(AuditTemplate, row_id)
                if template is None:
                    continue
                if hard_delete_fixtures:
                    await db.delete(template)
                else:
                    template.status = TemplateStatus.ARCHIVED
                applied[px] = applied.get(px, 0) + 1
            elif table == "engineer_groups":
                group = await db.get(EngineerGroup, row_id)
                if group is None:
                    continue
                group.name = _prefix(group.name)
                applied[px] = applied.get(px, 0) + 1

        await db.commit()
    return applied


def _planned_action(hit: dict[str, Any], *, hard_delete_fixtures: bool) -> str:
    table = hit["table"]
    if table == "users":
        return "deactivate + clear is_superuser"
    if table == "incidents":
        return "close + prefix title [PURGED-RUN021]"
    if table == "complaints":
        return "close + prefix title [PURGED-RUN021]"
    if table == "engineers":
        return "set is_active=false"
    if table == "document_campaigns":
        return "close + prefix title [PURGED-RUN021]"
    if table == "audit_builder_templates":
        return "HARD DELETE fixture" if hard_delete_fixtures else "archive (unpublish)"
    if table == "engineer_groups":
        return "prefix name [PURGED-RUN021] (retain row)"
    return "review-only"


async def _amain(args: argparse.Namespace) -> int:
    mode = enforce_apply_safety(apply=args.apply, i_understand_prod=args.i_understand_prod)
    hits = await _collect(tenant_id=args.tenant_id, limit=args.limit * 10)
    plan = [
        {
            **hit,
            "action": _planned_action(hit, hard_delete_fixtures=args.hard_delete_fixtures),
        }
        for hit in hits
    ]

    applied: dict[str, int] = {}
    if args.apply:
        applied = await _apply_plan(plan, hard_delete_fixtures=args.hard_delete_fixtures)

    payload = {
        "script": "purge_test_debris",
        "mode": mode,
        "counts_by_px": summarise_counts(plan),
        "total_planned": len(plan),
        "applied_counts": applied,
        "hard_delete_fixtures": bool(args.hard_delete_fixtures),
        "plan_sample": truncate(plan, args.limit),
        "safety": (
            "Human approval required before --apply on staging/prod. "
            "Default dry-run performs zero writes. "
            "Prod additionally requires --i-understand-prod."
        ),
    }
    emit_report(payload, as_json=args.json)
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_safety_args(parser)
    parser.add_argument(
        "--hard-delete-fixtures",
        action="store_true",
        default=False,
        help="PX-266 only: physically delete Playwright fixtures instead of archiving. Off by default.",
    )
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
