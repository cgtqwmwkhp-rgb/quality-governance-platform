"""Issuing a customer pack: the gate (DEC-4) and the retained bytes (DEC-5).

Generating a pack and *issuing* one are different acts. Generating produces an
immutable, already-redacted snapshot; issuing hands that snapshot to somebody
outside the organisation. Until INV-C17 the product had only the first: a pack
was generated, and its PDF was re-rendered from the stored payload on every
download, so nothing recorded that a disclosure had happened, who received it,
or which bytes they were given.

Two rules follow from that, and this module owns both.

**DEC-4 — the gate.** An external pack may not be issued unless

* the investigation is complete, and
* a human has cleared the redaction review on that pack.

INV-C1 made the pack state the redaction it actually performed, and it says in
terms that redaction reaches recorded identity fields only — narrative text is
reproduced as written. So "was this safe to send?" is a judgement no rule in the
code can make, and the honest thing is to refuse to issue until somebody has
made it and said so. The review is never inferred and never created on the
caller's behalf: an unreviewed pack is refused with 422, not quietly reviewed.

Internal packs are deliberately not gated. An internal pack is the organisation
reading its own record, which is not a disclosure.

**DEC-5 — the retained bytes.** At the moment of issue the PDF is rendered
once, checksummed, and written to the existing evidence library as an
``EvidenceAsset`` linked to the investigation. The pack keeps the storage key,
the SHA-256 and the size, and every later download of that pack serves those
bytes. A renderer change afterwards therefore cannot rewrite what a customer
was given: the retained copy is what the download returns, and the disclosure
log names its checksum.

Both the storage key and the asset id are held on the pack on purpose. If the
asset row is ever removed the key still resolves, so a missing library row
cannot silently downgrade a retained pack back into a live re-render.
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import ValidationError
from src.domain.models.evidence_asset import (
    EvidenceAsset,
    EvidenceAssetType,
    EvidenceRetentionPolicy,
    EvidenceSourceModule,
    EvidenceVisibility,
)
from src.domain.models.investigation import (
    CustomerPackAudience,
    InvestigationCustomerPack,
    InvestigationPackDisclosure,
    InvestigationRun,
    InvestigationStatus,
)
from src.domain.services.investigation_pack_pdf import InvestigationPackPdfService
from src.infrastructure.storage import StorageError, storage_service

logger = logging.getLogger(__name__)

#: Reason codes returned to the client when an external issue is refused. Stable
#: strings so a caller can branch on them; the accompanying message is prose.
BLOCKER_NOT_COMPLETE = "INVESTIGATION_NOT_COMPLETE"
BLOCKER_REDACTION_REVIEW_NOT_CLEARED = "REDACTION_REVIEW_NOT_CLEARED"

#: Error code on the 422 an external issue is refused with.
PACK_ISSUE_BLOCKED = "PACK_ISSUE_BLOCKED"

#: Statuses that mean the investigation itself is finished. CLOSED is included
#: because a closed investigation has been through COMPLETED to get there.
_COMPLETE_STATUSES = frozenset({InvestigationStatus.COMPLETED.value, InvestigationStatus.CLOSED.value})

_BLOCKER_MESSAGES = {
    BLOCKER_NOT_COMPLETE: "the investigation is not complete",
    BLOCKER_REDACTION_REVIEW_NOT_CLEARED: "the redaction review has not been cleared",
}


class RetainedPackUnavailableError(Exception):
    """The retained bytes for an issued pack could not be served.

    Raised rather than falling back to a live re-render: quietly re-rendering
    would hand back a document that is not the one the disclosure log names,
    which is the failure DEC-5 exists to prevent.
    """

    def __init__(self, message: str, *, code: str) -> None:
        super().__init__(message)
        self.message = message
        self.code = code


def _enum_value(value: Any) -> str:
    """Read an enum-or-string column without assuming which it is."""
    if value is None:
        return ""
    return str(getattr(value, "value", value))


def is_external_pack(pack: InvestigationCustomerPack) -> bool:
    """True when this pack's audience is a customer outside the organisation."""
    return _enum_value(pack.audience) == CustomerPackAudience.EXTERNAL_CUSTOMER.value


