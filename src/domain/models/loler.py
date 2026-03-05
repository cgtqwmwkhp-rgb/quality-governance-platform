"""LOLER 1998 Thorough Examination models."""

from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

if TYPE_CHECKING:
    from src.domain.models.asset import Asset

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, CaseInsensitiveEnum, ReferenceNumberMixin, TimestampMixin
from src.infrastructure.database import Base


class LOLERDefectCategory(str, enum.Enum):
    CAT_A = "cat_a"  # Imminent risk of serious personal injury -- must not be used
    CAT_B = "cat_b"  # Defect that will become dangerous -- repair within time limit
    CAT_C = "cat_c"  # Advisory observation -- good practice improvement


class LOLERExaminationType(str, enum.Enum):
    THOROUGH_EXAMINATION = "thorough_examination"
    INSPECTION = "inspection"
    PROOF_LOAD_TEST = "proof_load_test"


class LOLERExamination(Base, TimestampMixin, ReferenceNumberMixin, AuditTrailMixin):
    """A LOLER 1998 thorough examination record."""

    __tablename__ = "loler_examinations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(
        String(36),
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False,
        index=True,
    )

    # Asset
    asset_id: Mapped[int] = mapped_column(ForeignKey("assets.id"), nullable=False, index=True)

    # Examination details
    examination_type: Mapped[LOLERExaminationType] = mapped_column(
        CaseInsensitiveEnum(LOLERExaminationType),
        default=LOLERExaminationType.THOROUGH_EXAMINATION,
    )
    examination_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_examination_due: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Competent person
    competent_person_name: Mapped[str] = mapped_column(String(200), nullable=False)
    competent_person_employer: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    competent_person_qualification: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # SWL at time of examination
    safe_working_load: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    swl_unit: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

    # Outcome
    safe_to_operate: Mapped[bool] = mapped_column(Boolean, default=True)
    conditions_of_use: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Employer details
    employer_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    employer_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Signature
    examiner_signature: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    asset: Mapped["Asset"] = relationship("Asset")
    defects: Mapped[List["LOLERDefect"]] = relationship(
        "LOLERDefect", back_populates="examination", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<LOLERExamination(id={self.id}, ref='{self.reference_number}', safe={self.safe_to_operate})>"


class LOLERDefect(Base, TimestampMixin):
    """A defect found during a LOLER thorough examination."""

    __tablename__ = "loler_defects"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    examination_id: Mapped[int] = mapped_column(
        ForeignKey("loler_examinations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    category: Mapped[LOLERDefectCategory] = mapped_column(
        CaseInsensitiveEnum(LOLERDefectCategory), nullable=False
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    location_on_equipment: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    remedial_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    timescale: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Linked CAPA
    capa_id: Mapped[Optional[int]] = mapped_column(ForeignKey("capa_actions.id"), nullable=True)

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    resolved: Mapped[bool] = mapped_column(Boolean, default=False)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    examination: Mapped["LOLERExamination"] = relationship("LOLERExamination", back_populates="defects")

    def __repr__(self) -> str:
        return f"<LOLERDefect(id={self.id}, category={self.category})>"
