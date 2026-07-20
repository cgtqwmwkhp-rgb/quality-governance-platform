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


async def persist_training_matrix_import(
    db: AsyncSession,
    *,
    tenant_id: int,
    filename: str,
    uploaded_by_user_id: Optional[int],
    parsed: ParsedMatrix,
) -> TrainingMatrixImport:
    # Resolve engineer lookup — Engineer model uses tenant_id
    eng_rows = (
        await db.execute(select(Engineer.id, Engineer.display_name).where(Engineer.tenant_id == tenant_id))
    ).all()
    eng_by_name = {normalize_person_name(name).lower(): eng_id for eng_id, name in eng_rows if name and name.strip()}

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

    # Clear prior cells for tenant (latest-import model)
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
        engineer_id = map_by_name.get(key) or eng_by_name.get(key)

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
            existing_person.engineer_id = engineer_id
            existing_person.last_seen_import_id = imp.id
            person_id = existing_person.id
        else:
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
