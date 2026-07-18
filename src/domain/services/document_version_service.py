"""Document version control — create → revise → publish with immutability.

ISO 9001:2015 §7.5-aligned conventions:
- Draft versions are editable; published/superseded versions are immutable.
- Create starts at 1.0 draft (matches document.current_version — no theatre).
- Publish freezes the working draft and supersedes any prior published tip.
- Revise after publish opens a new draft tip; prior published remains read-only.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import BadRequestError, NotFoundError
from src.domain.models.document import Document, DocumentVersion
from src.domain.models.document_control import ControlledDocument, ControlledDocumentVersion

IMMUTABLE_VERSION_STATUSES = frozenset(
    {
        "published",
        "superseded",
        "approved",
        "effective",
        "active",
        "obsolete",
    }
)


@dataclass(frozen=True)
class VersionNumber:
    major: int
    minor: int

    @property
    def label(self) -> str:
        return f"{self.major}.{self.minor}"


_FILENAME_VERSION_HINT = re.compile(
    r"[_\-\s]v(?P<major>\d+)\.(?P<minor>\d+)(?:[_\-\s\.]|$)",
    re.IGNORECASE,
)


def parse_filename_version_hint(filename: str | None) -> VersionNumber | None:
    """Advisory version hint from filename (e.g. ``Policy_v2.1.pdf``). Does not mutate state."""
    if not filename:
        return None
    match = _FILENAME_VERSION_HINT.search(filename)
    if not match:
        return None
    try:
        major = int(match.group("major"))
        minor = int(match.group("minor"))
        if major < 1 or minor < 0:
            return None
        return VersionNumber(major=major, minor=minor)
    except (TypeError, ValueError):
        return None


def parse_version(value: str | None) -> VersionNumber:
    """Parse major.minor; invalid/missing values fall back to 1.0."""
    raw = (value or "1.0").strip()
    try:
        parts = raw.split(".")
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        if major < 0 or minor < 0:
            raise ValueError
        return VersionNumber(major=major or 1, minor=minor)
    except (TypeError, ValueError, IndexError):
        return VersionNumber(major=1, minor=0)


def next_version(current: VersionNumber, *, is_major: bool) -> VersionNumber:
    if is_major:
        return VersionNumber(major=current.major + 1, minor=0)
    return VersionNumber(major=current.major, minor=current.minor + 1)


def version_is_immutable(status: str | None, is_immutable: bool | None = None) -> bool:
    if is_immutable is True:
        return True
    return (status or "").lower() in IMMUTABLE_VERSION_STATUSES


def assert_version_mutable(status: str | None, is_immutable: bool | None = None) -> None:
    if version_is_immutable(status, is_immutable):
        raise BadRequestError(
            "Published and superseded versions are immutable (read-only). " "Create a revision draft, then publish."
        )


def assert_document_metadata_editable(status: str | None) -> None:
    normalized = (status or "").lower()
    if normalized in {"published", "active", "effective", "obsolete", "retired", "archived"}:
        raise BadRequestError(f"Document status '{normalized}' is read-only. Revise to open a draft before editing.")


LIBRARY_IMMUTABLE_METADATA_STATUSES = frozenset(
    {"published", "approved", "active", "superseded", "retired", "obsolete", "archived"}
)


def assert_library_metadata_editable(status: object | None) -> None:
    """Title/description edits on draft/working rows must not force a version bump."""
    raw = getattr(status, "value", status)
    normalized = str(raw or "").lower()
    if normalized in LIBRARY_IMMUTABLE_METADATA_STATUSES:
        raise BadRequestError(
            f"Document status '{normalized}' is read-only. Revise to open a draft before editing metadata."
        )


class DocumentVersionService:
    """Library + controlled document version lifecycle."""

    # ------------------------------------------------------------------
    # Controlled documents
    # ------------------------------------------------------------------

    @staticmethod
    def build_initial_controlled_version(
        *,
        tenant_id: int,
        document_id: int,
        author_name: str | None,
        created_by_id: int | None = None,
    ) -> ControlledDocumentVersion:
        """Honest create: document tip and version row both start at 1.0 draft."""
        return ControlledDocumentVersion(
            tenant_id=tenant_id,
            document_id=document_id,
            version_number="1.0",
            major_version=1,
            minor_version=0,
            change_summary="Initial document creation",
            change_type="new",
            status="draft",
            is_immutable=False,
            created_by_id=created_by_id,
            created_by_name=author_name,
        )

    async def revise_controlled(
        self,
        db: AsyncSession,
        document: ControlledDocument,
        *,
        tenant_id: int,
        change_summary: str,
        change_reason: str | None = None,
        change_type: str = "revision",
        is_major_version: bool = False,
        created_by_id: int | None = None,
        created_by_name: str | None = None,
    ) -> ControlledDocumentVersion:
        """Open a new draft tip. Prior published/superseded rows stay immutable."""
        open_draft = await db.scalar(
            select(ControlledDocumentVersion)
            .where(
                ControlledDocumentVersion.document_id == document.id,
                ControlledDocumentVersion.tenant_id == tenant_id,
                ControlledDocumentVersion.status == "draft",
                ControlledDocumentVersion.is_immutable.is_(False),
            )
            .order_by(ControlledDocumentVersion.created_at.desc())
            .limit(1)
        )
        if open_draft is not None:
            has_published = await db.scalar(
                select(ControlledDocumentVersion.id)
                .where(
                    ControlledDocumentVersion.document_id == document.id,
                    ControlledDocumentVersion.tenant_id == tenant_id,
                    ControlledDocumentVersion.status.in_(("published", "approved", "effective", "active")),
                )
                .limit(1)
            )
            if has_published is not None:
                raise BadRequestError(
                    f"Draft version {open_draft.version_number} is already open. "
                    "Publish or discard it before revising again."
                )
            # Pre-publish revise: bump the working draft tip in place (create→revise→publish)
            tip = parse_version(open_draft.version_number)
            nxt = next_version(tip, is_major=is_major_version)
            open_draft.version_number = nxt.label
            open_draft.major_version = nxt.major
            open_draft.minor_version = nxt.minor
            open_draft.change_summary = change_summary
            open_draft.change_reason = change_reason
            open_draft.change_type = change_type
            open_draft.created_by_id = created_by_id or open_draft.created_by_id
            open_draft.created_by_name = created_by_name or open_draft.created_by_name
            document.current_version = nxt.label
            document.major_version = nxt.major
            document.minor_version = nxt.minor
            document.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.flush()
            return open_draft

        tip = parse_version(document.current_version)
        nxt = next_version(tip, is_major=is_major_version)

        document.current_version = nxt.label
        document.major_version = nxt.major
        document.minor_version = nxt.minor
        if (document.status or "").lower() in {
            "published",
            "approved",
            "active",
            "effective",
        }:
            document.status = "under_revision"
        elif not document.status:
            document.status = "draft"
        document.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

        version = ControlledDocumentVersion(
            tenant_id=tenant_id,
            document_id=document.id,
            version_number=nxt.label,
            major_version=nxt.major,
            minor_version=nxt.minor,
            change_summary=change_summary,
            change_reason=change_reason,
            change_type=change_type,
            status="draft",
            is_immutable=False,
            created_by_id=created_by_id,
            created_by_name=created_by_name,
            file_name=document.file_name,
            file_path=document.file_path,
            file_size=document.file_size,
            checksum=document.checksum,
        )
        db.add(version)
        await db.flush()
        return version

    async def publish_controlled(
        self,
        db: AsyncSession,
        document: ControlledDocument,
        *,
        tenant_id: int,
        published_by_id: int | None = None,
        published_by_name: str | None = None,
        version_id: int | None = None,
    ) -> ControlledDocumentVersion:
        """Publish working draft; supersede prior published tip (immutable)."""
        if version_id is not None:
            version = await db.scalar(
                select(ControlledDocumentVersion).where(
                    ControlledDocumentVersion.id == version_id,
                    ControlledDocumentVersion.document_id == document.id,
                    ControlledDocumentVersion.tenant_id == tenant_id,
                )
            )
        else:
            version = await db.scalar(
                select(ControlledDocumentVersion)
                .where(
                    ControlledDocumentVersion.document_id == document.id,
                    ControlledDocumentVersion.tenant_id == tenant_id,
                    ControlledDocumentVersion.status == "draft",
                    ControlledDocumentVersion.is_immutable.is_(False),
                )
                .order_by(ControlledDocumentVersion.created_at.desc())
                .limit(1)
            )

        if version is None:
            raise BadRequestError("No draft version available to publish")

        assert_version_mutable(version.status, getattr(version, "is_immutable", False))

        prior_published = (
            (
                await db.execute(
                    select(ControlledDocumentVersion).where(
                        ControlledDocumentVersion.document_id == document.id,
                        ControlledDocumentVersion.tenant_id == tenant_id,
                        ControlledDocumentVersion.status.in_(("published", "approved", "effective", "active")),
                        ControlledDocumentVersion.id != version.id,
                    )
                )
            )
            .scalars()
            .all()
        )

        now = datetime.now(timezone.utc).replace(tzinfo=None)
        for prior in prior_published:
            prior.status = "superseded"
            prior.is_immutable = True

        version.status = "published"
        version.is_immutable = True
        version.approved_by_id = published_by_id
        version.approved_by_name = published_by_name
        version.approved_date = now
        version.effective_date = now

        document.current_version = version.version_number
        document.major_version = version.major_version
        document.minor_version = version.minor_version
        document.status = "published"
        document.approver_id = published_by_id
        document.approver_name = published_by_name
        document.approved_date = now
        document.effective_date = now
        document.updated_at = now

        await db.flush()
        return version

    # ------------------------------------------------------------------
    # Library documents
    # ------------------------------------------------------------------

    @staticmethod
    def build_initial_library_version(
        document: Document,
        *,
        created_by_id: int | None = None,
        change_notes: str = "Initial upload",
    ) -> DocumentVersion:
        return DocumentVersion(
            tenant_id=document.tenant_id,
            document_id=document.id,
            version_number=document.version or "1.0",
            change_notes=change_notes,
            change_type="new",
            file_name=document.file_name,
            file_path=document.file_path,
            file_size=document.file_size,
            created_by_id=created_by_id,
            status="draft",
            is_immutable=False,
        )

    async def list_library_versions(
        self,
        db: AsyncSession,
        document_id: int,
        *,
        tenant_id: int | None,
        is_superuser: bool = False,
    ) -> list[DocumentVersion]:
        stmt = select(DocumentVersion).where(DocumentVersion.document_id == document_id)
        if not is_superuser:
            if tenant_id is None:
                raise BadRequestError("Tenant context required")
            stmt = stmt.where(DocumentVersion.tenant_id == tenant_id)
        result = await db.execute(stmt.order_by(DocumentVersion.created_at.desc()))
        return list(result.scalars().all())

    async def revise_library(
        self,
        db: AsyncSession,
        document: Document,
        *,
        change_notes: str,
        change_type: str = "revision",
        is_major_version: bool = False,
        file_name: str | None = None,
        file_path: str | None = None,
        file_size: int | None = None,
        created_by_id: int | None = None,
    ) -> DocumentVersion:
        open_draft = await db.scalar(
            select(DocumentVersion)
            .where(
                DocumentVersion.document_id == document.id,
                DocumentVersion.tenant_id == document.tenant_id,
                DocumentVersion.status == "draft",
                DocumentVersion.is_immutable.is_(False),
            )
            .order_by(DocumentVersion.created_at.desc())
            .limit(1)
        )
        if open_draft is not None:
            has_published = await db.scalar(
                select(DocumentVersion.id)
                .where(
                    DocumentVersion.document_id == document.id,
                    DocumentVersion.tenant_id == document.tenant_id,
                    DocumentVersion.status == "published",
                )
                .limit(1)
            )
            if has_published is not None:
                raise BadRequestError(
                    f"Draft version {open_draft.version_number} is already open. "
                    "Publish it before creating another revision."
                )
            tip = parse_version(open_draft.version_number)
            nxt = next_version(tip, is_major=is_major_version)
            open_draft.version_number = nxt.label
            open_draft.change_notes = change_notes
            open_draft.change_type = change_type
            if file_name:
                open_draft.file_name = file_name
                document.file_name = file_name
            if file_path:
                open_draft.file_path = file_path
                document.file_path = file_path
            if file_size is not None:
                open_draft.file_size = file_size
                document.file_size = file_size
            document.version = nxt.label
            await db.flush()
            return open_draft

        tip = parse_version(document.version)
        nxt = next_version(tip, is_major=is_major_version)

        document.version = nxt.label
        if document.status and str(document.status.value if hasattr(document.status, "value") else document.status) in {
            "published",
            "approved",
            "indexed",
            "active",
        }:
            from src.domain.models.enums import DocumentStatus

            document.status = DocumentStatus.UNDER_REVISION

        version = DocumentVersion(
            tenant_id=document.tenant_id,
            document_id=document.id,
            version_number=nxt.label,
            change_notes=change_notes,
            change_type=change_type,
            file_name=file_name or document.file_name,
            file_path=file_path or document.file_path,
            file_size=file_size if file_size is not None else document.file_size,
            created_by_id=created_by_id,
            status="draft",
            is_immutable=False,
        )
        if file_name:
            document.file_name = file_name
        if file_path:
            document.file_path = file_path
        if file_size is not None:
            document.file_size = file_size

        db.add(version)
        await db.flush()
        return version

    async def publish_library(
        self,
        db: AsyncSession,
        document: Document,
        *,
        published_by_id: int | None = None,
        version_id: int | None = None,
    ) -> DocumentVersion:
        if version_id is not None:
            version = await db.scalar(
                select(DocumentVersion).where(
                    DocumentVersion.id == version_id,
                    DocumentVersion.document_id == document.id,
                    DocumentVersion.tenant_id == document.tenant_id,
                )
            )
        else:
            version = await db.scalar(
                select(DocumentVersion)
                .where(
                    DocumentVersion.document_id == document.id,
                    DocumentVersion.tenant_id == document.tenant_id,
                    DocumentVersion.status == "draft",
                    DocumentVersion.is_immutable.is_(False),
                )
                .order_by(DocumentVersion.created_at.desc())
                .limit(1)
            )

        if version is None:
            raise NotFoundError("No draft version available to publish")

        assert_version_mutable(version.status, version.is_immutable)

        prior_published = (
            (
                await db.execute(
                    select(DocumentVersion).where(
                        DocumentVersion.document_id == document.id,
                        DocumentVersion.tenant_id == document.tenant_id,
                        DocumentVersion.status == "published",
                        DocumentVersion.id != version.id,
                    )
                )
            )
            .scalars()
            .all()
        )

        now = datetime.now(timezone.utc)
        for prior in prior_published:
            prior.status = "superseded"
            prior.is_immutable = True

        version.status = "published"
        version.is_immutable = True
        version.published_at = now
        version.published_by_id = published_by_id

        document.version = version.version_number
        document.file_name = version.file_name
        document.file_path = version.file_path
        document.file_size = version.file_size
        from src.domain.models.enums import DocumentStatus

        document.status = DocumentStatus.PUBLISHED

        await db.flush()
        return version

    @staticmethod
    def serialize_library_version(version: DocumentVersion) -> dict:
        hint = parse_filename_version_hint(version.file_name)
        return {
            "id": version.id,
            "version_number": version.version_number,
            "change_notes": version.change_notes,
            "change_type": getattr(version, "change_type", None) or "revision",
            "status": version.status,
            "is_immutable": bool(version.is_immutable),
            "file_name": version.file_name,
            "file_size": version.file_size,
            "filename_version_hint": hint.label if hint else None,
            "created_by_id": version.created_by_id,
            "created_at": version.created_at.isoformat() if version.created_at else None,
            "published_at": version.published_at.isoformat() if version.published_at else None,
            "published_by_id": version.published_by_id,
            "read_only": version_is_immutable(version.status, version.is_immutable),
        }

    @staticmethod
    def serialize_controlled_version(version: ControlledDocumentVersion) -> dict:
        immutable = version_is_immutable(version.status, getattr(version, "is_immutable", False))
        return {
            "id": version.id,
            "version_number": version.version_number,
            "change_summary": version.change_summary,
            "change_type": version.change_type,
            "status": version.status,
            "is_immutable": immutable,
            "read_only": immutable,
            "created_by_name": version.created_by_name,
            "created_at": version.created_at.isoformat() if version.created_at else None,
            "approved_by_name": version.approved_by_name,
            "approved_date": version.approved_date.isoformat() if version.approved_date else None,
            "effective_date": version.effective_date.isoformat() if version.effective_date else None,
        }


document_version_service = DocumentVersionService()
