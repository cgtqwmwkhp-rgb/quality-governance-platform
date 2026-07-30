"""Pydantic schemas for Export Center sync APIs (PX-160)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ExportModuleId = Literal[
    "incidents",
    "rtas",
    "complaints",
    "risks",
    "audits",
    "actions",
    "documents",
]

ExportFormat = Literal["csv"]


class ExportCapabilities(BaseModel):
    """Honest capability disclosure — sync CSV now; job store deferred to Lane S."""

    sync_csv: bool = True
    job_history: bool = False
    scheduled_templates: bool = False
    max_sync_rows: int


def _default_csv_formats() -> list[ExportFormat]:
    return ["csv"]


class ExportModuleCatalogItem(BaseModel):
    """One exportable module with a live tenant-scoped row count."""

    id: ExportModuleId
    name: str
    description: str
    record_count: int = Field(ge=0)
    formats: list[ExportFormat] = Field(default_factory=_default_csv_formats)
    sync_available: bool = True


class ExportCatalogResponse(BaseModel):
    """Catalog returned by GET /exports/catalog."""

    modules: list[ExportModuleCatalogItem]
    capabilities: ExportCapabilities


class CreateExportRequest(BaseModel):
    """POST /exports body — sync stream only this wave (no async job create).

    ``extra="forbid"`` so a misspelled or unsupported field fails loudly instead
    of the export proceeding while the unknown key is silently dropped (B-10).
    """

    model_config = ConfigDict(extra="forbid")

    module: ExportModuleId
    format: ExportFormat = "csv"
