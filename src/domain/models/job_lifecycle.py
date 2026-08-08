"""Job Lifecycle axes (ADR-0022): Job Type / Lane / Step + cell document refs.

Identity is JL ``code`` + tenant scope — not LookupOption, free-text department,
or a new org entity. Cells hold library document IDs only (document SSOT remains
the library ``Document``). No department annotation column in JL-1.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base, DataClassification, TimestampMixin


class JobType(Base, TimestampMixin):
    """Tenant-scoped process pack (e.g. Commissioning). Identity = ``code``."""

    __tablename__ = "job_types"
    __data_classification__ = DataClassification.C2_INTERNAL
    __table_args__ = (
        Index(
            "ux_job_types_tenant_code_live",
            "tenant_id",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_job_types_tenant_sort", "tenant_id", "sort_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))

    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def __repr__(self) -> str:
        return f"<JobType(id={self.id}, code={self.code!r}, tenant={self.tenant_id})>"


class JobLane(Base, TimestampMixin):
    """Horizontal process axis within a job type. Identity = ``code`` per type."""

    __tablename__ = "job_lanes"
    __data_classification__ = DataClassification.C2_INTERNAL
    __table_args__ = (
        Index(
            "ux_job_lanes_tenant_type_code_live",
            "tenant_id",
            "job_type_id",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_job_lanes_tenant_type_sort", "tenant_id", "job_type_id", "sort_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    job_type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("job_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))

    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def __repr__(self) -> str:
        return f"<JobLane(id={self.id}, code={self.code!r}, job_type_id={self.job_type_id})>"


class JobStep(Base, TimestampMixin):
    """Vertical process axis within a job type (matrix column). Identity = ``code``."""

    __tablename__ = "job_steps"
    __data_classification__ = DataClassification.C2_INTERNAL
    __table_args__ = (
        Index(
            "ux_job_steps_tenant_type_code_live",
            "tenant_id",
            "job_type_id",
            "code",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_job_steps_tenant_type_sort", "tenant_id", "job_type_id", "sort_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    job_type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("job_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    code: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default=text("true"))

    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def __repr__(self) -> str:
        return f"<JobStep(id={self.id}, code={self.code!r}, job_type_id={self.job_type_id})>"


class JobCell(Base, TimestampMixin):
    """Lane × step intersection within a job type. Payload is document refs only."""

    __tablename__ = "job_cells"
    __data_classification__ = DataClassification.C2_INTERNAL
    __table_args__ = (
        Index(
            "ux_job_cells_tenant_type_lane_step_live",
            "tenant_id",
            "job_type_id",
            "lane_id",
            "step_id",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        Index("ix_job_cells_tenant_lane", "tenant_id", "lane_id"),
        Index("ix_job_cells_tenant_step", "tenant_id", "step_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    job_type_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("job_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    lane_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("job_lanes.id", ondelete="CASCADE"),
        nullable=False,
    )
    step_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("job_steps.id", ondelete="CASCADE"),
        nullable=False,
    )

    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None

    def __repr__(self) -> str:
        return (
            f"<JobCell(id={self.id}, type={self.job_type_id}, "
            f"lane={self.lane_id}, step={self.step_id})>"
        )


class JobCellDocument(Base, TimestampMixin):
    """Membership of a library document in a job cell (``library_document_id[]``)."""

    __tablename__ = "job_cell_documents"
    __data_classification__ = DataClassification.C2_INTERNAL
    __table_args__ = (
        UniqueConstraint(
            "cell_id",
            "library_document_id",
            name="ux_job_cell_documents_cell_doc",
        ),
        Index("ix_job_cell_documents_tenant_doc", "tenant_id", "library_document_id"),
        Index("ix_job_cell_documents_tenant_cell_sort", "tenant_id", "cell_id", "sort_order"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    cell_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("job_cells.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    library_document_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))

    def __repr__(self) -> str:
        return (
            f"<JobCellDocument(id={self.id}, cell={self.cell_id}, "
            f"doc={self.library_document_id})>"
        )


__all__ = [
    "JobCell",
    "JobCellDocument",
    "JobLane",
    "JobStep",
    "JobType",
]
