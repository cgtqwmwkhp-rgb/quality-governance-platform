#!/usr/bin/env python3
"""Idempotently (re)seed the Governance Library taxonomy (Wave W0, WA-2).

Loads specs/governance-library/taxonomy.json into `document_categories` +
`document_tags`, and specs/governance-library/functions.json into
`document_functions` + `pel_doc_ref_counters` (one counter per function since
WA-2 / ADR-0023). Safe to run repeatedly — an admin re-running this after a
spec edit will never duplicate rows, never reset an existing PEL counter, and
06.04 (O-Licence & Tachograph) is always re-forced inactive regardless of
what the JSON says (see `document_category_seed_data.DEACTIVATED_TAXONOMY_IDS`).

Usage:
    python -m scripts.governance.library.seed_document_categories
"""

from __future__ import annotations

import asyncio
import sys

from src.domain.services.document_category_service import seed_document_categories
from src.infrastructure.database import async_session_maker


async def _run() -> None:
    async with async_session_maker() as db:
        result = await seed_document_categories(db)
        await db.commit()
        print(
            "[seed_document_categories] categories: "
            f"{result.categories_created} created, {result.categories_updated} updated "
            f"(total {result.total_categories}); functions: {result.functions_created} created, "
            f"{result.functions_updated} updated (total {result.total_functions}); "
            f"tags: {result.tags_created} created, "
            f"{result.tags_updated} updated (total {result.total_tags}); "
            f"counters: {result.counters_created} created"
        )


def main() -> int:
    try:
        asyncio.run(_run())
    except Exception as exc:  # noqa: BLE001 — script entrypoint
        print(f"[seed_document_categories] failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
