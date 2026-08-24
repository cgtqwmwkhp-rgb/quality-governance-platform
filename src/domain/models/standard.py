"""Standard, Clause, and Control models for ISO standards library."""

import enum
from typing import List, Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import Base, CaseInsensitiveEnum, TimestampMixin


class StandardKind(str, enum.Enum):
    """L-26 scheme converge: ISO editions vs assurance-scheme identity shells."""

    ISO = "iso"
    SCHEME = "scheme"


_KIND_VALUES = ", ".join(f"'{m.value}'" for m in StandardKind)


class Standard(Base, TimestampMixin):
    """Standard model representing an ISO standard (e.g., ISO 9001:2015)."""

    __tablename__ = "standards"
    __table_args__ = (CheckConstraint(f"kind IN ({_KIND_VALUES})", name="ck_standards_kind"),)

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)  # e.g., "ISO9001"
    name: Mapped[str] = mapped_column(String(200), nullable=False)  # e.g., "ISO 9001:2015"
    full_name: Mapped[str] = mapped_column(String(500), nullable=False)  # Full title
    version: Mapped[str] = mapped_column(String(20), nullable=False)  # e.g., "2015"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    effective_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # L-26: iso editions vs UVDB/Planet Mark scheme shells on the same table.
    kind: Mapped[StandardKind] = mapped_column(
        CaseInsensitiveEnum(StandardKind, length=20),
        nullable=False,
        default=StandardKind.ISO,
        server_default=text(f"'{StandardKind.ISO.value}'"),
        index=True,
    )

    # Relationships
    clauses: Mapped[List["Clause"]] = relationship(
        "Clause",
        back_populates="standard",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Standard(id={self.id}, code='{self.code}', name='{self.name}', kind='{self.kind}')>"


class Clause(Base, TimestampMixin):
    """Clause model representing a section/clause within a standard."""

    __tablename__ = "clauses"
    __table_args__ = (
        # D14: CEL.clause_id joins here. Partial unique so legacy nulls can coexist
        # until every row is keyed.
        Index(
            "ux_clauses_catalogue_key",
            "catalogue_key",
            unique=True,
            postgresql_where=text("catalogue_key IS NOT NULL"),
            sqlite_where=text("catalogue_key IS NOT NULL"),
        ),
        Index("ix_clauses_catalogue_key", "catalogue_key"),
    )

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    standard_id: Mapped[int] = mapped_column(ForeignKey("standards.id", ondelete="CASCADE"), nullable=False)
    clause_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # e.g., "4.1", "7.2.1"
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    # D14 / WI-1: equals ALL_CLAUSES / CEL.clause_id (e.g. "9001-7.2").
    catalogue_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    parent_clause_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("clauses.id", ondelete="SET NULL"),
        nullable=True,
    )
    level: Mapped[int] = mapped_column(Integer, default=1)  # Hierarchy level
    sort_order: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    standard: Mapped["Standard"] = relationship("Standard", back_populates="clauses")
    parent_clause: Mapped[Optional["Clause"]] = relationship(
        "Clause",
        remote_side=[id],
        backref="sub_clauses",
    )
    controls: Mapped[List["Control"]] = relationship(
        "Control",
        back_populates="clause",
        cascade="all, delete-orphan",
    )

    @property
    def full_reference(self) -> str:
        """Get full reference including standard code."""
        return f"{self.standard.code} {self.clause_number}"

    def __repr__(self) -> str:
        return (
            f"<Clause(id={self.id}, number='{self.clause_number}', "
            f"catalogue_key='{self.catalogue_key}', title='{self.title}')>"
        )


class Control(Base, TimestampMixin):
    """Control model representing specific controls within a clause."""

    __tablename__ = "controls"

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    clause_id: Mapped[int] = mapped_column(ForeignKey("clauses.id", ondelete="CASCADE"), nullable=False)
    control_number: Mapped[str] = mapped_column(String(20), nullable=False, index=True)  # e.g., "A.5.1.1"
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    implementation_guidance: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # For ISO 27001 Statement of Applicability
    is_applicable: Mapped[bool] = mapped_column(Boolean, default=True)
    applicability_justification: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    implementation_status: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # implemented, partial, planned, not_implemented

    # Relationships
    clause: Mapped["Clause"] = relationship("Clause", back_populates="controls")

    @property
    def full_reference(self) -> str:
        """Get full reference including standard and clause."""
        return f"{self.clause.standard.code} {self.control_number}"

    def __repr__(self) -> str:
        return f"<Control(id={self.id}, number='{self.control_number}', title='{self.title}')>"
