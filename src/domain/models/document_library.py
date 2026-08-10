"""Governance Library taxonomy: categories, functions, tag vocabulary, PEL counters.

Wave W0 (feat/gov-lib-w0-taxonomy-pel) — see specs/governance-library/README.md
for the locked decisions this schema implements. `documents` (src.domain.
models.document.Document) remains the library file system-of-record;
`ControlledDocument` remains the control layer. This module only adds the
taxonomy/classification/reference layer that sits alongside them.

Wave WA-2 (ADR-0023) adds `document_functions` and moves the PEL sequence
counter from the category to the function: the reference is
`PEL-<FUNCTION>-<SEQ>`, so the *category classifies* and the *reference
identifies*. Category and Function are deliberately different axes — a
policy about information security files to `01.01 Policies` and carries
`PEL-IT-0014`.

NS-1 (Northern Star v6) bands that sequence by cascade level: the reference
is `PEL-<FUNCTION>-<BAND><SEQ>` where the band digit *is* the level, so
`PEL-IT-2014` reads "IT, a Policy, the 14th one". The counter is re-keyed
from `function_id` to `(function_id, level_band)` accordingly. References
already issued under the unbanded form keep their leading `0` and are never
rewritten; a `0` band digit is outside the 1–5 the new scheme allocates, so
the two forms cannot collide.
"""

from typing import List, Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.domain.models.base import Base, TimestampMixin

# Level-2 (subcategory) taxonomy_id that must always seed inactive — HGV/O-licence
# is out of scope for Plantexpand's current fleet (Wave W0 decision log).
DEACTIVATED_TAXONOMY_IDS = frozenset({"06.04"})

# Northern Star v6 cascade levels. The level is not decoration: it is the first
# digit of every sequence the library issues (`PEL-HSEQ-3001` is a level-3
# Procedure), so the band and the level are the same number by construction —
# that is rule R02 ("the first digit of the sequence equals the cascade level").
#
#   1 Manual   2 Policy   3 Procedure/Standard   4 SOP/RAMS/Assessment
#   5 Form/Register/Record
CASCADE_LEVEL_MIN = 1
CASCADE_LEVEL_MAX = 5
CASCADE_LEVELS: tuple[int, ...] = tuple(range(CASCADE_LEVEL_MIN, CASCADE_LEVEL_MAX + 1))

# Digits after the band digit. Four digits total (`[1-5][0-9]{3}`) is the whole
# reference grammar under R01, so a band holds 999 documents and the 1000th is
# refused rather than silently widened — see `allocate_pel_doc_ref`.
PEL_BAND_SEQ_WIDTH = 3
PEL_BAND_CAPACITY = 10**PEL_BAND_SEQ_WIDTH - 1


class DocumentFunction(Base, TimestampMixin):
    """Owning business function for a filed document — the PEL reference axis (ADR-0023).

    Seeded idempotently from specs/governance-library/functions.json (11
    rows). Global reference data (tenant_id nullable), matching the
    `document_categories` / `document_tags` pattern: readable by any active
    user, writable by admins only.

    A function is *not* a pointer to whoever currently owns the document. It
    is fixed when the document is filed, so moving ownership of information
    security from the IT Manager to the DPO leaves every existing
    `PEL-IT-####` reference standing. Deactivate rather than delete — an
    inactive function cannot be chosen for a new document but keeps backing
    every reference already issued under it.
    """

    __tablename__ = "document_functions"
    __table_args__ = (UniqueConstraint("code", name="uq_document_functions_code"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=True, index=True)

    # Natural key from functions.json (e.g. "HSEQ") — the idempotent seed anchor
    # and the literal prefix segment of every reference the function issues.
    code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    def __repr__(self) -> str:
        return f"<DocumentFunction(code='{self.code}', name='{self.name}')>"


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

    # CUT-1 / F-7 §2 — the machine-readable form of `retention_rule`, derived by
    # `library_retention_policy.resolve_retention_rule` at seed time. The prose
    # stays: it is the governance authority and the R19 "basis", and these two
    # are its projection, never a second rule someone can edit independently.
    # NULL where the grammar refuses the prose (a scoped or conditional rule) —
    # those categories are the Citation cutover blocker list, not a default.
    retention_years: Mapped[Optional[int]] = mapped_column(SmallInteger, nullable=True)
    retention_anchor: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)

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
    """Atomic per-(function, band) sequence counter for `PEL-<FUNCTION>-<BAND><SEQ>`.

    One row per `DocumentFunction` *per cascade level* (NS-1 / Northern Star
    v6 — WA-2 had one row per function, and Wave W0 before it had one row per
    level-2 category). A function therefore owns five independent sequences,
    because HSEQ's procedures and HSEQ's forms number separately: the first
    procedure is `PEL-HSEQ-3001` while the first form is `PEL-HSEQ-5001`.

    Allocation is a single atomic ``UPDATE ... SET next_seq = next_seq + 1
    RETURNING next_seq`` scoped to one (function, band) row, so concurrent
    allocations in the same band are guaranteed distinct numbers and
    allocations in *different* bands of the same function no longer contend at
    all — see
    src.domain.services.document_category_service.allocate_pel_doc_ref.

    ``ondelete="RESTRICT"`` rather than CASCADE: deleting the counter would
    restart the sequence and re-issue references that are already printed on
    documents and cited in audit packs. Functions are deactivated, not
    deleted.
    """

    __tablename__ = "pel_doc_ref_counters"
    __table_args__ = (
        CheckConstraint(
            f"level_band >= {CASCADE_LEVEL_MIN} AND level_band <= {CASCADE_LEVEL_MAX}",
            name="ck_pel_doc_ref_counters_level_band",
        ),
    )

    function_id: Mapped[int] = mapped_column(
        ForeignKey("document_functions.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    # The cascade level this sequence numbers, and literally the leading digit
    # of every reference it issues (R02). Part of the primary key, so a band
    # can never acquire a second counter row and fork its own sequence.
    level_band: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    next_seq: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    def __repr__(self) -> str:
        return (
            f"<PelDocRefCounter(function_id={self.function_id}, "
            f"level_band={self.level_band}, next_seq={self.next_seq})>"
        )
