from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base


class FailedTask(Base):
    __tablename__ = "failed_tasks"

    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    task_name: Mapped[str] = mapped_column(String(255), nullable=False)
    task_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    exception: Mapped[str] = mapped_column(Text, nullable=False)
    args: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    kwargs: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    failed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc).replace(tzinfo=None)
    )
    retried: Mapped[bool] = mapped_column(Boolean, default=False)
    retried_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
