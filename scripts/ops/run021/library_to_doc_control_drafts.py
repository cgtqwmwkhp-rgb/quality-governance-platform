#!/usr/bin/env python3
"""PX-263 — Library → Document Control drafts (dry-run by default).

Finds Library ``documents`` that look like controlled policies (H&S Policy,
Incident Management Policy, Quality Assurance Manual, EDI Policy, etc.) and
are not yet linked as ``controlled_documents``.

Default dry-run prints the draft plan. ``--apply`` inserts ``controlled_documents``
rows in ``draft`` status with a golden-thread ``library_document_id`` link.
Never auto-approves / publishes.

Usage:
  python -m scripts.ops.run021.library_to_doc_control_drafts
  python -m scripts.ops.run021.library_to_doc_control_drafts --apply --i-understand-prod
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from typing import Any, Optional

from sqlalchemy import select

from scripts.ops.run021._common import (
    add_safety_args,
    emit_report,
    enforce_apply_safety,
    open_session,
    truncate,
)

POLICY_TITLE_RE = re.compile(
    r"(?:"
    r"H\s*&\s*S\s+Policy|"
    r"Health\s+and\s+Safety\s+Policy|"
    r"Incident\s+Management\s+Policy|"
    r"Quality\s+Assurance\s+Manual|"
    r"EDI\s+Policy|"
    r"Equality.*Diversity|"
    r"\bPolicy\b|"
    r"\bManual\b|"
    r"\bProcedure\b"
    r")",
    re.IGNORECASE,
)


async def _build_plan(*, tenant_id: Optional[int], limit: int) -> list[dict[str, Any]]:
    from src.domain.models.document import Document
    from src.domain.models.document_control import ControlledDocument

    plan: list[dict[str, Any]] = []
    async with await open_session() as db:
        linked = select(ControlledDocument.library_document_id).where(
            ControlledDocument.library_document_id.is_not(None)
        )
        q = select(Document.id, Document.title, Document.tenant_id, Document.reference_number).where(
            Document.id.not_in(linked)
        )
        if tenant_id is not None:
            q = q.where(Document.tenant_id == tenant_id)

        for row in (await db.execute(q)).all():
            title = row.title or ""
            if not POLICY_TITLE_RE.search(title):
                continue
            plan.append(
                {
                    "px": "PX-263",
                    "library_document_id": row.id,
                    "tenant_id": row.tenant_id,
                    "title": title,
                    "reference_number": getattr(row, "reference_number", None),
                    "action": "insert controlled_documents row status=draft",
                    "proposed_document_number": f"DRAFT-LIB-{row.id}",
                }
            )
            if len(plan) >= limit * 5:
                break
    return plan


async def _apply(plan: list[dict[str, Any]]) -> int:
    from src.domain.models.document_control import ControlledDocument

    created = 0
    async with await open_session() as db:
        for item in plan:
            exists = (
                await db.execute(
                    select(ControlledDocument.id).where(
                        ControlledDocument.library_document_id == item["library_document_id"]
                    )
                )
            ).scalar_one_or_none()
            if exists is not None:
                continue
            db.add(
                ControlledDocument(
                    tenant_id=item["tenant_id"],
                    document_number=item["proposed_document_number"],
                    title=item["title"],
                    description="Drafted from Library by Run021 PX-263 ops script; awaiting control workflow.",
                    library_document_id=item["library_document_id"],
                    document_type="policy",
                    category="policies",
                    current_version="1.0",
                    major_version=1,
                    minor_version=0,
                    status="draft",
                    is_current=True,
                )
            )
            created += 1
        await db.commit()
    return created


async def _amain(args: argparse.Namespace) -> int:
    mode = enforce_apply_safety(apply=args.apply, i_understand_prod=args.i_understand_prod)
    plan = await _build_plan(tenant_id=args.tenant_id, limit=args.limit)
    created = 0
    if args.apply:
        created = await _apply(plan)

    payload = {
        "script": "library_to_doc_control_drafts",
        "mode": mode,
        "px": "PX-263",
        "candidates": len(plan),
        "created_drafts": created,
        "plan_sample": truncate(plan, args.limit),
        "safety": (
            "Human approval required before --apply on staging/prod. "
            "Creates draft controlled documents only — never auto-approves. "
            "Default dry-run performs zero writes."
        ),
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
