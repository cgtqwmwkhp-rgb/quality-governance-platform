"""Governance Library taxonomy: categories, tag vocabulary, PEL reference counters.

Wave W0 (feat/gov-lib-w0-taxonomy-pel) — see specs/governance-library/README.md
for the locked decisions this schema implements. `documents` (src.domain.
models.document.Document) remains the library file system-of-record;
`ControlledDocument` remains the control layer. This module only adds the
taxonomy/classification/reference layer that sits alongside them.
"""

from typing import List, Optional

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import Base, TimestampMixin

# Level-2 (subcategory) taxonomy_id that must always seed inactive — HGV/O-licence
# is out of scope for Plantexpand's current fleet (Wave W0 decision log).
DEACTIVATED_TAXONOMY_IDS = frozenset({"06.04"})


class DocumentCategory(Base, TimestampMixin):
    """Governance Library taxonomy category (2-level: section > subcategory).

    Seeded idempotently from specs/governance-library/taxonomy.json — 13
    sections + 73 subcategories = 86 rows. Global reference/configuration
    data (tenant_id nullable), matching the existing `standards` taxonomy
    pattern: readable by any active user, writable by admins only.
    """

    __tablename__ = "document_categories"
    __table_args__ = (UniqueConstraint("taxonomy_id", name="uq_document_categories_taxonomy_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Natural key from taxonomy.json (e.g. "01", "04.04") — the idempotent seed anchor.
    taxonomy_id: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("document_categories.id", ondelete="SET NULL"), nullable=True, index=True
    )
    level: Mapped[int] = mapped_column(Integer, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    slug: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    ref_prefix: Mapped[str] = mapped_column(String(20), nullable=False)  # "PEL-HSE" | "PEL-HSE-01"
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    default_access: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # all_staff|managers|restricted
    access_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_owner_role: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    review_cycle: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    retention_rule: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    typical_contents: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # False for retired/out-of-scope categories (e.g. 06.04 HGV O-Licence).
    # Inactive categories are excluded from active listings and cannot be
    # assigned to new documents, but are never deleted (taxonomy provenance).
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    parent: Mapped[Optional["DocumentCategory"]] = relationship(
        "DocumentCategory",
        remote_side="DocumentCategory.id",
        back_populates="children",
    )
    children: Mapped[List["DocumentCategory"]] = relationship("DocumentCategory", back_populates="parent")

    def __repr__(self) -> str:
        return f"<DocumentCategory(id={self.id}, taxonomy_id='{self.taxonomy_id}', name='{self.name}')>"


class DocumentTag(Base, TimestampMixin):
    """Governance Library document classification tag vocabulary.

    Admin-managed controlled vocabulary; the document form should offer only
    these (no free-typed tags). ISO/standards certification tags
    (iso-9001/14001/45001/27001) are intentionally excluded from the
    required seed — see Wave W0 decision log. `planet-mark` and subject
    tags are kept.
    """

    __tablename__ = "document_tags"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    slug: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    group: Mapped[str] = mapped_column(String(50), nullable=False)  # standards|subjects|audience|process
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:
        return f"<DocumentTag(slug='{self.slug}', group='{self.group}')>"


class PelDocRefCounter(Base):
    """Atomic per-category sequence counter for PEL-<SECTION>-<SUB>-<SEQ> allocation.

    One row per level-2 `DocumentCategory`. Allocation is a single atomic
    ``UPDATE ... SET next_seq = next_seq + 1 RETURNING next_seq`` so
    concurrent allocations for the same category can never collide —
    see src.domain.services.document_category_service.allocate_pel_doc_ref.
    """

    __tablename__ = "pel_doc_ref_counters"

    category_id: Mapped[int] = mapped_column(
        ForeignKey("document_categories.id", ondelete="CASCADE"),
        primary_key=True,
    )
    next_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    def __repr__(self) -> str:
        return f"<PelDocRefCounter(category_id={self.category_id}, next_seq={self.next_seq})>"