def investigation_is_complete(investigation: InvestigationRun) -> bool:
    """True when the investigation has reached completion (INV-C8 closure).

    Fails closed: an absent or unrecognised status is not complete.
    """
    return _enum_value(investigation.status) in _COMPLETE_STATUSES


def redaction_review_is_cleared(pack: InvestigationCustomerPack) -> bool:
    """True when a human recorded a cleared redaction review on this pack."""
    return pack.redaction_review_cleared_at is not None


def external_issue_blockers(
    investigation: InvestigationRun,
    pack: InvestigationCustomerPack,
) -> list[str]:
    """Reason codes that stop this pack being issued externally, in report order.

    An empty list means issue is allowed. Internal packs are never blocked here
    — issuing internally is not a disclosure — so callers must still check
    :func:`is_external_pack` before deciding what an empty list means.
    """
    if not is_external_pack(pack):
        return []
    blockers: list[str] = []
    if not investigation_is_complete(investigation):
        blockers.append(BLOCKER_NOT_COMPLETE)
    if not redaction_review_is_cleared(pack):
        blockers.append(BLOCKER_REDACTION_REVIEW_NOT_CLEARED)
    return blockers


def assert_issuable(investigation: InvestigationRun, pack: InvestigationCustomerPack) -> None:
    """Raise a 422 naming every blocker, or return when the pack may be issued."""
    blockers = external_issue_blockers(investigation, pack)
    if not blockers:
        return
    reasons = " and ".join(_BLOCKER_MESSAGES[code] for code in blockers)
    raise ValidationError(
        f"This external pack cannot be issued because {reasons}.",
        code=PACK_ISSUE_BLOCKED,
        details={
            "blockers": blockers,
            "pack_id": pack.id,
            "investigation_id": pack.investigation_id,
        },
    )


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PackBranding:
    """Tenant branding applied to the rendered pack."""

    organisation_name: Optional[str] = None
    primary_color: Optional[str] = None


async def load_pack_branding(db: AsyncSession, tenant_id: Optional[int]) -> PackBranding:
    """Read the issuing tenant's name and colour, or plain branding if absent."""
    if tenant_id is None:
        return PackBranding()
    from src.domain.models.tenant import Tenant

    tenant = await db.scalar(select(Tenant).where(Tenant.id == tenant_id))
    if tenant is None:
        return PackBranding()
    return PackBranding(organisation_name=tenant.name, primary_color=tenant.primary_color)


def pack_render_payload(
    investigation: InvestigationRun,
    pack: InvestigationCustomerPack,
) -> dict[str, Any]:
    """The stored pack, in the shape the PDF renderer reads.

    Built here rather than at each call site so that the bytes retained at issue
    and the bytes a download would render are the same document by construction.
    Note what it does *not* do: it never re-reads the investigation's sections,
    so it cannot leak content the pack omitted.
    """
    return {
        "pack_uuid": pack.pack_uuid,
        "audience": _enum_value(pack.audience),
        "investigation_reference": investigation.reference_number,
        "investigation_title": investigation.title,
        "generated_at": pack.created_at.isoformat() if pack.created_at else None,
        "checksum_sha256": pack.checksum_sha256,
        "content": pack.content,
        "redaction_log": pack.redaction_log,
        "included_assets": pack.included_assets,
    }


def render_pack_pdf(payload: dict[str, Any], branding: PackBranding) -> bytes:
    """Render pack bytes. Raises ``RuntimeError`` when rendering is impossible."""
    service = InvestigationPackPdfService()
    return service.build_pdf_bytes(
        payload,
        organisation_name=branding.organisation_name,
        primary_color=branding.primary_color,
    )


# ---------------------------------------------------------------------------
# Retention
# ---------------------------------------------------------------------------


