#!/usr/bin/env python3
"""Inventory UAT / CUJ / smoke debris across live registers (Run021 ops park).

Covers:
  PX-125  incident titles / refs that look like test debris
  PX-192  complaint register test rows
  PX-197  test / smoke user accounts (incl. Superuser)
  PX-239  workforce roster test rows
  PX-221  document-campaign UAT drafts
  PX-266  Playwright CUJ audit templates (published)
  PX-275  empty / test engineer audience groups

Default: dry-run report only. Mutations live in ``purge_test_debris`` and
still require ``--apply`` (+ ``--i-understand-prod`` on prod).

Usage:
  python -m scripts.ops.run021.inventory_test_debris
  python -m scripts.ops.run021.inventory_test_debris --json --tenant-id 1
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from typing import Any, Optional

from sqlalchemy import func, select, text

from scripts.ops.run021._common import (
    add_safety_args,
    emit_report,
    enforce_apply_safety,
    matches_test_token,
    open_session,
    summarise_counts,
    truncate,
)


async def _collect(*, tenant_id: Optional[int], limit: int) -> list[dict[str, Any]]:
    # Avoid ORM AuditTemplate: audit.py and audit_template.py both register
    # class name "AuditTemplate" on the same Base → mapper path collision.
    from src.domain.models.complaint import Complaint
    from src.domain.models.document_campaign import DocumentCampaign, EngineerGroup, EngineerGroupMember
    from src.domain.models.engineer import Engineer
    from src.domain.models.incident import Incident
    from src.domain.models.user import User

    hits: list[dict[str, Any]] = []

    async with await open_session() as db:
        # PX-125 incidents
        q = select(Incident.id, Incident.reference_number, Incident.title, Incident.tenant_id)
        if tenant_id is not None:
            q = q.where(Incident.tenant_id == tenant_id)
        for row in (await db.execute(q)).all():
            if matches_test_token(row.reference_number, row.title):
                hits.append(
                    {
                        "px": "PX-125",
                        "table": "incidents",
                        "id": row.id,
                        "tenant_id": row.tenant_id,
                        "reference_number": row.reference_number,
                        "title": row.title,
                        "reason": "title/ref matches UAT/CUJ/TEST/smoke pattern",
                    }
                )

        # PX-192 complaints
        q = select(
            Complaint.id,
            Complaint.reference_number,
            Complaint.title,
            Complaint.complainant_name,
            Complaint.tenant_id,
        )
        if tenant_id is not None:
            q = q.where(Complaint.tenant_id == tenant_id)
        for row in (await db.execute(q)).all():
            if matches_test_token(row.reference_number, row.title, row.complainant_name):
                hits.append(
                    {
                        "px": "PX-192",
                        "table": "complaints",
                        "id": row.id,
                        "tenant_id": row.tenant_id,
                        "reference_number": row.reference_number,
                        "title": row.title,
                        "reason": "title/complainant matches UAT/CUJ pattern",
                    }
                )

        # PX-197 users
        q = select(User.id, User.email, User.first_name, User.last_name, User.is_superuser, User.is_active, User.tenant_id)
        if tenant_id is not None:
            q = q.where(User.tenant_id == tenant_id)
        for row in (await db.execute(q)).all():
            if matches_test_token(row.email, row.first_name, row.last_name):
                hits.append(
                    {
                        "px": "PX-197",
                        "table": "users",
                        "id": row.id,
                        "tenant_id": row.tenant_id,
                        "email": row.email,
                        "name": f"{row.first_name} {row.last_name}",
                        "status": "active" if row.is_active else "inactive",
                        "reason": f"test/smoke account; is_superuser={row.is_superuser}",
                    }
                )

        # PX-239 engineers
        q = select(Engineer.id, Engineer.display_name, Engineer.employee_number, Engineer.is_active, Engineer.tenant_id)
        if tenant_id is not None:
            q = q.where(Engineer.tenant_id == tenant_id)
        for row in (await db.execute(q)).all():
            if matches_test_token(row.display_name, row.employee_number):
                hits.append(
                    {
                        "px": "PX-239",
                        "table": "engineers",
                        "id": row.id,
                        "name": row.display_name,
                        "status": "active" if row.is_active else "inactive",
                        "reason": "display_name/employee_number matches UAT/RBAC pattern",
                    }
                )

        # PX-221 campaigns
        q = select(DocumentCampaign.id, DocumentCampaign.title, DocumentCampaign.status, DocumentCampaign.tenant_id)
        if tenant_id is not None:
            q = q.where(DocumentCampaign.tenant_id == tenant_id)
        for row in (await db.execute(q)).all():
            status = row.status.value if hasattr(row.status, "value") else str(row.status)
            if matches_test_token(row.title):
                hits.append(
                    {
                        "px": "PX-221",
                        "table": "document_campaigns",
                        "id": row.id,
                        "tenant_id": row.tenant_id,
                        "title": row.title,
                        "status": status,
                        "reason": "campaign title matches UAT pattern",
                    }
                )

        # PX-266 audit templates (Core SQL — dual ORM AuditTemplate collision).
        # Live envs use audit_templates; builder table may be absent.
        existing = {
            r
            for r in (
                await db.execute(
                    text(
                        "SELECT table_name FROM information_schema.tables "
                        "WHERE table_schema = 'public' "
                        "AND table_name IN ('audit_templates', 'audit_builder_templates')"
                    )
                )
            ).scalars().all()
        }

        async def _scan_templates(table: str, sql: str, params: dict[str, Any]) -> None:
            for row in (await db.execute(text(sql), params)).mappings().all():
                status = (row["status"] or "").lower()
                name = row["name"] or ""
                if matches_test_token(name) or "Playwright" in name:
                    hits.append(
                        {
                            "px": "PX-266",
                            "table": table,
                            "id": row["id"],
                            "tenant_id": row.get("tenant_id"),
                            "name": name,
                            "status": status,
                            "reason": "Playwright/CUJ fixture template",
                        }
                    )
                elif status in {"published", "true", "t", "1"} and matches_test_token(name):
                    hits.append(
                        {
                            "px": "PX-266",
                            "table": table,
                            "id": row["id"],
                            "name": name,
                            "status": status,
                            "reason": "published test template",
                        }
                    )

        if "audit_templates" in existing:
            tpl_sql = (
                "SELECT id, name, "
                "COALESCE(template_status::text, CASE WHEN is_published THEN 'published' ELSE 'draft' END) "
                "AS status, tenant_id "
                "FROM audit_templates"
            )
            tpl_params: dict[str, Any] = {}
            if tenant_id is not None:
                tpl_sql += " WHERE tenant_id = :tenant_id"
                tpl_params["tenant_id"] = tenant_id
            await _scan_templates("audit_templates", tpl_sql, tpl_params)

        if "audit_builder_templates" in existing:
            tpl_sql = (
                "SELECT id, name, status::text AS status, tenant_id "
                "FROM audit_builder_templates"
            )
            tpl_params = {}
            if tenant_id is not None:
                tpl_sql += " WHERE tenant_id = :tenant_id"
                tpl_params["tenant_id"] = tenant_id
            await _scan_templates("audit_builder_templates", tpl_sql, tpl_params)

        # PX-275 engineer groups (empty and/or test-named)
        member_count = (
            select(EngineerGroupMember.group_id, func.count().label("n"))
            .group_by(EngineerGroupMember.group_id)
            .subquery()
        )
        q = (
            select(EngineerGroup.id, EngineerGroup.name, EngineerGroup.tenant_id, member_count.c.n)
            .outerjoin(member_count, member_count.c.group_id == EngineerGroup.id)
        )
        if tenant_id is not None:
            q = q.where(EngineerGroup.tenant_id == tenant_id)
        for row in (await db.execute(q)).all():
            n = int(row.n or 0)
            if matches_test_token(row.name) or n == 0:
                hits.append(
                    {
                        "px": "PX-275",
                        "table": "engineer_groups",
                        "id": row.id,
                        "tenant_id": row.tenant_id,
                        "name": row.name,
                        "reason": f"test-named and/or empty group (members={n})",
                    }
                )

    return truncate(hits, limit) if limit and len(hits) > limit * 4 else hits


async def _amain(args: argparse.Namespace) -> int:
    # Inventory never mutates; --apply is rejected so operators cannot confuse tools.
    if args.apply:
        print(
            "inventory_test_debris is read-only. Use purge_test_debris.py --apply after human approval.",
            file=sys.stderr,
        )
        return 2
    mode = enforce_apply_safety(apply=False, i_understand_prod=False)
    hits = await _collect(tenant_id=args.tenant_id, limit=args.limit)
    payload = {
        "script": "inventory_test_debris",
        "mode": mode,
        "counts_by_px": summarise_counts(hits),
        "total_hits": len(hits),
        "sample": truncate(hits, args.limit),
        "note": "No writes performed. Review sample, then run purge_test_debris dry-run → human approval → --apply.",
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
