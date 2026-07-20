"""Atlas training matrix compliance models (not an LMS).

Completions come from weekly Atlas CSV/XLS exports. QGP stores role/frequency
rules and computes due dates from Passed + frequency_years.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base, TimestampMixin


class TrainingMatrixImport(Base, TimestampMixin):
    __tablename__ = "training_matrix_imports"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    uploaded_by_user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(40), nullable=False, default="completed")
    person_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    course_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cell_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    nonempty_cell_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    expiry_without_passed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class TrainingMatrixCourse(Base, TimestampMixin):
    __tablename__ = "training_matrix_courses"
    __table_args__ = (UniqueConstraint("tenant_id", "course_key", name="uq_training_matrix_course_tenant_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    course_key: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    last_seen_import_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("training_matrix_imports.id", ondelete="SET NULL"), nullable=True
    )


class TrainingMatrixPerson(Base, TimestampMixin):
    __tablename__ = "training_matrix_people"
    __table_args__ = (UniqueConstraint("tenant_id", "atlas_name", name="uq_training_matrix_person_tenant_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    atlas_name: Mapped[str] = mapped_column(String(200), nullable=False)
    department: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    engineer_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("engineers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    last_seen_import_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("training_matrix_imports.id", ondelete="SET NULL"), nullable=True
    )


class TrainingMatrixCell(Base, TimestampMixin):
    __tablename__ = "training_matrix_cells"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "import_id",
            "person_id",
            "course_id",
            name="uq_training_matrix_cell_import_person_course",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    import_id: Mapped[int] = mapped_column(
        ForeignKey("training_matrix_imports.id", ondelete="CASCADE"), nullable=False, index=True
    )
    person_id: Mapped[int] = mapped_column(
        ForeignKey("training_matrix_people.id", ondelete="CASCADE"), nullable=False, index=True
    )
    course_id: Mapped[int] = mapped_column(
        ForeignKey("training_matrix_courses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    atlas_status: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    passed_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expires_on: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


class TrainingMatrixNameMap(Base, TimestampMixin):
    __tablename__ = "training_matrix_name_maps"
    __table_args__ = (UniqueConstraint("tenant_id", "atlas_name", name="uq_training_matrix_name_map_tenant_name"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    atlas_name: Mapped[str] = mapped_column(String(200), nullable=False)
    engineer_id: Mapped[int] = mapped_column(ForeignKey("engineers.id", ondelete="CASCADE"), nullable=False, index=True)
    mapped_by_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    mapped_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class TrainingMatrixRequirement(Base, TimestampMixin):
    __tablename__ = "training_matrix_requirements"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "match_department",
            "match_role_key",
            "course_key",
            name="uq_training_matrix_req_tenant_dept_role_course",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    match_department: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    match_role_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    course_key: Mapped[str] = mapped_column(String(255), nullable=False)
    course_display_name: Mapped[str] = mapped_column(String(500), nullable=False)
    frequency_years: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
