"""Export Center sync builders (PX-160) + IMS052 document register (WA-3 / L-07).

Prefer synchronous streaming exports. Async ``export_jobs`` persistence is
owned by Lane S (alembic) and is intentionally not claimed here.

The ``documents`` module is the Master Document Register evidence pack —
fixed IMS052 columns, never driven by a UI column picker. Other modules keep
their generic CSV row mappers.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, Optional, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import BadRequestError
from src.domain.models.audit import AuditRun
from src.domain.models.capa import CAPAAction
from src.domain.models.complaint import Complaint
from src.domain.models.compliance_schedule import ComplianceRequirement
from src.domain.models.document import Document
from src.domain.models.incident import Incident
from src.domain.models.risk import Risk
from src.domain.models.rta import RoadTrafficCollision
from src.domain.services.document_register_export import (
    IMS052_FILENAME_STEM,
    build_document_register_rows,
    serialize_register,
)

# Hard cap for sync responses — keep request-scoped memory bounded.
SYNC_ROW_LIMIT = 10_000

SUPPORTED_MODULES = (
    "incidents",
    "rtas",
    "complaints",
    "risks",
    "audits",
    "actions",
    "documents",
    "compliance_schedule",
)

SUPPORTED_FORMATS = ("csv", "xlsx", "pdf")


@dataclass(frozen=True)
class _ModuleSpec:
    id: str
    name: str
    description: str
    model: Any
    columns: Sequence[str]
    row_mapper: Callable[[Any], list[str]]
    order_by: Any
    formats: tuple[str, ...] = ("csv",)
    filename_stem: Optional[str] = None
    # When set, replaces the generic select+row_mapper path (documents / IMS052).
    rows_builder: Optional[Callable[..., Awaitable[tuple[list[list[str]], int, bool]]]] = None
    active_only: bool = False


def _enum_str(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value))


def _s(value: object | None) -> str:
    """Coerce ORM/column-ish values to plain str for CSV cells."""
    if value is None:
        return ""
    return str(value)


def _dt_str(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        return value.isoformat()
    return value.isoformat()


def _incident_row(row: Incident) -> list[str]:
    return [
        str(row.id),
        _s(row.reference_number),
        _s(row.title),
        _enum_str(row.incident_type),
        _enum_str(row.severity),
        _enum_str(row.status),
        _dt_str(row.incident_date),
        _dt_str(getattr(row, "created_at", None)),
    ]


def _rta_row(row: RoadTrafficCollision) -> list[str]:
    return [
        str(row.id),
        _s(row.reference_number),
        _s(row.title),
        _enum_str(row.severity),
        _enum_str(row.status),
        _dt_str(row.collision_date),
        row.location or "",
        _dt_str(getattr(row, "created_at", None)),
    ]


def _complaint_row(row: Complaint) -> list[str]:
    return [
        str(row.id),
        _s(row.reference_number),
        _s(row.title),
        _enum_str(getattr(row, "complaint_type", None)),
        _enum_str(getattr(row, "priority", None)),
        _enum_str(row.status),
        _enum_str(getattr(row, "feedback_kind", None)),
        _dt_str(getattr(row, "created_at", None)),
    ]


def _risk_row(row: Risk) -> list[str]:
    return [
        str(row.id),
        _s(row.reference_number),
        _s(row.title),
        _enum_str(getattr(row, "risk_level", None)),
        _enum_str(row.status),
        _dt_str(getattr(row, "created_at", None)),
    ]


def _audit_row(row: AuditRun) -> list[str]:
    return [
        str(row.id),
        _s(row.reference_number),
        _s(row.title),
        _enum_str(row.status),
        str(row.template_id) if row.template_id is not None else "",
        _dt_str(getattr(row, "created_at", None)),
    ]


def _action_row(row: CAPAAction) -> list[str]:
    return [
        str(row.id),
        _s(row.reference_number),
        _s(row.title),
        _enum_str(row.status),
        _enum_str(getattr(row, "priority", None)),
        _enum_str(getattr(row, "capa_type", None)),
        _dt_str(getattr(row, "due_date", None)),
        _dt_str(getattr(row, "created_at", None)),
    ]


def _document_row(row: Document) -> list[str]:
    # Retained for type completeness; documents use rows_builder (IMS052).
    return [
        str(row.id),
        _s(row.reference_number),
        _s(row.title),
        _enum_str(row.status),
        _s(row.file_name),
        _dt_str(getattr(row, "created_at", None)),
    ]


def _compliance_schedule_row(row: ComplianceRequirement) -> list[str]:
    return [
        str(row.id),
        _s(row.reference_number),
        _s(row.title),
        _s(row.next_due_date),
        _s(row.owner_id),
        _s(row.is_active),
        _s(row.statutory),
    ]


async def _build_document_register(
    db: AsyncSession,
    tenant_id: int,
    *,
    user: Any,
) -> tuple[list[list[str]], int, bool]:
    return await build_document_register_rows(db, tenant_id, user=user, row_limit=SYNC_ROW_LIMIT)


_MODULE_SPECS: dict[str, _ModuleSpec] = {
    "incidents": _ModuleSpec(
        id="incidents",
        name="Incidents",
        description="Tenant incident register (CSV sync)",
        model=Incident,
        columns=[
            "id",
            "reference_number",
            "title",
            "incident_type",
            "severity",
            "status",
            "incident_date",
            "created_at",
        ],
        row_mapper=_incident_row,
        order_by=Incident.id.desc(),
    ),
    "rtas": _ModuleSpec(
        id="rtas",
        name="Road Traffic Collisions",
        description="Tenant RTC / RTA register (CSV sync)",
        model=RoadTrafficCollision,
        columns=[
            "id",
            "reference_number",
            "title",
            "severity",
            "status",
            "collision_date",
            "location",
            "created_at",
        ],
        row_mapper=_rta_row,
        order_by=RoadTrafficCollision.id.desc(),
    ),
    "complaints": _ModuleSpec(
        id="complaints",
        name="Complaints",
        description="Tenant complaints register (CSV sync)",
        model=Complaint,
        columns=[
            "id",
            "reference_number",
            "title",
            "complaint_type",
            "priority",
            "status",
            "feedback_kind",
            "created_at",
        ],
        row_mapper=_complaint_row,
        order_by=Complaint.id.desc(),
    ),
    "risks": _ModuleSpec(
        id="risks",
        name="Risks",
        description="Operational risk register (CSV sync)",
        model=Risk,
        columns=[
            "id",
            "reference_number",
            "title",
            "risk_level",
            "status",
            "created_at",
        ],
        row_mapper=_risk_row,
        order_by=Risk.id.desc(),
    ),
    "audits": _ModuleSpec(
        id="audits",
        name="Audits",
        description="Audit runs (CSV sync)",
        model=AuditRun,
        columns=[
            "id",
            "reference_number",
            "title",
            "status",
            "template_id",
            "created_at",
        ],
        row_mapper=_audit_row,
        order_by=AuditRun.id.desc(),
    ),
    "actions": _ModuleSpec(
        id="actions",
        name="Actions (CAPA)",
        description="CAPA corrective / preventive actions (CSV sync)",
        model=CAPAAction,
        columns=[
            "id",
            "reference_number",
            "title",
            "status",
            "priority",
            "capa_type",
            "due_date",
            "created_at",
        ],
        row_mapper=_action_row,
        order_by=CAPAAction.id.desc(),
    ),
    "documents": _ModuleSpec(
        id="documents",
        name="Documents (IMS052 Register)",
        description=(
            "Master Document Register evidence pack (IMS052). "
            "Fixed columns — UI column picker is ignored. CSV / XLSX / PDF."
        ),
        model=Document,
        columns=[],  # fixed IMS052 header owned by document_register_export
        row_mapper=_document_row,
        order_by=Document.id.desc(),
        formats=("csv", "xlsx", "pdf"),
        filename_stem=IMS052_FILENAME_STEM,
        rows_builder=_build_document_register,
        active_only=True,
    ),
    "compliance_schedule": _ModuleSpec(
        id="compliance_schedule",
        name="Compliance Schedule",
        description="Tenant compliance requirements register (CSV sync)",
        model=ComplianceRequirement,
        columns=[
            "id",
            "reference_number",
            "title",
            "next_due_date",
            "owner",
            "is_active",
            "statutory",
        ],
        row_mapper=_compliance_schedule_row,
        order_by=ComplianceRequirement.id.desc(),
    ),
}


@dataclass(frozen=True)
class SyncExportResult:
    """In-memory sync export payload (streamed by the route layer)."""

    module: str
    filename: str
    content: bytes
    media_type: str
    row_count: int
    truncated: bool
    total_available: int

    @property
    def csv_text(self) -> str:
        """Backward-compatible view for CSV payloads (tests / callers)."""
        if not self.media_type.startswith("text/csv"):
            raise TypeError("csv_text is only available for CSV exports")
        return self.content.decode("utf-8")


class ExportCenterService:
    """Tenant-scoped catalog + sync export generation for Export Center."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_catalog(self, tenant_id: int) -> dict[str, Any]:
        modules: list[dict[str, Any]] = []
        for module_id in SUPPORTED_MODULES:
            spec = _MODULE_SPECS[module_id]
            count = await self._count(spec, tenant_id)
            modules.append(
                {
                    "id": spec.id,
                    "name": spec.name,
                    "description": spec.description,
                    "record_count": count,
                    "formats": list(spec.formats),
                    "sync_available": True,
                }
            )
        return {
            "modules": modules,
            "capabilities": {
                "sync_csv": True,
                "job_history": False,
                "scheduled_templates": False,
                "max_sync_rows": SYNC_ROW_LIMIT,
            },
        }

    async def build_sync_csv(
        self,
        tenant_id: int,
        module: str,
        export_format: str = "csv",
        *,
        user: Any = None,
    ) -> SyncExportResult:
        """Build a sync export. Name retained for route compatibility; formats vary."""
        module_key = (module or "").strip().lower()
        fmt = (export_format or "").strip().lower()
        if module_key not in _MODULE_SPECS:
            raise BadRequestError(
                f"Unsupported export module '{module}'. " f"Supported: {', '.join(SUPPORTED_MODULES)}."
            )
        spec = _MODULE_SPECS[module_key]
        if fmt not in spec.formats:
            raise BadRequestError(
                f"Unsupported export format '{export_format}' for module '{module_key}'. "
                f"Supported: {', '.join(spec.formats)}."
            )

        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        stem = spec.filename_stem or f"{module_key}_export"

        if spec.rows_builder is not None:
            if user is None:
                raise BadRequestError("Document register export requires an authenticated user for ACL narrowing.")
            data_rows, total_visible, truncated = await spec.rows_builder(self._db, tenant_id, user=user)
            try:
                content, media_type, extension = serialize_register(data_rows, fmt)
            except ValueError as exc:
                raise BadRequestError(str(exc)) from exc
            return SyncExportResult(
                module=module_key,
                filename=f"{stem}_{stamp}.{extension}",
                content=content,
                media_type=media_type,
                row_count=len(data_rows),
                truncated=truncated,
                total_available=total_visible,
            )

        if fmt != "csv":
            raise BadRequestError(
                f"Unsupported export format '{export_format}' for module '{module_key}'. "
                f"Supported: {', '.join(spec.formats)}."
            )

        total = await self._count(spec, tenant_id)
        stmt: Select[Any] = (
            select(spec.model).where(spec.model.tenant_id == tenant_id).order_by(spec.order_by).limit(SYNC_ROW_LIMIT)
        )
        if spec.active_only and hasattr(spec.model, "is_active"):
            stmt = stmt.where(spec.model.is_active.is_(True))
        result = await self._db.execute(stmt)
        rows = list(result.scalars().all())

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(list(spec.columns))
        for row in rows:
            writer.writerow(spec.row_mapper(row))

        truncated = total > len(rows)
        return SyncExportResult(
            module=module_key,
            filename=f"{stem}_{stamp}.csv",
            content=buffer.getvalue().encode("utf-8"),
            media_type="text/csv; charset=utf-8",
            row_count=len(rows),
            truncated=truncated,
            total_available=total,
        )

    async def _count(self, spec: _ModuleSpec, tenant_id: int) -> int:
        model = spec.model
        stmt = select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
        if spec.active_only and hasattr(model, "is_active"):
            stmt = stmt.where(model.is_active.is_(True))
        result = await self._db.execute(stmt)
        return int(result.scalar_one() or 0)
