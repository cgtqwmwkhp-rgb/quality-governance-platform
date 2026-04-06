"""Time-stamped owner commentary on unified actions (action_key scoped)."""

from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base, TimestampMixin


class ActionOwnerNote(Base, TimestampMixin):
    """Append-only commentary rows tied to a unified action_key within a tenant."""

    __tablename__ = "action_owner_notes"
    __table_args__ = (Index("ix_action_owner_notes_tenant_key_created", "tenant_id", "action_key", "created_at"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    action_key: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    author_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    body: Mapped[str] = mapped_column(Text, nullable=False)