def retained_pdf_storage_key(investigation_id: int, pack_uuid: str) -> str:
    """Deterministic key for a pack's retained PDF.

    Deterministic on purpose: if a first attempt uploads the bytes and then the
    database commit fails, the retry writes the same key instead of leaving an
    orphan blob behind for every attempt.
    """
    return f"evidence/investigation/{investigation_id}/issued-packs/{pack_uuid}.pdf"


def has_retained_pdf(pack: InvestigationCustomerPack) -> bool:
    """True when this pack has issued bytes on record that can be served."""
    return bool(pack.issued_pdf_storage_key) and bool(pack.issued_pdf_sha256)


def pack_evidence_assets_query(*, investigation_id: int, tenant_id: int) -> Any:
    """Evidence a new pack may consider, minus packs retained by an earlier issue.

    A retained pack is linked to the investigation as an ``EvidenceAsset`` so it
    lives in the one library rather than a second blob store. It is a record of
    a disclosure, though, not evidence gathered during the investigation, so
    listing it back to the customer as an attachment on the next pack would be
    wrong. Excluded by id rather than by type, because a genuine PDF exhibit
    must still be offered.
    """
    retained = select(InvestigationCustomerPack.issued_pdf_asset_id).where(
        InvestigationCustomerPack.investigation_id == investigation_id,
        InvestigationCustomerPack.issued_pdf_asset_id.is_not(None),
    )
    return select(EvidenceAsset).where(
        EvidenceAsset.linked_investigation_id == investigation_id,
        EvidenceAsset.tenant_id == tenant_id,
        EvidenceAsset.deleted_at.is_(None),
        EvidenceAsset.id.not_in(retained),
    )


@dataclass(frozen=True)
class RetainedPdf:
    """Where an issued pack's bytes live, and whether this call wrote them."""

    storage_key: str
    sha256: str
    size_bytes: int
    asset_id: Optional[int]
    newly_retained: bool


async def retain_issued_pdf(
    db: AsyncSession,
    *,
    investigation: InvestigationRun,
    pack: InvestigationCustomerPack,
    tenant_id: int,
    actor_id: int,
) -> RetainedPdf:
    """Return the pack's retained bytes, writing them on the first issue only.

    A pack that already carries a storage key and a checksum is returned as-is
    without rendering anything. That is what stops a second disclosure — or a
    renderer that has changed since — replacing the record of what was
    originally issued.
    """
    if has_retained_pdf(pack):
        return RetainedPdf(
            storage_key=str(pack.issued_pdf_storage_key),
            sha256=str(pack.issued_pdf_sha256),
            size_bytes=int(pack.issued_pdf_size_bytes or 0),
            asset_id=pack.issued_pdf_asset_id,
            newly_retained=False,
        )

    branding = await load_pack_branding(db, tenant_id)
    pdf_bytes = render_pack_pdf(pack_render_payload(investigation, pack), branding)
    checksum = hashlib.sha256(pdf_bytes).hexdigest()
    storage_key = retained_pdf_storage_key(int(investigation.id), str(pack.pack_uuid))

    await storage_service().upload(
        storage_key=storage_key,
        content=pdf_bytes,
        content_type="application/pdf",
        metadata={
            "source_module": EvidenceSourceModule.INVESTIGATION.value,
            "source_id": str(investigation.id),
            "pack_uuid": str(pack.pack_uuid),
            "checksum_sha256": checksum,
        },
    )

    asset = EvidenceAsset(
        tenant_id=tenant_id,
        storage_key=storage_key,
        original_filename=InvestigationPackPdfService.pdf_filename(investigation.reference_number, pack.pack_uuid),
        content_type="application/pdf",
        file_size_bytes=len(pdf_bytes),
        checksum_sha256=checksum,
        asset_type=EvidenceAssetType.PDF,
        source_module=EvidenceSourceModule.INVESTIGATION,
        source_id=str(investigation.id),
        linked_investigation_id=int(investigation.id),
        title=f"Issued customer pack {pack.pack_uuid}",
        description="Retained copy of the pack as issued (INV-C17).",
        render_hint="link",
        # INTERNAL_ONLY is about what a *future* pack may carry, not about who
        # has already seen this one. The bytes went to a customer; the record of
        # that disclosure must never be swept into the next pack as evidence.
        visibility=EvidenceVisibility.INTERNAL_ONLY,
        # A pack reproduces narrative text as written (INV-C1), so it cannot be
        # asserted PII-free for either audience.
        contains_pii=True,
        redaction_required=False,
        retention_policy=EvidenceRetentionPolicy.STANDARD,
        created_by_id=actor_id,
        updated_by_id=actor_id,
    )
    db.add(asset)
    await db.flush()

    pack.issued_pdf_asset_id = asset.id
    pack.issued_pdf_storage_key = storage_key
    pack.issued_pdf_sha256 = checksum
    pack.issued_pdf_size_bytes = len(pdf_bytes)

    return RetainedPdf(
        storage_key=storage_key,
        sha256=checksum,
        size_bytes=len(pdf_bytes),
        asset_id=asset.id,
        newly_retained=True,
    )


