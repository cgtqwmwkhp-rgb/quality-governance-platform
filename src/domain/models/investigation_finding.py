"""One investigation finding, as a row (INV-C7 / DEC-3).

Until this table existed a finding was a paragraph: ``investigation_runs.data`` held
``findings`` as a single string, flat and — since INV-C4 — also nested under
``sections.section_3_investigation_findings.findings``. Nothing could reference an
individual finding, order it, or count it, so the closure gate could only ask "is the
paragraph non-empty" and the pack could only reprint it.

Deliberately **not** a relationship on ``InvestigationRun``. A ``back_populates`` pair
needs both sides declared, and the run model is shared with the timeline and closure
work in flight; the service reads this table by ``investigation_id`` instead. The
cascade that matters is on the database (``ON DELETE CASCADE``), not on the ORM, so a
deleted run still cannot leave findings behind.

``tenant_id`` is NOT NULL and always filtered on, even though ``investigation_id``
already implies a tenant: the run is fetched and tenant-checked first, and the row
filter is the second, independent refusal. See
``InvestigationFindingsService`` for the write side.
"""

from __future__ import annotations

from typing import Optional

from sqlalchemy import ForeignKey, Index, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import AuditTrailMixin, Base, TimestampMixin

#: Longest body a single finding may carry. Matches the comment body cap in
#: ``AddCommentRequest`` — a finding is prose of the same order, not a document.
FINDING_BODY_MAX_LENGTH = 10000


class InvestigationFinding(Base, TimestampMixin, AuditTrailMixin):
    """A single ordered finding belonging to one investigation run."""

    __tablename__ = "investigation_findings"
    __table_args__ = (
        # The only read this table serves is "the findings of run X, in order".
        Index(
            "ix_investigation_findings_run_order",
            "investigation_id",
            "sort_order",
            "id",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    investigation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("investigation_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    #: Position within the run's findings list, 0-based and dense after any write.
    #: Not unique: a swap would have to violate the constraint mid-transaction, and a
    #: duplicated position degrades to "ordered by (sort_order, id)" rather than to an
    #: error the user cannot act on.
    #:
    #: ``server_default`` as well as ``default`` so the declared schema and the DDL
    #: in 20261120_inv_c7_findings agree — ``alembic check`` compares them on every
    #: build, and a default that exists on only one side reads as drift.
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))

    body: Mapped[str] = mapped_column(Text, nullable=False)

    def __repr__(self) -> str:
        return (
            f"<InvestigationFinding(id={self.id}, investigation_id={self.investigation_id}, "
            f"sort_order={self.sort_order})>"
        )
