#!/usr/bin/env python3
"""Idempotently seed the Doc Graph Incident Management demo vertical.

Requires DOCUMENT_GRAPH_ENABLED (the script refuses to run when the flag is off
so operators cannot invent edges in environments that have not opted in).

Usage:
    DOCUMENT_GRAPH_ENABLED=true \\
      python -m scripts.governance.library.seed_document_graph_im --tenant-id 1

Optional:
    --actor-id N          Stamp confirmed_by_id on newly created edges
    --no-create-docs      Only link existing titles; do not invent stub documents
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from src.core.config import settings
from src.domain.services.document_graph_im_seed import DocumentGraphImSeedService
from src.infrastructure.database import async_session_maker


async def _run(*, tenant_id: int, actor_id: int | None, create_missing_documents: bool) -> int:
    if not settings.document_graph_enabled:
        print(
            "[seed_document_graph_im] refused: DOCUMENT_GRAPH_ENABLED is off",
            file=sys.stderr,
        )
        return 2

    async with async_session_maker() as db:
        service = DocumentGraphImSeedService(db)
        result = await service.seed(
            tenant_id=tenant_id,
            actor_id=actor_id,
            create_missing_documents=create_missing_documents,
        )

    print(
        "[seed_document_graph_im] documents: "
        f"{result.documents_created} created, {result.documents_reused} reused; "
        f"edges: {result.edges_created} created, {result.edges_reused} reused"
    )
    for doc in result.documents:
        verb = "created" if doc.created else "reused"
        print(f"  doc[{doc.role}] id={doc.document_id} ({verb}) {doc.title!r}")
    for edge in result.edges:
        verb = "created" if edge.created else "reused"
        print(f"  edge[{edge.edge_type}] {edge.src_role}→{edge.dst_role} " f"id={edge.edge_id} ({verb})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tenant-id", type=int, required=True)
    parser.add_argument("--actor-id", type=int, default=None)
    parser.add_argument(
        "--no-create-docs",
        action="store_true",
        help="Do not create stub library documents when titles are missing",
    )
    args = parser.parse_args(argv)
    try:
        return asyncio.run(
            _run(
                tenant_id=args.tenant_id,
                actor_id=args.actor_id,
                create_missing_documents=not args.no_create_docs,
            )
        )
    except Exception as exc:  # noqa: BLE001 — script entrypoint
        print(f"[seed_document_graph_im] failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
