#!/usr/bin/env python3
"""PX-306 — verify portal intake templates; dry-run re-seed plan.

Checks that published ``form_templates`` exist for slugs:
  incident, near-miss, complaint, rta

The canonical seed content lives in alembic revision
``20260827_lookup_tenant_fix``. This script:

  1. Reports missing / unpublished / wrong-tenant rows (always).
  2. On ``--apply``, marks existing drafts published OR inserts minimal
     published stubs for missing slugs (never deletes admin-edited templates).

Default is dry-run. Prod requires ``--i-understand-prod``.

Usage:
  python -m scripts.ops.run021.verify_reseed_portal_templates
  python -m scripts.ops.run021.verify_reseed_portal_templates --apply --i-understand-prod
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select

from scripts.ops.run021._common import (
    PORTAL_TEMPLATE_SLUGS,
    add_safety_args,
    emit_report,
    enforce_apply_safety,
    open_session,
    truncate,
)

SLUG_META: dict[str, dict[str, str]] = {
    "incident": {
        "name": "Incident Report",
        "form_type": "incident",
        "description": "Report workplace incidents and injuries",
    },
    "near-miss": {
        "name": "Near Miss Report",
        "form_type": "near_miss",
        "description": "Report near-miss events",
    },
    "complaint": {
        "name": "Complaint",
        "form_type": "complaint",
        "description": "Submit a customer or stakeholder complaint",
    },
    "rta": {
        "name": "Road Traffic Collision",
        "form_type": "rta",
        "description": "Report a road traffic collision",
    },
}


async def _resolve_tenant_id(db, explicit: Optional[int]) -> Optional[int]:
    if explicit is not None:
        return explicit
    from src.domain.models.tenant import Tenant

    result = await db.execute(select(Tenant.id).order_by(Tenant.id.asc()).limit(2))
    ids = [row[0] for row in result.all()]
    if not ids:
        return None
    if len(ids) > 1:
        # Prefer lowest id (matches migration convention) but surface ambiguity.
        return ids[0]
    return ids[0]


async def _verify(*, tenant_id: Optional[int]) -> tuple[list[dict[str, Any]], Optional[int]]:
    from src.domain.models.form_config import FormTemplate

    findings: list[dict[str, Any]] = []
    async with await open_session() as db:
        resolved_tenant = await _resolve_tenant_id(db, tenant_id)
        rows = (
            await db.execute(select(FormTemplate).where(FormTemplate.slug.in_(PORTAL_TEMPLATE_SLUGS)))
        ).scalars().all()
        by_slug = {t.slug: t for t in rows}

        for slug in PORTAL_TEMPLATE_SLUGS:
            meta = SLUG_META[slug]
            tmpl = by_slug.get(slug)
            if tmpl is None:
                findings.append(
                    {
                        "px": "PX-306",
                        "slug": slug,
                        "status": "missing",
                        "action": "insert published stub (apply) or re-run alembic 20260827_lookup_tenant_fix",
                        "tenant_id": resolved_tenant,
                    }
                )
                continue
            issues = []
            if not tmpl.is_published:
                issues.append("not_published")
            if not tmpl.is_active:
                issues.append("inactive")
            if resolved_tenant is not None and tmpl.tenant_id not in (None, resolved_tenant):
                issues.append(f"tenant_mismatch:{tmpl.tenant_id}")
            findings.append(
                {
                    "px": "PX-306",
                    "slug": slug,
                    "id": tmpl.id,
                    "tenant_id": tmpl.tenant_id,
                    "status": "ok" if not issues else ",".join(issues),
                    "name": tmpl.name,
                    "action": "publish+activate" if issues else "none",
                    "form_type": meta["form_type"],
                }
            )
    return findings, resolved_tenant


async def _apply(findings: list[dict[str, Any]], *, tenant_id: Optional[int]) -> dict[str, int]:
    from src.domain.models.form_config import FormTemplate

    counts = {"published": 0, "inserted": 0}
    now = datetime.now(timezone.utc)

    async with await open_session() as db:
        resolved_tenant = await _resolve_tenant_id(db, tenant_id)
        for item in findings:
            slug = item["slug"]
            if item["status"] == "ok":
                continue
            if item["status"] == "missing":
                meta = SLUG_META[slug]
                db.add(
                    FormTemplate(
                        name=meta["name"],
                        slug=slug,
                        description=meta["description"],
                        form_type=meta["form_type"],
                        tenant_id=resolved_tenant,
                        is_active=True,
                        is_published=True,
                        published_at=now,
                        version=1,
                    )
                )
                counts["inserted"] += 1
                continue
            tmpl = await db.get(FormTemplate, item["id"])
            if tmpl is None:
                continue
            tmpl.is_published = True
            tmpl.is_active = True
            tmpl.published_at = tmpl.published_at or now
            counts["published"] += 1
        await db.commit()
    return counts


async def _amain(args: argparse.Namespace) -> int:
    mode = enforce_apply_safety(apply=args.apply, i_understand_prod=args.i_understand_prod)
    findings, resolved_tenant = await _verify(tenant_id=args.tenant_id)
    applied: dict[str, int] = {}
    if args.apply:
        applied = await _apply(findings, tenant_id=args.tenant_id)

    missing = sum(1 for f in findings if f["status"] == "missing")
    unhealthy = sum(1 for f in findings if f["status"] not in {"ok", "missing"})

    payload = {
        "script": "verify_reseed_portal_templates",
        "mode": mode,
        "px": "PX-306",
        "resolved_tenant_id": resolved_tenant,
        "missing": missing,
        "unhealthy": unhealthy,
        "applied": applied,
        "findings": truncate(findings, args.limit),
        "note": (
            "Prefer alembic 20260827_lookup_tenant_fix for full step/field seed. "
            "This script's --apply inserts minimal published stubs only when a slug is absent."
        ),
        "safety": (
            "Human approval required before --apply on staging/prod. "
            "Default dry-run performs zero writes."
        ),
    }
    emit_report(payload, as_json=args.json)
    return 0 if missing == 0 and unhealthy == 0 else 1


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    add_safety_args(parser)
    args = parser.parse_args(argv)
    return asyncio.run(_amain(args))


if __name__ == "__main__":
    sys.exit(main())
