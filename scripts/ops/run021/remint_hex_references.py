#!/usr/bin/env python3
"""PX-126 remint runner — hex portal refs → sequential PREFIX-YYYY-NNNN.

Lane S owns the *mint* fix (stop issuing hex). This script remints existing
rows that already carry ``PREFIX-YYYY-XXXXXXXX`` hex suffixes.

Default: dry-run mapping only. ``--apply`` writes new sequential refs and
leaves an audit mapping table in ``system_settings`` (JSON).

Tables scanned: incidents, complaints, near_misses, rtas (when present).

Usage:
  python -m scripts.ops.run021.remint_hex_references
  python -m scripts.ops.run021.remint_hex_references --apply --i-understand-prod
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from typing import Any, Optional

from sqlalchemy import select

from scripts.ops.run021._common import (
    HEX_REF_RE,
    add_safety_args,
    emit_report,
    enforce_apply_safety,
    is_hex_reference,
    open_session,
    truncate,
    utc_now_iso,
)

LEDGER_KEY = "ops.run021.px126_remint_mapping"


def _next_seq(existing: set[str], prefix: str, year: str) -> str:
    n = 1
    while True:
        candidate = f"{prefix}-{year}-{n:04d}"
        if candidate not in existing:
            return candidate
        n += 1


async def _load_models():
    from src.domain.models.complaint import Complaint
    from src.domain.models.incident import Incident

    models: list[tuple[str, Any, str]] = [
        ("incidents", Incident, "INC"),
        ("complaints", Complaint, "COMP"),
    ]
    try:
        from src.domain.models.near_miss import NearMiss

        models.append(("near_misses", NearMiss, "NM"))
    except Exception:
        pass
    try:
        from src.domain.models.rta import RoadTrafficCollision

        models.append(("road_traffic_collisions", RoadTrafficCollision, "RTA"))
    except Exception:
        pass
    return models


async def _build_plan(*, tenant_id: Optional[int]) -> list[dict[str, Any]]:
    models = await _load_models()
    plan: list[dict[str, Any]] = []

    async with await open_session() as db:
        for table, model, expected_prefix in models:
            q = select(model.id, model.reference_number, model.tenant_id)
            if tenant_id is not None and hasattr(model, "tenant_id"):
                q = q.where(model.tenant_id == tenant_id)

            rows = (await db.execute(q)).all()
            existing = {r.reference_number for r in rows if r.reference_number}
            # Also reserve sequential numbers we are about to allocate within this plan.
            reserved = set(existing)

            for row in rows:
                ref = row.reference_number
                if not is_hex_reference(ref):
                    continue
                match = HEX_REF_RE.match(ref.strip())
                assert match is not None
                prefix, year, _hex = match.groups()
                if prefix != expected_prefix:
                    # Still remint using the prefix embedded in the ref.
                    pass
                new_ref = _next_seq(reserved, prefix, year)
                reserved.add(new_ref)
                plan.append(
                    {
                        "px": "PX-126",
                        "table": table,
                        "id": row.id,
                        "tenant_id": row.tenant_id,
                        "old_reference": ref,
                        "new_reference": new_ref,
                        "action": "rewrite reference_number hex→sequential",
                    }
                )
    return plan


async def _apply(plan: list[dict[str, Any]]) -> int:
    models = {table: model for table, model, _ in await _load_models()}
    from src.domain.models.form_config import SystemSetting

    async with await open_session() as db:
        for item in plan:
            model = models[item["table"]]
            obj = await db.get(model, item["id"])
            if obj is None:
                continue
            if obj.reference_number != item["old_reference"]:
                # Concurrent change — skip rather than clobber.
                continue
            obj.reference_number = item["new_reference"]

        mapping_blob = {
            "generated_at": utc_now_iso(),
            "count": len(plan),
            "mappings": [
                {
                    "table": i["table"],
                    "id": i["id"],
                    "old": i["old_reference"],
                    "new": i["new_reference"],
                }
                for i in plan
            ],
        }
        existing = (
            await db.execute(select(SystemSetting).where(SystemSetting.key == LEDGER_KEY))
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                SystemSetting(
                    key=LEDGER_KEY,
                    value=json.dumps(mapping_blob),
                    description="Run021 PX-126 remint mapping (ops park)",
                )
            )
        else:
            existing.value = json.dumps(mapping_blob)

        await db.commit()
    return len(plan)


async def _amain(args: argparse.Namespace) -> int:
    mode = enforce_apply_safety(apply=args.apply, i_understand_prod=args.i_understand_prod)
    plan = await _build_plan(tenant_id=args.tenant_id)
    applied = 0
    if args.apply:
        applied = await _apply(plan)

    payload = {
        "script": "remint_hex_references",
        "mode": mode,
        "px": "PX-126",
        "total_hex_refs": len(plan),
        "applied": applied,
        "ledger_key": LEDGER_KEY,
        "plan_sample": truncate(plan, args.limit),
        "safety": (
            "Human approval required before --apply on staging/prod. "
            "Mint-path fix is Lane S; this script only remints existing hex rows. "
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
