"""Parse Atlas Training Matrix Report CSV (Status / Passed / Expiry triplets)."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Optional


def normalize_course_key(name: str) -> str:
    key = re.sub(r"[^a-z0-9]+", "_", (name or "").strip().lower()).strip("_")
    return key[:255] or "course"


def normalize_person_name(name: str) -> str:
    return re.sub(r"\s+", " ", (name or "").strip())


def parse_atlas_date(value: str | None) -> Optional[date]:
    raw = (value or "").strip()
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).date()
        except ValueError:
            continue
    return None


@dataclass
class ParsedCell:
    course_name: str
    course_key: str
    atlas_status: Optional[str]
    passed_on: Optional[date]
    expires_on: Optional[date]


@dataclass
class ParsedPerson:
    atlas_name: str
    department: Optional[str]
    cells: list[ParsedCell] = field(default_factory=list)


@dataclass
class ParsedMatrix:
    courses: list[str]
    people: list[ParsedPerson]
    cell_count: int
    nonempty_cell_count: int
    expiry_without_passed_count: int


def parse_training_matrix_csv(content: bytes | str) -> ParsedMatrix:
    if isinstance(content, bytes):
        text = content.decode("utf-8-sig", errors="replace")
    else:
        text = content
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if len(rows) < 4:
        raise ValueError("Training matrix CSV must include title, course, status, and data rows")

    course_row = rows[1]
    courses: list[str] = []
    for i in range(2, len(course_row), 3):
        name = (course_row[i] or "").strip()
        if name:
            courses.append(name)

    if not courses:
        raise ValueError("No course columns found in training matrix CSV")

    people: list[ParsedPerson] = []
    cell_count = 0
    nonempty = 0
    expiry_without_passed = 0

    for row in rows[3:]:
        if not row or not (row[0] or "").strip():
            continue
        # Ignore footer noise
        name = normalize_person_name(row[0])
        if name.lower().startswith("page "):
            continue
        department = (row[1] if len(row) > 1 else "").strip() or None
        person = ParsedPerson(atlas_name=name, department=department)
        for ci, course_name in enumerate(courses):
            base = 2 + ci * 3
            cell_count += 1
            status = (row[base] if base < len(row) else "").strip() or None
            passed_s = (row[base + 1] if base + 1 < len(row) else "").strip()
            expiry_s = (row[base + 2] if base + 2 < len(row) else "").strip()
            if not (status or passed_s or expiry_s):
                continue
            if status and status.lower().startswith("page "):
                continue
            nonempty += 1
            passed_on = parse_atlas_date(passed_s)
            expires_on = parse_atlas_date(expiry_s)
            if expires_on and not passed_on:
                expiry_without_passed += 1
            person.cells.append(
                ParsedCell(
                    course_name=course_name,
                    course_key=normalize_course_key(course_name),
                    atlas_status=status,
                    passed_on=passed_on,
                    expires_on=expires_on,
                )
            )
        people.append(person)

    if not people:
        raise ValueError("No people rows found in training matrix CSV")

    return ParsedMatrix(
        courses=courses,
        people=people,
        cell_count=cell_count,
        nonempty_cell_count=nonempty,
        expiry_without_passed_count=expiry_without_passed,
    )
