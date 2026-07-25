#!/usr/bin/env python3
"""Delete Pinecone vectors that no longer have a document chunk behind them.

#1289 stopped the leak going forward: chunk rows now record their ``vector_id``,
re-indexing deletes vectors the new upsert did not overwrite, and disposal deletes
a document's vectors after the SQL delete commits. None of that reaches vectors
already orphaned before it shipped — documents disposed of earlier, and shrinking
re-indexes whose high-index vectors were simply abandoned. This sweeps those.

Orphans are classified rather than merely counted, because the two classes mean
different things when the numbers come back:

  missing-document  no ``documents`` row at all — disposal or a hard delete.
  missing-chunk     the document lives, but no chunk row claims that index —
                    a re-index that produced fewer chunks than the run before it.

Dry run unless ``--apply`` is passed. Documents with an unfinished index job are
skipped: their chunk rows are mid-rewrite, so "no chunk row" would be a lie.

Usage:
    python -m scripts.maintenance.sweep_orphaned_vectors           # report only
    python -m scripts.maintenance.sweep_orphaned_vectors --apply   # delete
"""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

import httpx
from sqlalchemy import select

from src.domain.models.document import Document, DocumentChunk, IndexJob, IndexJobStatus
from src.domain.services.document_ai_service import VectorSearchService
from src.infrastructure.database import async_session_maker

# Mirrors document_chunk_vector_id; anything else was not written by this app.
_VECTOR_ID = re.compile(r"^doc_(\d+)_chunk_(\d+)$")

_LIST_PAGE_SIZE = 100
_UNFINISHED_JOB_STATUSES = (IndexJobStatus.PENDING, IndexJobStatus.PROCESSING)


@dataclass
class SweepPlan:
    """What the sweep would delete, and why."""

    orphans: dict[str, str] = field(default_factory=dict)
    kept: int = 0
    unrecognised: list[str] = field(default_factory=list)
    skipped_documents: set[int] = field(default_factory=set)

    @property
    def reasons(self) -> Counter:
        return Counter(self.orphans.values())


def classify(
    vector_ids: Iterable[str],
    *,
    live_chunks: set[tuple[int, int]],
    live_documents: set[int],
    skip_documents: set[int],
) -> SweepPlan:
    """Split vector IDs into orphans, keepers and IDs this app did not write.

    Pure so the decision can be tested without Pinecone or a database: getting
    this wrong deletes live vectors, and nothing downstream would notice until a
    user's search quietly stopped finding a document.
    """
    plan = SweepPlan()
    for vector_id in vector_ids:
        match = _VECTOR_ID.match(vector_id)
        if match is None:
            # Never delete what we cannot explain — it may predate this scheme or
            # belong to another writer sharing the index.
            plan.unrecognised.append(vector_id)
            continue

        document_id, chunk_index = int(match.group(1)), int(match.group(2))
        if document_id in skip_documents:
            plan.skipped_documents.add(document_id)
            plan.kept += 1
        elif (document_id, chunk_index) in live_chunks:
            plan.kept += 1
        elif document_id not in live_documents:
            plan.orphans[vector_id] = "missing-document"
        else:
            plan.orphans[vector_id] = "missing-chunk"
    return plan


async def list_vector_ids(service: VectorSearchService) -> list[str]:
    """Enumerate every vector ID in the index's default namespace.

    ``/vectors/list`` is serverless-only, which is also why cleanup deletes by ID
    rather than by metadata filter — see delete_vectors_by_id.

    There is deliberately no namespace option. ``upsert_chunks`` never sets one, so
    every vector this app writes lives in the default namespace (production: 305
    vectors, one namespace). Worse, adding the flag here alone would be actively
    destructive: ``delete_vectors_by_id`` sends no namespace, so listing namespace
    "x" and deleting its IDs would remove the identically-named *live* vectors from
    the default namespace and leave the real orphans untouched. Thread the namespace
    through the delete path first, or not at all.
    """
    ids: list[str] = []
    token: str | None = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        while True:
            params: dict[str, str | int] = {"limit": _LIST_PAGE_SIZE}
            if token:
                params["paginationToken"] = token
            response = await client.get(
                f"{service.base_url}/vectors/list",
                headers=service._headers(),
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
            ids.extend(vector["id"] for vector in payload.get("vectors", []) if vector.get("id"))
            token = (payload.get("pagination") or {}).get("next")
            if not token:
                return ids


async def load_sql_state() -> tuple[set[tuple[int, int]], set[int], set[int]]:
    """Read the chunk keys, document IDs and documents to leave alone."""
    async with async_session_maker() as db:
        chunk_rows = (await db.execute(select(DocumentChunk.document_id, DocumentChunk.chunk_index))).all()
        document_ids = set((await db.execute(select(Document.id))).scalars().all())
        unfinished = (
            await db.execute(select(IndexJob.document_ids).where(IndexJob.status.in_(_UNFINISHED_JOB_STATUSES)))
        ).scalars()

    skip: set[int] = set()
    for document_ids_in_job in unfinished:
        skip.update(int(document_id) for document_id in document_ids_in_job or [])
    return {(document_id, chunk_index) for document_id, chunk_index in chunk_rows}, document_ids, skip


def report(plan: SweepPlan, total: int, *, applied: bool) -> None:
    print(f"  vectors in index:      {total}")
    print(f"  matched a live chunk:  {plan.kept}")
    for reason, count in sorted(plan.reasons.items()):
        print(f"  orphaned ({reason}): {count}")
    if plan.skipped_documents:
        print(f"  skipped (index job in flight): documents {sorted(plan.skipped_documents)}")
    if plan.unrecognised:
        print(f"  unrecognised ID form (left alone): {len(plan.unrecognised)}")
        for vector_id in plan.unrecognised[:5]:
            print(f"    {vector_id}")
    if not plan.orphans:
        print("  nothing to delete")
    elif not applied:
        print(f"  DRY RUN — pass --apply to delete {len(plan.orphans)} vector(s)")


async def _run(args: argparse.Namespace) -> int:
    service = VectorSearchService()
    if not service.api_key:
        print("PINECONE_API_KEY is not set — refusing to report 'no orphans' from an unconfigured index")
        return 2

    vector_ids = await list_vector_ids(service)
    live_chunks, live_documents, skip_documents = await load_sql_state()
    plan = classify(
        vector_ids,
        live_chunks=live_chunks,
        live_documents=live_documents,
        skip_documents=skip_documents,
    )

    report(plan, len(vector_ids), applied=args.apply)
    if not plan.orphans or not args.apply:
        return 0

    if not await service.delete_vectors_by_id(list(plan.orphans)):
        print("  delete failed — deletes are idempotent by ID, so re-running is safe")
        return 1
    print(f"  deleted {len(plan.orphans)} orphaned vector(s)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--apply", action="store_true", help="delete the orphans instead of reporting them")
    args = parser.parse_args()
    try:
        return asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 — script entrypoint
        print(f"[sweep_orphaned_vectors] failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
