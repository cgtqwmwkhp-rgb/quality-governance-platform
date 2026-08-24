"""JL-UX-W5: cycle baseline snapshot + structured diff (pure, no DB).

A baseline freezes axes and nest edges at time T. Live tables remain the
source of truth for edit — the snapshot is never a fork. Diff keys use JL
``code`` identity (and lane×step / target codes for cells and nest edges) so
a rename of a display name is a *change*, not an add+remove.
"""

from __future__ import annotations

from typing import Any, Iterable, Mapping, Optional

SNAPSHOT_VERSION = 1

#: Sections compared by ``diff_snapshots``. Order is presentation order.
DIFF_SECTIONS: tuple[str, ...] = ("job_type", "lanes", "steps", "cells", "nest_edges")


def _as_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def build_snapshot(
    *,
    job_type: Mapping[str, Any],
    lanes: Iterable[Mapping[str, Any]],
    steps: Iterable[Mapping[str, Any]],
    cells: Iterable[Mapping[str, Any]],
    nest_edges: Iterable[Mapping[str, Any]],
) -> dict[str, Any]:
    """Freeze a pack's axes + nest edges. Codes are the stable identity."""
    return {
        "version": SNAPSHOT_VERSION,
        "job_type": {
            "code": str(job_type["code"]),
            "name": str(job_type["name"]),
            "description": job_type.get("description"),
            "is_active": bool(job_type.get("is_active", True)),
            "sort_order": int(job_type.get("sort_order") or 0),
        },
        "lanes": [
            {
                "code": str(lane["code"]),
                "name": str(lane["name"]),
                "description": lane.get("description"),
                "sort_order": int(lane.get("sort_order") or 0),
                "is_active": bool(lane.get("is_active", True)),
            }
            for lane in lanes
        ],
        "steps": [
            {
                "code": str(step["code"]),
                "name": str(step["name"]),
                "description": step.get("description"),
                "sort_order": int(step.get("sort_order") or 0),
                "is_active": bool(step.get("is_active", True)),
                "pdca_phase": step.get("pdca_phase"),
            }
            for step in steps
        ],
        "cells": [
            {
                "lane_code": str(cell["lane_code"]),
                "step_code": str(cell["step_code"]),
                "requires_evidence": bool(cell.get("requires_evidence", False)),
            }
            for cell in cells
        ],
        "nest_edges": [
            {
                "lane_code": str(edge["lane_code"]),
                "step_code": str(edge["step_code"]),
                "target_job_type_code": str(edge["target_job_type_code"]),
                "label": str(edge.get("label") or ""),
            }
            for edge in nest_edges
        ],
    }


def _lane_key(row: Mapping[str, Any]) -> str:
    return str(row["code"])


def _step_key(row: Mapping[str, Any]) -> str:
    return str(row["code"])


def _cell_key(row: Mapping[str, Any]) -> str:
    return f"{row['lane_code']}|{row['step_code']}"


def _nest_key(row: Mapping[str, Any]) -> str:
    return f"{row['lane_code']}|{row['step_code']}|{row['target_job_type_code']}"


def _index_by(rows: Iterable[Mapping[str, Any]], key_fn) -> dict[str, dict[str, Any]]:
    return {key_fn(row): _as_dict(row) for row in rows}


def _changed_fields(before: Mapping[str, Any], after: Mapping[str, Any]) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    keys = set(before) | set(after)
    for key in sorted(keys):
        left = before.get(key)
        right = after.get(key)
        if left != right:
            fields[key] = {"from": left, "to": right}
    return fields


def _diff_collection(
    *,
    baseline_rows: Iterable[Mapping[str, Any]],
    live_rows: Iterable[Mapping[str, Any]],
    key_fn,
) -> dict[str, list[Any]]:
    baseline_map = _index_by(baseline_rows, key_fn)
    live_map = _index_by(live_rows, key_fn)
    added = [live_map[k] for k in sorted(set(live_map) - set(baseline_map))]
    removed = [baseline_map[k] for k in sorted(set(baseline_map) - set(live_map))]
    changed: list[dict[str, Any]] = []
    for key in sorted(set(baseline_map) & set(live_map)):
        fields = _changed_fields(baseline_map[key], live_map[key])
        if fields:
            changed.append({"key": key, "before": baseline_map[key], "after": live_map[key], "fields": fields})
    return {"added": added, "removed": removed, "changed": changed}


def diff_snapshots(
    baseline: Mapping[str, Any],
    live: Mapping[str, Any],
) -> dict[str, Any]:
    """Structured added / removed / changed between a baseline and live tip."""
    baseline = _as_dict(baseline)
    live = _as_dict(live)

    job_type_fields = _changed_fields(_as_dict(baseline.get("job_type")), _as_dict(live.get("job_type")))
    sections = {
        "job_type": {
            "added": [],
            "removed": [],
            "changed": (
                [
                    {
                        "key": "job_type",
                        "before": _as_dict(baseline.get("job_type")),
                        "after": _as_dict(live.get("job_type")),
                        "fields": job_type_fields,
                    }
                ]
                if job_type_fields
                else []
            ),
        },
        "lanes": _diff_collection(
            baseline_rows=_as_list(baseline.get("lanes")),
            live_rows=_as_list(live.get("lanes")),
            key_fn=_lane_key,
        ),
        "steps": _diff_collection(
            baseline_rows=_as_list(baseline.get("steps")),
            live_rows=_as_list(live.get("steps")),
            key_fn=_step_key,
        ),
        "cells": _diff_collection(
            baseline_rows=_as_list(baseline.get("cells")),
            live_rows=_as_list(live.get("cells")),
            key_fn=_cell_key,
        ),
        "nest_edges": _diff_collection(
            baseline_rows=_as_list(baseline.get("nest_edges")),
            live_rows=_as_list(live.get("nest_edges")),
            key_fn=_nest_key,
        ),
    }

    summary = {
        section: {
            "added": len(payload["added"]),
            "removed": len(payload["removed"]),
            "changed": len(payload["changed"]),
        }
        for section, payload in sections.items()
    }
    has_changes = any(
        summary[section]["added"] or summary[section]["removed"] or summary[section]["changed"]
        for section in DIFF_SECTIONS
    )
    return {
        "has_changes": has_changes,
        "summary": summary,
        "sections": sections,
    }


def viewing_baseline_banner(*, baseline_id: int, label: Optional[str] = None) -> str:
    """Operator-facing cue: viewing a snapshot; edit always targets live tip."""
    named = f' "{label}"' if label else ""
    return (
        f"Viewing baseline{named} #{baseline_id}. "
        "This is a snapshot — edit always targets the live tip, not this baseline."
    )


__all__ = [
    "DIFF_SECTIONS",
    "SNAPSHOT_VERSION",
    "build_snapshot",
    "diff_snapshots",
    "viewing_baseline_banner",
]