async def read_retained_pdf(pack: InvestigationCustomerPack) -> bytes:
    """Fetch an issued pack's retained bytes and verify them against the record.

    Raises :class:`RetainedPackUnavailableError` when the bytes cannot be read,
    or when what came back does not hash to the checksum the disclosure log
    published. Serving unverified bytes under an issued pack's name would make
    the checksum a decoration.
    """
    storage_key = str(pack.issued_pdf_storage_key or "")
    expected = str(pack.issued_pdf_sha256 or "")
    if not storage_key or not expected:
        raise RetainedPackUnavailableError(
            "This pack is marked issued but carries no retained document.",
            code="RETAINED_PACK_MISSING",
        )
    try:
        content = await storage_service().download(storage_key)
    except StorageError as exc:
        raise RetainedPackUnavailableError(
            "The retained copy of this issued pack could not be read from storage.",
            code="RETAINED_PACK_UNREADABLE",
        ) from exc

    actual = hashlib.sha256(content).hexdigest()
    if actual != expected:
        logger.error(
            "investigation_pack_retained_checksum_mismatch",
            extra={
                "pack_id": pack.id,
                "investigation_id": pack.investigation_id,
                "expected_sha256": expected,
                "actual_sha256": actual,
            },
        )
        raise RetainedPackUnavailableError(
            "The retained copy of this issued pack does not match its recorded checksum.",
            code="RETAINED_PACK_CHECKSUM_MISMATCH",
        )
    return content


# ---------------------------------------------------------------------------
# Disclosure
# ---------------------------------------------------------------------------


def record_disclosure(
    db: AsyncSession,
    *,
    investigation: InvestigationRun,
    pack: InvestigationCustomerPack,
    tenant_id: int,
    actor_id: int,
    recipient: str,
    recipient_email: Optional[str],
    note: Optional[str],
    pdf_sha256: str,
    issued_at: datetime,
) -> InvestigationPackDisclosure:
    """Add one disclosure row. Fails closed on a missing tenant."""
    if tenant_id is None:
        raise ValidationError(
            "tenant_id is required to record a customer pack disclosure",
            details={"pack_id": pack.id},
        )
    disclosure = InvestigationPackDisclosure(
        tenant_id=int(tenant_id),
        investigation_id=int(investigation.id),
        pack_id=int(pack.id),
        recipient=recipient,
        recipient_email=recipient_email,
        issued_at=issued_at,
        pdf_sha256=pdf_sha256,
        actor_id=actor_id,
        note=note,
    )
    db.add(disclosure)
    return disclosure


def utc_now() -> datetime:
    """Timezone-aware now, isolated so tests can hold the clock still."""
    return datetime.now(timezone.utc)
