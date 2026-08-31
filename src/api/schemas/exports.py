"""Pydantic schemas for Export Center sync APIs (PX-160 + WA-3 IMS052)."""

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
    "compliance_schedule",
]

ExportFormat = Literal["csv", "xlsx", "pdf"]


class ExportCapabilities(BaseModel):
    """Honest capability disclosure — sync formats now; job store deferred to Lane S."""

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

    Column pickers are forbidden: documents always emit the fixed IMS052 header
    (WA-3 / L-07). Passing ``columns`` / ``fields`` / ``visible_columns`` is a 422.
    """

    model_config = ConfigDict(extra="forbid")

    module: ExportModuleId
    format: ExportFormat = "csv"
    register: str | None = Field(
        default=None,
        max_length=32,
        pattern=r"^PEL-[A-Z]{2,6}-\d{4}$",
        description=(
            "Optional PEL register reference to tag the filename with (REG-SSOT-E1). "
            "Only registers whose own scope is this module are accepted; the rows are "
            "still the whole module, never a per-register dump."
        ),
    )
