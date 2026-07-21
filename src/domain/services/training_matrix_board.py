"""Pure helpers for the manager-facing Training Matrix board (horizon-first view).

These functions take already-computed compliance rows (see
``training_matrix_compliance.evaluate_compliance``) and classify/summarise them for the
board UI. Nothing here talks to the database — the route layer loads rows once and this
module reshapes them.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Mapping, Optional, Sequence

BOARD_ROLES: tuple[str, ...] = ("Engineer", "Workshop", "Office", "Management")

_OVERDUE_STATUSES = ("overdue", "missing", "pending", "failed")
_OK_STATUSES = ("compliant", "due_soon")  # in-cycle: has Passed within frequency

Horizon = str  # one of: "overdue" | "d30" | "d60" | "d180" | "ok"


def is_ok_status(status: Optional[str]) -> bool:
    """True when the module is still in-cycle (compliant or due_soon)."""
    return (status or "").strip().lower() in _OK_STATUSES


def is_gap_status(status: Optional[str]) -> bool:
    """True when the person still needs to complete this required module."""
    return (status or "").strip().lower() in _OVERDUE_STATUSES


def normalize_board_role(value: Optional[str]) -> Optional[str]:
    """Return canonical BOARD_ROLES value if ``value`` matches one (case-insensitive)."""
    if not value:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    for role in BOARD_ROLES:
        if role.lower() == cleaned.lower():
            return role
    return None


def resolve_board_role(department: Optional[str], override: Optional[str] = None) -> Optional[str]:
    """Map to one of BOARD_ROLES.

    Prefers an explicit Admin ``override`` when set. Otherwise returns the first
    role whose lowercased name is a substring of ``department``
    (e.g. "Engineer" matches "Mobile Engineers"). Returns None if no role matches.
    """
    normalized_override = normalize_board_role(override)
    if normalized_override:
        return normalized_override
    if not department:
        return None
    dept_l = department.strip().lower()
    for role in BOARD_ROLES:
        if role.lower() in dept_l:
            return role
    return None


def horizon_for_row(
    status: Optional[str],
    qgp_due_on: Optional[date],
    today: Optional[date] = None,
) -> Horizon:
    """Classify a single person x course compliance row into a due-date horizon bucket.

    - overdue: status is overdue/missing/pending/failed, OR qgp_due_on is in the past.
      (missing/pending/failed rows without a due date fall here too.)
    - Otherwise, bucket by how far qgp_due_on is from today: d30 / d60 / d180 / ok.
    """
    today = today or date.today()
    status_l = (status or "").strip().lower()
    if status_l in _OVERDUE_STATUSES and (qgp_due_on is None or qgp_due_on < today):
        return "overdue"
    if qgp_due_on is None:
        return "overdue" if status_l in _OVERDUE_STATUSES else "ok"
    if qgp_due_on < today:
        return "overdue"
    if qgp_due_on <= today + timedelta(days=30):
        return "d30"
    if qgp_due_on <= today + timedelta(days=60):
        return "d60"
    if qgp_due_on <= today + timedelta(days=180):
        return "d180"
    return "ok"


def days_until_due(qgp_due_on: Optional[date], today: Optional[date] = None) -> Optional[int]:
    """Calendar days from today to qgp_due_on, or None if no due date."""
    if qgp_due_on is None:
        return None
    today = today or date.today()
    return (qgp_due_on - today).days


def _course_label(row: Mapping[str, Any]) -> str:
    return str(row.get("course_display_name") or row.get("course_key") or "Unknown module")


def _row_role(row: Mapping[str, Any]) -> Optional[str]:
    return resolve_board_role(row.get("department"), row.get("board_role_override"))


def person_rollup(
    person_rows: Sequence[Mapping[str, Any]],
    *,
    today: Optional[date] = None,
) -> dict[str, Any]:
    """Complete / overdue / need / pct for one person's full required set."""
    today = today or date.today()
    total = len(person_rows)
    complete = sum(1 for r in person_rows if is_ok_status(r.get("status")))
    overdue = sum(1 for r in person_rows if horizon_for_row(r.get("status"), r.get("qgp_due_on"), today) == "overdue")
    need = total - complete
    pct = round(100 * complete / total) if total else 0
    first = person_rows[0] if person_rows else {}
    return {
        "atlas_name": first.get("atlas_name"),
        "person_id": first.get("person_id"),
        "department": first.get("department"),
        "board_role_override": first.get("board_role_override"),
        "engineer_display_name": first.get("engineer_display_name"),
        "role": _row_role(first) if first else None,
        "complete": complete,
        "overdue": overdue,
        "need": need,
        "total": total,
        "pct": pct,
    }


