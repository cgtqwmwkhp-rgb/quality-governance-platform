#!/usr/bin/env python3
"""Reconcile action-ownership counts across the six stores behind GET /actions/.

Board item ``w3-owner-count`` (PX-168 follow-up): two measurements shared a total
of 21 but disagreed on ownership (8/21 vs 0/21). This script prints every
denominator with an unambiguous label so those two figures cannot be confused
again.

Each store is measured two ways:

1. **total** — row count for the tenant (optional ``--tenant``).
2. **owned_correct** — rows where the store's *real* ownership column is set
   (``owner_id`` for operational stores, ``assigned_to_id`` for CAPA stores).

For CAPA stores the script also prints what a mislabeled ``owner_id IS NOT NULL``
probe would mean: those tables have **no** ``owner_id`` column (see the
denominators module), so the naive figure is reported as ``n/a`` rather than
silently reading NULL. That is the 8-of-21 vs 0-of-21 hazard.

The unified Actions API maps both physical columns onto response ``owner_id``;
see ``docs/uat/ACTION_OWNERSHIP_COUNT_RECONCILIATION.md``.

Usage::

    python scripts/governance/reconcile_action_ownership_counts.py

    env -u PRODDB -u STAGING_DB DATABASE_URL=postgresql+asyncpg://... \\
      python scripts/governance/reconcile_action_ownership_counts.py --tenant 1

Exit code 0 when the connection succeeds — this is a measurement tool, not a
gate. Exit 2 on connection / SQL failure.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402

from scripts.governance.action_ownership_denominators import (  # noqa: E402
    ACTION_OWNERSHIP_STORES,
    ActionOwnershipStore,
    format_store_row,
    naive_wrong_column,
)


@dataclass(frozen=True)
class StoreMeasurement:
    store: ActionOwnershipStore
    total: int
    owned_correct: int
    owned_naive_owner_id: Optional[int]
    naive_note: str


def _quote_ident(name: str) -> str:
    """Quote an identifier for SQL (tables / columns are fixed literals above)."""
    if not name.replace("_", "").isalnum():
        raise ValueError(f"refusing non-identifier: {name!r}")
    return f'"{name}"'


async def _scalar(conn, sql: str, params: Optional[dict] = None) -> int:
    result = await conn.execute(text(sql), params or {})
    value = result.scalar()
    return int(value or 0)


async def _measure_store(
    conn,
    store: ActionOwnershipStore,
    *,
    tenant_id: Optional[int],
) -> StoreMeasurement:
    table = _quote_ident(store.table)
    owner_col = _quote_ident(store.ownership_column)

    if tenant_id is not None:
        total = await _scalar(
            conn,
            f"SELECT COUNT(*) FROM {table} WHERE {_quote_ident('tenant_id')} = :tenant_id",
            {"tenant_id": tenant_id},
        )
        owned_correct = await _scalar(
            conn,
            f"SELECT COUNT(*) FROM {table} "
            f"WHERE {_quote_ident('tenant_id')} = :tenant_id AND {owner_col} IS NOT NULL",
            {"tenant_id": tenant_id},
        )
    else:
        total = await _scalar(conn, f"SELECT COUNT(*) FROM {table}")
        owned_correct = await _scalar(
            conn,
            f"SELECT COUNT(*) FROM {table} WHERE {owner_col} IS NOT NULL",
        )

    wrong = naive_wrong_column(store.table)
    if wrong is None:
        return StoreMeasurement(
            store=store,
            total=total,
            owned_correct=owned_correct,
            owned_naive_owner_id=owned_correct,
            naive_note="same column (operational store)",
        )

    # Registry truth: CAPA stores have no owner_id column. Do not invent a SQL
    # probe that would fail or silently misread — report the hazard explicitly.
    return StoreMeasurement(
        store=store,
        total=total,
        owned_correct=owned_correct,
        owned_naive_owner_id=None,
        naive_note=f"n/a — table has no `{wrong}` column (mislabeled ownership query)",
    )


def _print_legend() -> None:
    print("Action-ownership denominators (w3-owner-count / PX-168 follow-up)")
    print("=" * 78)
    print("Each row is one physical table behind GET /api/v1/actions/.")
    print("owned_correct  = COUNT where the store's real ownership column is set")
    print("owned_naive    = COUNT where owner_id IS NOT NULL (wrong / absent for CAPA)")
    print("unified API    = maps both physical columns onto response.owner_id")
    print()
    print("Label map:")
    for store in ACTION_OWNERSHIP_STORES:
        print(f"  {format_store_row(store)}")
    print()


def _print_measurement(m: StoreMeasurement) -> None:
    naive = "n/a" if m.owned_naive_owner_id is None else str(m.owned_naive_owner_id)
    print(
        f"{m.store.table:24} total={m.total:5d}  "
        f"owned_correct({m.store.ownership_column})={m.owned_correct:5d}  "
        f"owned_naive(owner_id)={naive:>5}  [{m.naive_note}]"
    )


def _print_totals(rows: list[StoreMeasurement]) -> None:
    total = sum(r.total for r in rows)
    owned = sum(r.owned_correct for r in rows)
    print()
    print("-" * 78)
    print(f"{'ALL six stores':24} total={total:5d}  owned_correct(sum)={owned:5d}")
    print(
        "Register truth for 'how many Actions have an owner?' is owned_correct(sum), "
        "which matches GET /actions/ items where owner_id is not null "
        "(after CAPA assigned_to_id → owner_id mapping)."
    )
    print(
        "Do NOT compare a raw SQL `owner_id` count on capa_actions/capa_items to "
        "the unified register — those tables have no owner_id column."
    )


async def _run(tenant_id: Optional[int]) -> int:
    os.environ.setdefault("TESTING", "1")

    url = os.environ.get("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set", file=sys.stderr)
        return 2

    engine = create_async_engine(url)
    try:
        _print_legend()
        if tenant_id is not None:
            print(f"Tenant filter: tenant_id = {tenant_id}")
        else:
            print("Tenant filter: none (all tenants)")
        print()
        async with engine.connect() as conn:
            rows: list[StoreMeasurement] = []
            for store in ACTION_OWNERSHIP_STORES:
                try:
                    m = await _measure_store(conn, store, tenant_id=tenant_id)
                except Exception as exc:  # noqa: BLE001 — measurement tool; report and continue
                    print(f"{store.table:24} ERROR: {exc}")
                    continue
                rows.append(m)
                _print_measurement(m)
            if rows:
                _print_totals(rows)
    finally:
        await engine.dispose()
    return 0


def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--tenant",
        type=int,
        default=None,
        help="Optional tenant_id filter (omit to count every tenant)",
    )
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_run(args.tenant))
    except Exception as exc:  # noqa: BLE001
        print(f"reconcile failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
