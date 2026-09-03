"""The link between an audit answer and the evidence captured for it (AUD-F5).

Until this table existed, the only record that a field photo belonged to a
question was ``audit_responses.response_json.evidence_asset_ids`` — a list the
client wrote. AUD-2026-0087 is what that costs: Jamie's photos reached Azure
with ``source_module=audit`` and ``source_id=<run id>``, and not one
``audit_responses`` row referenced them, because the save that would have
written the list never landed. Nothing in the schema could tell anyone which
question the photos answered.

The join is the durable record. ``response_json.evidence_asset_ids`` is kept in
step by the capture write so AUD-F4's completion resolve keeps seeing the id,
but it is a projection: for rows written before this table existed it is the
*only* record, and there is deliberately no backfill (see
``20261119_aud_f5_response_evidence``).

A link row outlives a *soft*-deleted asset, because a soft delete does not
touch this table. AUD-F5 writes the join and nothing reads it back yet, so that
is currently inert; whoever makes this table the read projection must join
``evidence_assets`` and filter ``deleted_at IS NULL``, or a deleted photo will
reappear in an evidence pack.

No ``tenant_id`` column, matching ``audit_responses``' own sibling joins
(``audit_finding_risks``): the tenant is a property of the run this answer
belongs to, and every write and read path reaches the join through a response
loaded under the caller's tenant filter. A second copy of the attribution here
could only ever disagree with the run.
"""

import enum
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Integer, String, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from src.domain.models.base import Base, TimestampMixin


class AuditEvidenceRole(str, enum.Enum):
    """What the linked asset is to the answer.

    Deliberately the language ``EvidenceAssetType`` already uses rather than a
    new vocabulary: a capture is a ``photo``, a drawn sign-off is a
    ``signature``, and anything else an auditor attaches is an ``attachment``.
    The capture endpoint derives the role from the asset type it resolved, so no
    client sends this.
    """

    PHOTO = "photo"
    SIGNATURE = "signature"
    ATTACHMENT = "attachment"


#: Rendered into the CHECK constraint and the migration. A role the database
#: does not know about is a write bug, not a value to store and puzzle over.
ROLE_VALUES: tuple[str, ...] = tuple(role.value for role in AuditEvidenceRole)

_ROLE_CHECK = "role IN (" + ", ".join(f"'{value}'" for value in ROLE_VALUES) + ")"


class AuditResponseEvidence(Base, TimestampMixin):
    """One evidence asset, attached to one audit answer."""

    __tablename__ = "audit_response_evidence"
    __table_args__ = (
        UniqueConstraint(
            "response_id",
            "evidence_asset_id",
            name="uq_audit_response_evidence_response_asset",
        ),
        CheckConstraint(_ROLE_CHECK, name="ck_audit_response_evidence_role"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # CASCADE: a link cannot outlive the answer it describes, and deleting a run
    # already removes its answers. ``AuditResponse`` maps no relationship back
    # here on purpose — a lazy collection on the answer row would load on any
    # attribute touch outside a greenlet, which is the MissingGreenlet class of
    # failure AUD-F4 spent time on. The cascade is therefore invisible to an ORM
    # hook and is recorded as such in
    # ``tests/unit/test_delete_cascade_audit_visibility.py``.
    response_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("audit_responses.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # No ``ondelete`` here, so a physical delete of an asset that an audit
    # answer cites is refused by the database rather than quietly taking the
    # link with it. Evidence is soft-deleted everywhere in this product
    # (``evidence_assets.deleted_at``), so the normal path never reaches this.
    evidence_asset_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("evidence_assets.id"),
        nullable=False,
        index=True,
    )

    role: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=AuditEvidenceRole.PHOTO.value,
        server_default=text(f"'{AuditEvidenceRole.PHOTO.value}'"),
    )

    created_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    def __repr__(self) -> str:
        return (
            f"<AuditResponseEvidence(response_id={self.response_id}, "
            f"evidence_asset_id={self.evidence_asset_id}, role='{self.role}')>"
        )