def compute_module_role_stats(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Module-level OK% (compliant+due_soon) overall and per BOARD_ROLE — hero primary metric."""
    scopes: list[Optional[str]] = [None, *BOARD_ROLES]
    out: list[dict[str, Any]] = []
    for scope in scopes:
        if scope is None:
            scoped = list(rows)
            label = "Overall"
        else:
            scoped = [r for r in rows if _row_role(r) == scope]
            label = scope
        total = len(scoped)
        ok = sum(1 for r in scoped if is_ok_status(r.get("status")))
        out.append(
            {
                "role": label,
                "ok": ok,
                "total": total,
                "pct": round(100 * ok / total) if total else 0,
                "metric": "module_ok",
            }
        )
    return out


def compute_people_fully_ok_stats(
    rows: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """People with every required module OK — secondary hero caption."""
    by_person: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        name = row.get("atlas_name")
        if not name:
            continue
        by_person.setdefault(str(name), []).append(row)

    role_counts: dict[str, dict[str, int]] = {role: {"ok": 0, "total": 0} for role in BOARD_ROLES}
    overall_ok = 0
    overall_total = 0
    for person_rows in by_person.values():
        if not person_rows:
            continue
        fully_ok = all(is_ok_status(r.get("status")) for r in person_rows)
        overall_total += 1
        if fully_ok:
            overall_ok += 1
        role = _row_role(person_rows[0])
        if role:
            role_counts[role]["total"] += 1
            if fully_ok:
                role_counts[role]["ok"] += 1

    out: list[dict[str, Any]] = [
        {
            "role": "Overall",
            "ok": overall_ok,
            "total": overall_total,
            "pct": round(100 * overall_ok / overall_total) if overall_total else 0,
            "metric": "people_fully_ok",
        }
    ]
    for role in BOARD_ROLES:
        c = role_counts[role]
        out.append(
            {
                "role": role,
                "ok": c["ok"],
                "total": c["total"],
                "pct": round(100 * c["ok"] / c["total"]) if c["total"] else 0,
                "metric": "people_fully_ok",
            }
        )
    return out


def compute_horizon_counts(
    rows: Sequence[Mapping[str, Any]],
    *,
    today: Optional[date] = None,
) -> dict[str, int]:
    """Counts by board horizon plus forward d90 (due within 90 days, not overdue)."""
    today = today or date.today()
    counts = {"overdue": 0, "d30": 0, "d60": 0, "d90": 0, "d180": 0, "ok": 0}
    for row in rows:
        h = horizon_for_row(row.get("status"), row.get("qgp_due_on"), today)
        if h in counts:
            counts[h] += 1
        days = days_until_due(row.get("qgp_due_on"), today)
        if days is not None and 0 <= days <= 90:
            counts["d90"] += 1
    return counts


def top_overdue_courses(
    rows: Sequence[Mapping[str, Any]],
    *,
    limit: int = 5,
    today: Optional[date] = None,
) -> list[dict[str, Any]]:
    today = today or date.today()
    counts: dict[str, int] = {}
    for row in rows:
        if horizon_for_row(row.get("status"), row.get("qgp_due_on"), today) != "overdue":
            continue
        label = _course_label(row)
        counts[label] = counts.get(label, 0) + 1
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    return [{"course_display_name": name, "count": count} for name, count in ranked[:limit]]


def build_board_summary(
    rows: Sequence[Mapping[str, Any]],
    *,
    today: Optional[date] = None,
) -> dict[str, Any]:
    """SSOT payload for GET /training-matrix/summary (hero + analytics)."""
    today = today or date.today()
    module_stats = compute_module_role_stats(rows)
    people_stats = compute_people_fully_ok_stats(rows)
    return {
        "module_ok": module_stats,
        "people_fully_ok": people_stats,
        "horizons": compute_horizon_counts(rows, today=today),
        "top_overdue_courses": top_overdue_courses(rows, today=today),
        "required_row_count": len(rows),
        "person_count": len({str(r.get("atlas_name")) for r in rows if r.get("atlas_name")}),
    }


def build_status_briefings(
    rows: Sequence[Mapping[str, Any]],
    role_stats: Mapping[str, Mapping[str, Any]],
    *,
    today: Optional[date] = None,
) -> list[dict[str, str]]:
    """Produce up to 5 grounded, data-derived insights for the rotating status banner.

    ``rows`` are person x course compliance rows (dict-like with at least atlas_name,
    course_display_name/course_key, status, qgp_due_on). ``role_stats`` maps role name
    (BOARD_ROLES, optionally "Overall") to a mapping with at least "pct" (0-100 float
    compliant) and "total" (people counted). Every insight is derived only from the data
    passed in — nothing here is fabricated or hardcoded to a specific course/person.
    """
    today = today or date.today()
    briefings: list[dict[str, str]] = []

    overdue_by_course: dict[str, int] = {}
    d30_count = 0
    by_person: dict[str, list[Mapping[str, Any]]] = {}
    for row in rows:
        horizon = horizon_for_row(row.get("status"), row.get("qgp_due_on"), today)
        if horizon == "overdue":
            label = _course_label(row)
            overdue_by_course[label] = overdue_by_course.get(label, 0) + 1
        elif horizon == "d30":
            d30_count += 1
        name = row.get("atlas_name")
        if name:
            by_person.setdefault(str(name), []).append(row)

    if overdue_by_course:
        course, count = max(overdue_by_course.items(), key=lambda kv: kv[1])
        briefings.append(
            {
                "title": "Highest-risk module",
                "detail": (
                    f"{course} has {count} overdue completion{'s' if count != 1 else ''} "
                    "across the workforce — the biggest single gap right now."
                ),
            }
        )

    new_starters = sorted(
        name
        for name, prows in by_person.items()
        if prows and all((r.get("status") or "").strip().lower() == "missing" for r in prows)
    )
    if new_starters:
        sample = ", ".join(new_starters[:3])
        more = f" and {len(new_starters) - 3} more" if len(new_starters) > 3 else ""
        briefings.append(
            {
                "title": "Likely new starters",
                "detail": (
                    f"{len(new_starters)} people show every required module as missing "
                    f"(no Atlas history yet) — check onboarding for {sample}{more}."
                ),
            }
        )

    role_entries = [
        (role, stats) for role, stats in role_stats.items() if role.strip().lower() != "overall" and stats.get("total")
    ]
    if role_entries:
        weakest = min(role_entries, key=lambda kv: kv[1].get("pct", 0))
        briefings.append(
            {
                "title": "Weakest role",
                "detail": (
                    f"{weakest[0]} is at {weakest[1].get('pct', 0):.0f}% fully compliant — "
                    "the lowest of the role groups."
                ),
            }
        )

    briefings.append(
        {
            "title": "Due in 30 days",
            "detail": (
                f"{d30_count} module completion{'s' if d30_count != 1 else ''} fall due in the "
                "next 30 days — plan Atlas time now to stay ahead of overdue."
            ),
        }
    )

    if role_entries:
        strongest = max(role_entries, key=lambda kv: kv[1].get("pct", 0))
        briefings.append(
            {
                "title": "Strongest role",
                "detail": (f"{strongest[0]} leads at {strongest[1].get('pct', 0):.0f}% fully compliant."),
            }
        )

    return briefings[:5]
