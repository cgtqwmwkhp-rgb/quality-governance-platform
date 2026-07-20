"""Seed editable requirement rows from the Plantexpand 2024 matrix template.

Compliance never reads this module at runtime — only DB rows after seed.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.training_matrix import TrainingMatrixCourse, TrainingMatrixRequirement
from src.domain.services.training_matrix_parser import normalize_course_key
from src.domain.training_matrix.plantexpand_matrix_2024 import (
    MODULE_ALIASES,
    TEMPLATE_ID,
    TEMPLATE_LABEL,
    expand_seed_rows,
)


def _norm_label(value: str) -> str:
    text = (value or "").strip().lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class CourseMatch:
    course_key: str
    display_name: str
    matched_atlas: bool


@dataclass
class SeedResult:
    template_id: str
    template_label: str
    created: int
    skipped_existing: int
    unmatched_modules: list[str]
    created_without_atlas_match: int


def match_module_to_course(
    module: str,
    courses: Sequence[TrainingMatrixCourse],
) -> CourseMatch:
    """Best-effort match PDF module name → Atlas course (fallback: normalized key)."""
    target = _norm_label(module)
    alias_targets = {target}
    for canonical, aliases in MODULE_ALIASES.items():
        if target == canonical or target in {_norm_label(a) for a in aliases}:
            alias_targets.add(canonical)
            alias_targets.update(_norm_label(a) for a in aliases)

    by_norm: dict[str, TrainingMatrixCourse] = {}
    for course in courses:
        by_norm[_norm_label(course.display_name)] = course
        by_norm[_norm_label(course.course_key.replace("_", " "))] = course

    for key in alias_targets:
        hit = by_norm.get(key)
        if hit:
            return CourseMatch(course_key=hit.course_key, display_name=hit.display_name, matched_atlas=True)

    # Containment: prefer longest Atlas name that contains / is contained by module.
    best: Optional[TrainingMatrixCourse] = None
    best_score = 0
    for course in courses:
        label = _norm_label(course.display_name)
        if not label:
            continue
        if target in label or label in target:
            score = min(len(target), len(label))
            if score > best_score:
                best = course
                best_score = score
    if best:
        return CourseMatch(course_key=best.course_key, display_name=best.display_name, matched_atlas=True)

    key = normalize_course_key(module)
    return CourseMatch(course_key=key, display_name=module, matched_atlas=False)


async def seed_plantexpand_2024_requirements(
    db: AsyncSession,
    *,
    tenant_id: int,
    mode: str = "fill_missing",
) -> SeedResult:
    """Insert requirement rows from the 2024 template into the tenant DB.

    mode:
      - fill_missing: create only missing (tenant, dept, role, course) keys
      - refresh_template: upsert frequency/active for rows previously seeded from this template;
        still fill missing. Does not delete admin-created rules.
    """
    if mode not in {"fill_missing", "refresh_template"}:
        raise ValueError("mode must be fill_missing or refresh_template")

    courses = (
        (await db.execute(select(TrainingMatrixCourse).where(TrainingMatrixCourse.tenant_id == tenant_id)))
        .scalars()
        .all()
    )
    existing = (
        (await db.execute(select(TrainingMatrixRequirement).where(TrainingMatrixRequirement.tenant_id == tenant_id)))
        .scalars()
        .all()
    )

    def _req_key(dept: Optional[str], role: Optional[str], course_key: str) -> tuple:
        return ((dept or "").strip().lower(), (role or "").strip().lower(), course_key)

    existing_by_key = {_req_key(r.match_department, r.match_role_key, r.course_key): r for r in existing}

    created = 0
    skipped = 0
    unmatched: set[str] = set()
    created_without_atlas = 0
    seed_note = f"seed:{TEMPLATE_ID}"

    for row in expand_seed_rows():
        module = str(row["module"])
        match = match_module_to_course(module, courses)
        if not match.matched_atlas:
            unmatched.add(module)

        key = _req_key(str(row["match_department"]), None, match.course_key)
        current = existing_by_key.get(key)
        if current:
            if mode == "refresh_template" and (current.notes or "").startswith("seed:"):
                current.frequency_years = int(row["frequency_years"])
                current.course_display_name = match.display_name
                current.is_active = True
                current.notes = seed_note
            else:
                skipped += 1
            continue

        req = TrainingMatrixRequirement(
            tenant_id=tenant_id,
            match_department=str(row["match_department"]),
            match_role_key=None,
            course_key=match.course_key,
            course_display_name=match.display_name,
            frequency_years=int(row["frequency_years"]),
            is_active=True,
            notes=seed_note,
        )
        db.add(req)
        existing_by_key[key] = req
        created += 1
        if not match.matched_atlas:
            created_without_atlas += 1

    await db.commit()
    return SeedResult(
        template_id=TEMPLATE_ID,
        template_label=TEMPLATE_LABEL,
        created=created,
        skipped_existing=skipped,
        unmatched_modules=sorted(unmatched),
        created_without_atlas_match=created_without_atlas,
    )
