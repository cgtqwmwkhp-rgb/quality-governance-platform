"""Export Center sync CSV builders (PX-160).

Prefer synchronous streaming exports. Async ``export_jobs`` persistence is
owned by Lane S (alembic) and is intentionally not claimed here.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Sequence

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.exceptions import BadRequestError
from src.domain.models.audit import AuditRun
from src.domain.models.capa import CAPAAction
from src.domain.models.complaint import Complaint
from src.domain.models.document import Document
from src.domain.models.incident import Incident
from src.domain.models.risk import Risk
from src.domain.models.rta import RoadTrafficCollision

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
)

SUPPORTED_FORMATS = ("csv",)


@dataclass(frozen=True)
class _ModuleSpec:
    id: str
    name: str
    description: str
    model: Any
    columns: Sequence[str]
    row_mapper: Callable[[Any], list[str]]
    order_by: Any


def _enum_str(value: Any) -> str:
    if value is None:
        return ""
    return str(getattr(value, "value", value))


def _dt_str(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        return value.isoformat()
    return value.isoformat()


def _incident_row(row: Incident) -> list[str]:
    return [
        str(row.id),
        row.reference_number or "",
        row.title or "",
        _enum_str(row.incident_type),
        _enum_str(row.severity),
        _enum_str(row.status),
        _dt_str(row.incident_date),
        _dt_str(getattr(row, "created_at", None)),
    ]


def _rta_row(row: RoadTrafficCollision) -> list[str]:
    return [
        str(row.id),
        row.reference_number or "",
        row.title or "",
        _enum_str(row.severity),
        _enum_str(row.status),
        _dt_str(row.collision_date),
        row.location or "",
        _dt_str(getattr(row, "created_at", None)),
    ]


def _complaint_row(row: Complaint) -> list[str]:
    return [
        str(row.id),
        row.reference_number or "",
        row.title or "",
        _enum_str(getattr(row, "complaint_type", None)),
        _enum_str(getattr(row, "priority", None)),
        _enum_str(row.status),
        _dt_str(getattr(row, "created_at", None)),
    ]


def _risk_row(row: Risk) -> list[str]:
    return [
        str(row.id),
        row.reference_number or "",
        row.title or "",
        _enum_str(getattr(row, "risk_level", None)),
        _enum_str(row.status),
        _dt_str(getattr(row, "created_at", None)),
    ]


def _audit_row(row: AuditRun) -> list[str]:
    return [
        str(row.id),
        row.reference_number or "",
        row.title or "",
        _enum_str(row.status),
        str(row.template_id) if row.template_id is not None else "",
        _dt_str(getattr(row, "created_at", None)),
    ]


def _action_row(row: CAPAAction) -> list[str]:
    return [
        str(row.id),
        row.reference_number or "",
        row.title or "",
        _enum_str(row.status),
        _enum_str(getattr(row, "priority", None)),
        _enum_str(getattr(row, "capa_type", None)),
        _dt_str(getattr(row, "due_date", None)),
        _dt_str(getattr(row, "created_at", None)),
    ]


def _document_row(row: Document) -> list[str]:
    return [
        str(row.id),
        row.reference_number or "",
        row.title or "",
        _enum_str(row.status),
        row.file_name or "",
        _dt_str(getattr(row, "created_at", None)),
    ]


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
        name="Documents",
        description="Document library metadata (CSV sync)",
        model=Document,
        columns=[
            "id",
            "reference_number",
            "title",
            "status",
            "file_name",
            "created_at",
        ],
        row_mapper=_document_row,
        order_by=Document.id.desc(),
    ),
}


@dataclass(frozen=True)
class SyncExportResult:
    """In-memory sync CSV payload (streamed by the route layer)."""

    module: str
    filename: str
    csv_text: str
    row_count: int
    truncated: bool
    total_available: int


class ExportCenterService:
    """Tenant-scoped catalog + sync CSV generation for Export Center."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_catalog(self, tenant_id: int) -> dict[str, Any]:
        modules: list[dict[str, Any]] = []
        for module_id in SUPPORTED_MODULES:
            spec = _MODULE_SPECS[module_id]
            count = await self._count(spec.model, tenant_id)
            modules.append(
                {
                    "id": spec.id,
                    "name": spec.name,
                    "description": spec.description,
                    "record_count": count,
                    "formats": ["csv"],
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

    async def build_sync_csv(self, tenant_id: int, module: str, export_format: str = "csv") -> SyncExportResult:
        module_key = (module or "").strip().lower()
        fmt = (export_format or "").strip().lower()
        if module_key not in _MODULE_SPECS:
            raise BadRequestError(
                f"Unsupported export module '{module}'. "
                f"Supported: {', '.join(SUPPORTED_MODULES)}."
            )
        if fmt not in SUPPORTED_FORMATS:
            raise BadRequestError(
                f"Unsupported export format '{export_format}'. Sync exports support csv only this wave."
            )

        spec = _MODULE_SPECS[module_key]
        total = await self._count(spec.model, tenant_id)
        stmt: Select[Any] = (
            select(spec.model)
            .where(spec.model.tenant_id == tenant_id)
            .order_by(spec.order_by)
            .limit(SYNC_ROW_LIMIT)
        )
        result = await self._db.execute(stmt)
        rows = list(result.scalars().all())

        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(list(spec.columns))
        for row in rows:
            writer.writerow(spec.row_mapper(row))

        truncated = total > len(rows)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
        filename = f"{module_key}_export_{stamp}.csv"
        return SyncExportResult(
            module=module_key,
            filename=filename,
            csv_text=buffer.getvalue(),
            row_count=len(rows),
            truncated=truncated,
            total_available=total,
        )

    async def _count(self, model: Any, tenant_id: int) -> int:
        stmt = select(func.count()).select_from(model).where(model.tenant_id == tenant_id)
        result = await self._db.execute(stmt)
        return int(result.scalar_one() or 0)
