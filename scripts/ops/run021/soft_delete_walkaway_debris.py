#!/usr/bin/env python3
"""Soft-delete Run021 walk-away residue via PX-177 product services.

Targets (live rows only, ``deleted_at IS NULL``):
  - Explicit refs: COMP-2026-0007, COMP-2026-0018, INA-2026-45D06064,
    INC-2026-0058 / 0059 / 0060
  - Any incident or complaint whose title starts with ``[PURGED-RUN021]``

Safety:
  - Default is dry-run (inventory + plan only).
  - ``--apply`` requires ``--manifest PATH`` and a resolvable ``--actor-email``.
  - Production additionally requires ``--i-understand-prod``.
  - Mutations go through ``ComplaintService.delete_complaint`` /
    ``IncidentService.delete_incident`` (and action soft-delete for orphan
    INA rows), matching DELETE ``/api/v1/{complaints,incidents,actions}``.

Usage:
  python -m scripts.ops.run021.soft_delete_walkaway_debris
  python -m scripts.ops.run021.soft_delete_walkaway_debris --apply \\
      --manifest /tmp/walkaway-stg.json --actor-email david.harris@plantexpand.com
  APP_ENV=production python -m scripts.ops.run021.soft_delete_walkaway_debris \\
      --apply --i-understand-prod --manifest /tmp/walkaway-prod.json \\
      --actor-email david.harris@plantexpand.com
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import or_, select

from scripts.ops.run021._common import (
    add_safety_args,
    emit_report,
    enforce_apply_safety,
    open_session,
    require_database_url,
    utc_now_iso,
)

PURGE_PREFIX = "[PURGED-RUN021]"

EXPLICIT_COMPLAINT_REFS = frozenset({"COMP-2026-0007", "COMP-2026-0018"})
EXPLICIT_INCIDENT_REFS = frozenset({"INC-2026-0058", "INC-2026-0059", "INC-2026-0060"})
EXPLICIT_ACTION_REFS = frozenset({"INA-2026-45D06064"})
EXPLICIT_ACTION_IDS = frozenset({7})


def _row_snapshot(obj: Any, *, kind: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "id": getattr(obj, "id", None),
        "reference_number": getattr(obj, "reference_number", None),
        "title": getattr(obj, "title", None),
        "status": str(getattr(obj, "status", None)),
        "tenant_id": getattr(obj, "tenant_id", None),
        "deleted_at": getattr(obj, "deleted_at", None),
        "deleted_by_id": getattr(obj, "deleted_by_id", None),
        "parent_id": getattr(obj, "incident_id", None) or getattr(obj, "complaint_id", None),
    }


async def _resolve_actor(db, email: str) -> tuple[int, int | None]:
    from src.domain.models.user import User

    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()
    if user is None:
        raise SystemExit(f"Actor email not found: {email!r}")
    if not user.is_active:
        raise SystemExit(f"Actor {email!r} is inactive (id={user.id})")
    return int(user.id), user.tenant_id


async def _collect_targets(db) -> dict[str, list[Any]]:
    from src.domain.models.complaint import Complaint
    from src.domain.models.incident import Incident, IncidentAction

    complaints = (
        (
            await db.execute(
                select(Complaint).where(
                    Complaint.deleted_at.is_(None),
                    or_(
                        Complaint.reference_number.in_(EXPLICIT_COMPLAINT_REFS),
                        Complaint.title.startswith(PURGE_PREFIX),
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    incidents = (
        (
            await db.execute(
                select(Incident).where(
                    Incident.deleted_at.is_(None),
                    or_(
                        Incident.reference_number.in_(EXPLICIT_INCIDENT_REFS),
                        Incident.title.startswith(PURGE_PREFIX),
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    actions = (
        (
            await db.execute(
                select(IncidentAction).where(
                    IncidentAction.deleted_at.is_(None),
                    or_(
                        IncidentAction.reference_number.in_(EXPLICIT_ACTION_REFS),
                        IncidentAction.id.in_(EXPLICIT_ACTION_IDS),
                        IncidentAction.title.startswith(PURGE_PREFIX),
                    ),
                )
            )
        )
        .scalars()
        .all()
    )
    return {
        "complaints": list(complaints),
        "incidents": list(incidents),
        "incident_actions": list(actions),
    }


async def _soft_delete_action(
    db,
    action: Any,
    *,
    user_id: int,
    request_id: str,
) -> None:
    """Mirror DELETE /api/v1/actions/{id}?source_type=incident for orphan INAs."""
    from src.api.routes._action_unified import STORAGE_INCIDENT_ACTION, action_key_for
    from src.domain.services.audit_service import record_audit_event

    now = datetime.now(timezone.utc)
    action.deleted_at = now
    action.deleted_by_id = user_id
    await record_audit_event(
        db=db,
        event_type="unified_action.deleted",
        entity_type="unified_action",
        entity_id=action_key_for(STORAGE_INCIDENT_ACTION, action.id),
        entity_name=action.reference_number,
        action="delete",
        description=f"Soft-deleted incident action {action.reference_number}",
        payload={
            "action_id": action.id,
            "source_type": "incident",
            "source_id": action.incident_id,
            "soft_delete": True,
            "walkaway_ops": True,
        },
        user_id=user_id,
        request_id=request_id,
        tenant_id=action.tenant_id,
    )
    await db.flush()


async def _apply(
    targets: dict[str, list[Any]],
    *,
    actor_id: int,
    actor_tenant_id: int | None,
    request_id: str,
) -> dict[str, list[dict[str, Any]]]:
    from src.domain.services.complaint_service import ComplaintService
    from src.domain.services.incident_service import IncidentService

    after: dict[str, list[dict[str, Any]]] = {
        "complaints": [],
        "incidents": [],
        "incident_actions": [],
    }

    async with await open_session() as db:
        complaint_svc = ComplaintService(db)
        incident_svc = IncidentService(db)

        # Parents first so cascade covers child actions under purged incidents.
        for incident in targets["incidents"]:
            await incident_svc.delete_incident(
                incident.id,
                user_id=actor_id,
                tenant_id=actor_tenant_id,
                request_id=request_id,
                skip_tenant_check=True,
            )
            refreshed = await db.get(type(incident), incident.id)
            after["incidents"].append(_row_snapshot(refreshed, kind="incident"))

        for complaint in targets["complaints"]:
            await complaint_svc.delete_complaint(
                complaint.id,
                user_id=actor_id,
                tenant_id=actor_tenant_id,
                request_id=request_id,
                skip_tenant_check=True,
            )
            refreshed = await db.get(type(complaint), complaint.id)
            after["complaints"].append(_row_snapshot(refreshed, kind="complaint"))

        # Explicit / leftover actions (e.g. INA if parent was not in set).
        from src.domain.models.incident import IncidentAction

        for action in targets["incident_actions"]:
            live = await db.get(IncidentAction, action.id)
            if live is None or live.deleted_at is not None:
                snap = _row_snapshot(live or action, kind="incident_action")
                snap["note"] = "already_soft_deleted_via_cascade_or_prior"
                after["incident_actions"].append(snap)
                continue
            await _soft_delete_action(db, live, user_id=actor_id, request_id=request_id)
            await db.refresh(live)
            after["incident_actions"].append(_row_snapshot(live, kind="incident_action"))

        await db.commit()

    return after


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    add_safety_args(parser)
    parser.add_argument(
        "--actor-email",
        default="david.harris@plantexpand.com",
        help="Active user attributed on deleted_by_id / audit events.",
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=None,
        help="Write before/after JSON evidence here (required with --apply).",
    )
    parser.add_argument(
        "--request-id",
        default=None,
        help="Optional request_id stamped on audit events.",
    )
    return parser


async def _run(args: argparse.Namespace) -> dict[str, Any]:
    require_database_url()
    mode = enforce_apply_safety(apply=args.apply, i_understand_prod=args.i_understand_prod)
    request_id = args.request_id or f"walkaway-px177-{utc_now_iso()}"

    async with await open_session() as db:
        actor_id, actor_tenant_id = await _resolve_actor(db, args.actor_email)
        targets = await _collect_targets(db)
        before = {
            "complaints": [_row_snapshot(r, kind="complaint") for r in targets["complaints"]],
            "incidents": [_row_snapshot(r, kind="incident") for r in targets["incidents"]],
            "incident_actions": [_row_snapshot(r, kind="incident_action") for r in targets["incident_actions"]],
        }

    counts = {k: len(v) for k, v in before.items()}
    payload: dict[str, Any] = {
        "script": "scripts.ops.run021.soft_delete_walkaway_debris",
        "mode": mode,
        "actor_email": args.actor_email,
        "actor_id": actor_id,
        "actor_tenant_id": actor_tenant_id,
        "request_id": request_id,
        "counts": counts,
        "before": before,
        "criteria": {
            "purge_prefix": PURGE_PREFIX,
            "explicit_complaint_refs": sorted(EXPLICIT_COMPLAINT_REFS),
            "explicit_incident_refs": sorted(EXPLICIT_INCIDENT_REFS),
            "explicit_action_refs": sorted(EXPLICIT_ACTION_REFS),
            "explicit_action_ids": sorted(EXPLICIT_ACTION_IDS),
        },
    }

    if not args.apply:
        payload["note"] = "Dry-run only; re-run with --apply --manifest to mutate."
        if args.manifest:
            args.manifest.write_text(json.dumps(payload, indent=2, default=str) + "\n")
            payload["manifest_path"] = str(args.manifest)
        return payload

    if args.manifest is None:
        raise SystemExit("--manifest PATH is required with --apply")

    after = await _apply(
        targets,
        actor_id=actor_id,
        actor_tenant_id=actor_tenant_id,
        request_id=request_id,
    )
    payload["after"] = after
    payload["applied_at"] = utc_now_iso()

    # Post-verify: selected refs must no longer be live.
    async with await open_session() as db:
        remaining = await _collect_targets(db)
        payload["remaining_live_counts"] = {k: len(v) for k, v in remaining.items()}
        payload["remaining_live"] = {
            "complaints": [_row_snapshot(r, kind="complaint") for r in remaining["complaints"]],
            "incidents": [_row_snapshot(r, kind="incident") for r in remaining["incidents"]],
            "incident_actions": [_row_snapshot(r, kind="incident_action") for r in remaining["incident_actions"]],
        }

    args.manifest.write_text(json.dumps(payload, indent=2, default=str) + "\n")
    payload["manifest_path"] = str(args.manifest)

    if any(payload["remaining_live_counts"].values()):
        print(
            "WARNING: some targeted rows remain live after apply; see remaining_live in manifest.",
            file=sys.stderr,
        )
        raise SystemExit(3)
    return payload


def main(argv: Optional[list[str]] = None) -> None:
    args = _build_parser().parse_args(argv)
    import asyncio

    payload = asyncio.run(_run(args))
    emit_report(payload, as_json=args.json)


if __name__ == "__main__":
    main()
