"""Standards alignment matrix (PEL-HSEQ-5064): imported clause↔clause verdicts.

Wave 2 PR-C. Two tables:

``matrix_versions``
    One row per imported edition of an alignment matrix workbook. The import is
    versioned rather than mutated so a verdict shown to an auditor can always be
    traced to the edition it came from.

``alignment_edges``
    One row per *unordered pair* of framework clauses, carrying the verdict that
    says whether one piece of evidence can serve both. ``UNIQUE`` is the one
    verdict that is not a pair: it records that a clause has no counterpart at
    all, so ``dst_framework`` is NULL there and only there.

Why pairs and not rows
----------------------
The source workbook prints one verdict per clause *row* across five standards,
but that row verdict is not true of every pair inside it. Clause 9.1.2 is
``DIFFERENT`` as a row, yet ISO 14001 and ISO 45001 9.1.2 are near identical and
one register genuinely serves both — while ISO 9001 9.1.2 (customer satisfaction)
shares nothing but the number. Storing the row verdict only would either deny a
real evidence saving or invent a false one. Pairs are the grain at which the
question "may this evidence serve both?" actually has an answer, which is the
question :mod:`src.domain.services.standards_trap_guard` is asked.

Canonical ordering
------------------
The verdicts are symmetric, so each pair is stored once with
``(src_framework, src_clause_key) < (dst_framework, dst_clause_key)`` by byte
order, applied in Python by :func:`canonical_alignment_pair`. Callers must
canonicalise before querying. Ordering is *not* a CHECK constraint on purpose:
``<`` on text is collation-dependent in PostgreSQL, and a constraint that can
change meaning with the database's collation is worse than one enforced by the
single writer and asserted by a unit test.
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base, CaseInsensitiveEnum, DataClassification, TimestampMixin


class AlignmentVerdict(str, enum.Enum):
    """The four verdicts the 5064 matrix uses. Stored lowercase, shown uppercase.

    ``EXACT``
        Identical requirement. One deliverable satisfies every framework listed,
        with nothing added.
    ``NEAR``
        Same requirement with a discipline-specific addition. One deliverable
        works *provided* it carries the addition, which ``addition_text`` names.
    ``DIFFERENT``
        Same clause number, materially different requirement. This is the trap:
        evidence cannot be shared, and reading across the number is how an
        integrated system fails.
    ``UNIQUE``
        Only one framework asks for it at all.
    """

    EXACT = "exact"
    NEAR = "near"
    DIFFERENT = "different"
    UNIQUE = "unique"

    @property
    def api_value(self) -> str:
        """The uppercase token used in the matrix vocabulary and the UI."""
        return self.value.upper()


class MatrixVersionStatus(str, enum.Enum):
    """Lifecycle of an imported matrix edition."""

    DRAFT = "draft"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


#: Verdicts ordered most restrictive first. Two source rows can describe the same
#: clause pair (clause 6.1.3 as a row, and Annex A 5.31 as an EXACT alignment),
#: and the pair is stored once. When they disagree the most restrictive verdict
#: wins: over-claiming a shared requirement is the failure this matrix exists to
#: prevent, so the tie is broken towards refusing to share evidence.
VERDICT_RESTRICTIVENESS: tuple[AlignmentVerdict, ...] = (
    AlignmentVerdict.DIFFERENT,
    AlignmentVerdict.UNIQUE,
    AlignmentVerdict.NEAR,
    AlignmentVerdict.EXACT,
)

#: Verdicts under which evidence may be shared between two clauses at all.
#: ``NEAR`` is included because the requirement genuinely is the same one — but
#: only when the named addition is carried, which is why callers are handed
#: ``addition_text`` rather than a bare boolean.
SHAREABLE_VERDICTS: frozenset[AlignmentVerdict] = frozenset({AlignmentVerdict.EXACT, AlignmentVerdict.NEAR})

_VERDICT_VALUES = ", ".join(f"'{m.value}'" for m in AlignmentVerdict)
_STATUS_VALUES = ", ".join(f"'{m.value}'" for m in MatrixVersionStatus)


def canonical_alignment_pair(
    src_framework: str,
    src_clause_key: str,
    dst_framework: Optional[str],
    dst_clause_key: Optional[str],
) -> tuple[str, str, Optional[str], Optional[str]]:
    """Order one unordered clause pair deterministically.

    Returns ``(src_framework, src_clause_key, dst_framework, dst_clause_key)``
    with the lexicographically smaller ``(framework, clause_key)`` tuple first.
    A pair with no destination (``UNIQUE``) is returned unchanged.

    Framework ids and clause keys are lowercased first, so the ordering is over
    ASCII byte values and does not depend on a database collation.
    """
    src_fw = (src_framework or "").strip().lower()
    src_key = (src_clause_key or "").strip().lower()
    if dst_framework is None:
        return src_fw, src_key, None, None
    dst_fw = dst_framework.strip().lower()
    dst_key = (dst_clause_key or "").strip().lower()
    if (dst_fw, dst_key) < (src_fw, src_key):
        return dst_fw, dst_key, src_fw, src_key
    return src_fw, src_key, dst_fw, dst_key


class MatrixVersion(Base, TimestampMixin):
    """One imported edition of an alignment matrix workbook."""

    __tablename__ = "matrix_versions"
    __data_classification__ = DataClassification.C2_INTERNAL
    __table_args__ = (
        CheckConstraint(f"status IN ({_STATUS_VALUES})", name="ck_matrix_versions_status"),
        # Idempotency anchor: re-importing byte-identical source content finds the
        # existing version instead of creating a second one.
        Index(
            "ux_matrix_versions_tenant_ref_checksum_live",
            "tenant_id",
            "source_ref",
            "source_checksum",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
            sqlite_where=text("deleted_at IS NULL"),
        ),
        # At most one active edition per source document per tenant.
        Index(
            "ux_matrix_versions_one_active_live",
            "tenant_id",
            "source_ref",
            unique=True,
            postgresql_where=text("status = 'active' AND deleted_at IS NULL"),
            sqlite_where=text("status = 'active' AND deleted_at IS NULL"),
        ),
        Index("ix_matrix_versions_tenant_status", "tenant_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)

    #: Source document reference, e.g. ``PEL-HSEQ-5064``.
    source_ref: Mapped[str] = mapped_column(String(40), nullable=False)
    version_label: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    #: Date printed on the source document, kept as text exactly as printed.
    source_date: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    #: SHA-256 over the canonicalised import payload.
    source_checksum: Mapped[str] = mapped_column(String(64), nullable=False)

    status: Mapped[MatrixVersionStatus] = mapped_column(
        CaseInsensitiveEnum(MatrixVersionStatus, length=16),
        nullable=False,
        default=MatrixVersionStatus.DRAFT,
        server_default=text("'draft'"),
    )

    row_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))
    edge_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))

    #: Frameworks deliberately left out of the import, recorded so the omission
    #: is visible rather than looking like missing data.
    excluded_frameworks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    #: Per-framework coverage honesty (e.g. ``{"chas": {"status": "declared_absent"}}``).
    coverage_declarations: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    imported_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    activated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    def __repr__(self) -> str:
        return (
            f"<MatrixVersion(id={self.id}, source_ref={self.source_ref!r}, "
            f"version={self.version_label!r}, status={self.status!r})>"
        )


class AlignmentEdge(Base, TimestampMixin):
    """One clause pair and the verdict on whether evidence can be shared."""

    __tablename__ = "alignment_edges"
    __data_classification__ = DataClassification.C2_INTERNAL
    __table_args__ = (
        CheckConstraint(f"verdict IN ({_VERDICT_VALUES})", name="ck_alignment_edges_verdict"),
        CheckConstraint(f"row_verdict IN ({_VERDICT_VALUES})", name="ck_alignment_edges_row_verdict"),
        # UNIQUE is the only verdict without a counterpart, and every other
        # verdict must have one. Both directions are enforced so a NULL
        # destination can never be read as "pair we failed to resolve".
        CheckConstraint(
            "(verdict = 'unique' AND dst_framework IS NULL AND dst_clause_key IS NULL) "
            "OR (verdict <> 'unique' AND dst_framework IS NOT NULL AND dst_clause_key IS NOT NULL)",
            name="ck_alignment_edges_unique_has_no_pair",
        ),
        # A clause may align with another clause of the same framework (Annex A
        # 5.33 with clause 7.5), so only a true self-reference is refused.
        CheckConstraint(
            "dst_framework IS NULL OR src_framework <> dst_framework OR src_clause_key <> dst_clause_key",
            name="ck_alignment_edges_no_self_pair",
        ),
        # One live verdict per pair per edition. Split in two because a NULL
        # destination does not collide in a unique index, so the UNIQUE rows need
        # their own narrower key.
        Index(
            "ux_alignment_edges_pair_live",
            "tenant_id",
            "matrix_version_id",
            "src_framework",
            "src_clause_key",
            "dst_framework",
            "dst_clause_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND dst_framework IS NOT NULL"),
            sqlite_where=text("deleted_at IS NULL AND dst_framework IS NOT NULL"),
        ),
        Index(
            "ux_alignment_edges_unique_live",
            "tenant_id",
            "matrix_version_id",
            "src_framework",
            "src_clause_key",
            unique=True,
            postgresql_where=text("deleted_at IS NULL AND dst_framework IS NULL"),
            sqlite_where=text("deleted_at IS NULL AND dst_framework IS NULL"),
        ),
        Index("ix_alignment_edges_tenant_version_row", "tenant_id", "matrix_version_id", "row_key"),
        Index("ix_alignment_edges_tenant_src", "tenant_id", "src_framework", "src_clause_key"),
        Index("ix_alignment_edges_tenant_dst", "tenant_id", "dst_framework", "dst_clause_key"),
        Index("ix_alignment_edges_tenant_verdict", "tenant_id", "verdict"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(Integer, ForeignKey("tenants.id"), nullable=False, index=True)
    matrix_version_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("matrix_versions.id", ondelete="CASCADE"),
        nullable=False,
    )

    #: Groups every edge derived from one printed matrix row.
    row_key: Mapped[str] = mapped_column(String(64), nullable=False)
    #: The shared clause reference as printed, e.g. ``6.1.2``, ``A.5.31``, ``IIP 3``.
    clause_ref: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)

    src_framework: Mapped[str] = mapped_column(String(24), nullable=False)
    #: Catalogue-shaped key, e.g. ``9001-7.2`` — matches ``clauses.catalogue_key``.
    src_clause_key: Mapped[str] = mapped_column(String(50), nullable=False)
    #: The subject this framework gives the clause, where it differs from the
    #: shared title (``6.1.2 environmental aspects`` vs ``hazard identification``).
    src_clause_label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    dst_framework: Mapped[Optional[str]] = mapped_column(String(24), nullable=True)
    dst_clause_key: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    dst_clause_label: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    verdict: Mapped[AlignmentVerdict] = mapped_column(
        CaseInsensitiveEnum(AlignmentVerdict, length=12),
        nullable=False,
    )
    #: The verdict printed against the whole row, kept so the matrix can show
    #: what the source said alongside the pair-level answer.
    row_verdict: Mapped[AlignmentVerdict] = mapped_column(
        CaseInsensitiveEnum(AlignmentVerdict, length=12),
        nullable=False,
    )
    #: True when this pair's verdict differs from ``row_verdict`` because the
    #: source text named the subset explicitly.
    is_pair_override: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=text("false"),
    )

    #: The addition a NEAR verdict requires the shared deliverable to carry.
    addition_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    #: Why the alignment holds, or why reading across the number fails.
    rationale: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    #: The deliverable(s) the source names for this row.
    deliverables: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    source_sheet: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    source_row: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    #: Who authorised this pair (``pel-hseq-5064``, ``ncsc_cyber_essentials``, …).
    source_authority: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    @property
    def is_trap(self) -> bool:
        """True when this pair must never be crossed to claim shared evidence."""
        return self.verdict in (AlignmentVerdict.DIFFERENT, AlignmentVerdict.UNIQUE)

    def __repr__(self) -> str:
        dst = f"{self.dst_framework}:{self.dst_clause_key}" if self.dst_framework else "—"
        return (
            f"<AlignmentEdge(id={self.id}, {self.src_framework}:{self.src_clause_key} "
            f"↔ {dst}, verdict={self.verdict!r})>"
        )
