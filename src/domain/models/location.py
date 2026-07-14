"""Physical locations (sites / workshops) for Safety Asset Management."""

import enum
from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import AuditTrailMixin, Base, CaseInsensitiveEnum, TimestampMixin


class LocationKind(str, enum.Enum):
    SITE = "site"
    WORKSHOP = "workshop"


class Location(Base, TimestampMixin, AuditTrailMixin):
    """Site or workshop where safety assets may be assigned."""

    __tablename__ = "locations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[LocationKind] = mapped_column(CaseInsensitiveEnum(LocationKind), nullable=False, index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("locations.id", ondelete="SET NULL"), nullable=True, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    parent: Mapped[Optional["Location"]] = relationship(
        "Location",
        remote_side="Location.id",
        back_populates="children",
    )
    children: Mapped[List["Location"]] = relationship("Location", back_populates="parent")

    def __repr__(self) -> str:
        return f"<Location(id={self.id}, name='{self.name}', kind={self.kind})>"
