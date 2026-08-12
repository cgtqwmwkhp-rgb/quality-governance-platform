#!/usr/bin/env python3
"""Seed the PEL-HSEQ-5064 alignment matrix for one tenant.

Reads the checked-in payload at ``specs/standards/pel-hseq-5064-alignment-v1.0.json``
and applies it through the import service, so the seed path and the API path share
one set of rules. Safe to run repeatedly: applying the same payload twice writes
nothing the second time.

Usage::

    python -m scripts.governance.standards.seed_5064_alignment --tenant-id 1
    python -m scripts.governance.standards.seed_5064_alignment --tenant-id 1 --dry-run

``--dry-run`` prints the diff against the tenant's active edition and writes
nothing, which is the same plan the API's ``/alignment/import/plan`` returns.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import Optional

from src.domain.services.standards_alignment_import_service import (
    AlignmentImportError,
    StandardsAlignmentImportService,
    build_edges,
    load_payload,
)
from src.infrastructure.database import async_session_maker


async def _run(*, tenant_id: int, payload_path: Optional[Path], dry_run: bool) -> None:
    payload = load_payload(payload_path)
    edges, warnings = build_edges(payload)
    for warning in warnings:
        print(f"[seed_5064] warning: {warning}")

    print(
        f"[seed_5064] payload {payload.get('source_ref')} v{payload.get('version_label')}: "
        f"{len(payload.get('rows') or [])} clause rows + "
        f"{len(payload.get('supplementary_rows') or [])} supplementary rows "
        f"→ {len(edges)} pair edges"
    )

    async with async_session_maker() as db:
        service = StandardsAlignmentImportService(db)
        if dry_run:
            plan = await service.plan(tenant_id=tenant_id, payload=payload)
            counts = plan.counts
            print(
                f"[seed_5064] dry-run against {plan.active_version_label or 'no active edition'}: "
                f"{counts['added']} added, {counts['changed']} changed, "
                f"{counts['unchanged']} unchanged, {counts['removed']} removed"
            )
            for item in plan.items:
                if item.change_type in ("added", "changed", "removed"):
                    print(
                        f"    {item.change_type:9} {item.clause_ref:8} "
                        f"{item.src_framework}:{item.src_clause_key} ↔ "
                        f"{item.dst_framework or '—'}:{item.dst_clause_key or '—'} "
                        f"{item.previous_verdict or '-'} → {item.verdict or '-'}"
                    )
            return

        result = await service.apply(tenant_id=tenant_id, payload=payload)
        await db.commit()
        if result.created:
            print(
                f"[seed_5064] applied edition {result.version_label} "
                f"(id={result.matrix_version_id}): {result.edges_written} edges across "
                f"{result.rows} rows; superseded={result.superseded_version_id}"
            )
        elif result.reactivated:
            print(
                f"[seed_5064] reactivated edition {result.version_label} "
                f"(id={result.matrix_version_id}): its edge set is live again; "
                f"superseded={result.superseded_version_id}"
            )
        else:
            print(
                f"[seed_5064] already current: edition {result.version_label} "
                f"(id={result.matrix_version_id}) already holds this exact edge set — "
                "nothing written"
            )


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", required=True, type=int)
    parser.add_argument("--payload", type=Path, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    try:
        asyncio.run(_run(tenant_id=args.tenant_id, payload_path=args.payload, dry_run=args.dry_run))
    except AlignmentImportError as exc:
        print(f"[seed_5064] refused: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 — script entrypoint
        print(f"[seed_5064] failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
