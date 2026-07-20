"""Persist a parsed Atlas training matrix import for a tenant."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.models.engineer import Engineer
from src.domain.models.training_matrix import (
    TrainingMatrixCell,
    TrainingMatrixCourse,
    TrainingMatrixImport,
    TrainingMatrixNameMap,
    TrainingMatrixPerson,
)
from src.domain.services.training_matrix_parser import ParsedMatrix, normalize_course_key, normalize_person_name


async def _unique_engineer_name_index(db: AsyncSession, tenant_id: int) -> dict[str, int]:
    """Map normalized unique Engineer.display_name → engineer id (skip ambiguous names)."""
    eng_rows = (
        await db.execute(select(Engineer.id, Engineer.display_name).where(Engineer.tenant_id == tenant_id))
    ).all()
    eng_by_name: dict[str, int] = {}
    ambiguous_names: set[str] = set()
    for eng_id, name in eng_rows:
        if not name or not name.strip():
            continue
        key = normalize_person_name(name).lower()
        if key in ambiguous_names:
            continue
        if key in eng_by_name:
            eng_by_name.pop(key, None)
            ambiguous_names.add(key)
            continue
        eng_by_name[key] = eng_id
    return eng_by_name


async def _ensure_name_map(
    db: AsyncSession,
    *,
    tenant_id: int,
    atlas_name: str,
    engineer_id: int,
    mapped_by_user_id: Optional[int],
) -> None:
    """Upsert a durable Atlas→employee name map (survives weekly CSV overwrite)."""
    existing = (
        await db.execute(
            select(TrainingMatrixNameMap).where(
                TrainingMatrixNameMap.tenant_id == tenant_id,
                TrainingMatrixNameMap.atlas_name == atlas_name,
            )
        )
    ).scalar_one_or_none()
    if existing:
        existing.engineer_id = engineer_id
        if mapped_by_user_id is not None:
            existing.mapped_by_user_id = mapped_by_user_id
        return
    db.add(
        TrainingMatrixNameMap(
            tenant_id=tenant_id,
            atlas_name=atlas_name,
            engineer_id=engineer_id,
            mapped_by_user_id=mapped_by_user_id,
        )
    )


async def auto_match_training_matrix_names(
    db: AsyncSession,
    *,
    tenant_id: int,
    mapped_by_user_id: Optional[int] = None,
    latest_import_only: bool = True,
) -> dict[str, int]:
    """Re-apply saved name maps + unique display-name auto-match.

    Never clears an existing person.engineer_id. Persists successful matches into
    training_matrix_name_maps so the next Atlas upload keeps them.
    """
    eng_by_name = await _unique_engineer_name_index(db, tenant_id)
    maps = (
        (await db.execute(select(TrainingMatrixNameMap).where(TrainingMatrixNameMap.tenant_id == tenant_id)))
        .scalars()
        .all()
    )
    map_by_name = {normalize_person_name(m.atlas_name).lower(): m.engineer_id for m in maps}

    people_q = select(TrainingMatrixPerson).where(TrainingMatrixPerson.tenant_id == tenant_id)
    if latest_import_only:
        latest = (
            await db.execute(
                select(TrainingMatrixImport)
                .where(TrainingMatrixImport.tenant_id == tenant_id)
                .order_by(TrainingMatrixImport.id.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if latest:
            people_q = people_q.where(TrainingMatrixPerson.last_seen_import_id == latest.id)

    people = (await db.execute(people_q.order_by(TrainingMatrixPerson.atlas_name))).scalars().all()

    from_saved = 0
    from_auto = 0
    already_mapped = 0
    still_unmatched = 0

    for person in people:
        key = normalize_person_name(person.atlas_name).lower()
        if person.engineer_id:
            already_mapped += 1
            await _ensure_name_map(
                db,
                tenant_id=tenant_id,
                atlas_name=person.atlas_name,
                engineer_id=person.engineer_id,
                mapped_by_user_id=mapped_by_user_id,
            )
            continue

        resolved = map_by_name.get(key) or eng_by_name.get(key)
        if not resolved:
            still_unmatched += 1
            continue

        person.engineer_id = resolved
        if key in map_by_name:
            from_saved += 1
        else:
            from_auto += 1
        await _ensure_name_map(
            db,
            tenant_id=tenant_id,
            atlas_name=person.atlas_name,
            engineer_id=resolved,
            mapped_by_user_id=mapped_by_user_id,
        )

    await db.flush()
    return {
        "already_mapped": already_mapped,
        "from_saved_maps": from_saved,
        "from_auto_match": from_auto,
        "still_unmatched": still_unmatched,
        "people_considered": len(people),
    }


async def persist_training_matrix_import(
    db: AsyncSession,
    *,
    tenant_id: int,
    filename: str,
    uploaded_by_user_id: Optional[int],
    parsed: ParsedMatrix,
) -> TrainingMatrixImport:
    eng_by_name = await _unique_engineer_name_index(db, tenant_id)

    maps = (
        (await db.execute(select(TrainingMatrixNameMap).where(TrainingMatrixNameMap.tenant_id == tenant_id)))
        .scalars()
        .all()
    )
    map_by_name = {normalize_person_name(m.atlas_name).lower(): m.engineer_id for m in maps}

    imp = TrainingMatrixImport(
        tenant_id=tenant_id,
        filename=filename,
        uploaded_by_user_id=uploaded_by_user_id,
        status="completed",
        person_count=len(parsed.people),
        course_count=len(parsed.courses),
        cell_count=parsed.cell_count,
        nonempty_cell_count=parsed.nonempty_cell_count,
        expiry_without_passed_count=parsed.expiry_without_passed_count,
    )
    db.add(imp)
    await db.flush()

    # Upsert courses
    course_id_by_key: dict[str, int] = {}
    for course_name in parsed.courses:
        key = normalize_course_key(course_name)
        existing = (
            await db.execute(
                select(TrainingMatrixCourse).where(
                    TrainingMatrixCourse.tenant_id == tenant_id,
                    TrainingMatrixCourse.course_key == key,
                )
            )
        ).scalar_one_or_none()
        if existing:
            existing.display_name = course_name
            existing.last_seen_import_id = imp.id
            course_id_by_key[key] = existing.id
        else:
            row = TrainingMatrixCourse(
                tenant_id=tenant_id,
                course_key=key,
                display_name=course_name,
                last_seen_import_id=imp.id,
            )
            db.add(row)
            await db.flush()
            course_id_by_key[key] = row.id

    # Clear prior cells for tenant (latest-import model) — name maps + requirements are kept.
    old_imports = (
        (
            await db.execute(
                select(TrainingMatrixImport.id).where(
                    TrainingMatrixImport.tenant_id == tenant_id,
                    TrainingMatrixImport.id != imp.id,
                )
            )
        )
        .scalars()
        .all()
    )
    if old_imports:
        await db.execute(
            delete(TrainingMatrixCell).where(
                TrainingMatrixCell.tenant_id == tenant_id,
                TrainingMatrixCell.import_id.in_(old_imports),
            )
        )

    for person in parsed.people:
        atlas_name = normalize_person_name(person.atlas_name)
        key = atlas_name.lower()
        resolved = map_by_name.get(key) or eng_by_name.get(key)

        existing_person = (
            await db.execute(
                select(TrainingMatrixPerson).where(
                    TrainingMatrixPerson.tenant_id == tenant_id,
                    TrainingMatrixPerson.atlas_name == atlas_name,
                )
            )
        ).scalar_one_or_none()
        if existing_person:
            existing_person.department = person.department
            existing_person.last_seen_import_id = imp.id
            # Never wipe a prior link when this week's auto-match misses.
            if resolved is not None:
                existing_person.engineer_id = resolved
            engineer_id = existing_person.engineer_id
            person_id = existing_person.id
        else:
            engineer_id = resolved
            prow = TrainingMatrixPerson(
                tenant_id=tenant_id,
                atlas_name=atlas_name,
                department=person.department,
                engineer_id=engineer_id,
                last_seen_import_id=imp.id,
            )
            db.add(prow)
            await db.flush()
            person_id = prow.id

        if engineer_id is not None:
            await _ensure_name_map(
                db,
                tenant_id=tenant_id,
                atlas_name=atlas_name,
                engineer_id=engineer_id,
                mapped_by_user_id=uploaded_by_user_id,
            )
            map_by_name[key] = engineer_id

        for cell in person.cells:
            db.add(
                TrainingMatrixCell(
                    tenant_id=tenant_id,
                    import_id=imp.id,
                    person_id=person_id,
                    course_id=course_id_by_key[cell.course_key],
                    atlas_status=cell.atlas_status,
                    passed_on=cell.passed_on,
                    expires_on=cell.expires_on,
                )
            )

    await db.flush()
    return imp
