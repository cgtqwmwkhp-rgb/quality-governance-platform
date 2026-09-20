"""Request/response contracts for the investigation RCA workspace (INV-C10).

A separate module from ``rca_tools.py`` so the investigation-scoped surface can
be read in one place. The generic ``/rca-tools/five-whys`` routes stay as they
are; this is the workspace document the detail page edits.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.domain.services.investigation_rca_service import RCA_TEXT_MAX_LENGTH


class InvestigationRcaWhy(BaseModel):
    """One Why step as the workspace renders it."""

    model_config = ConfigDict(extra="forbid")

    level: int = Field(..., ge=1, le=20)
    why: str = ""
    answer: str = Field("", max_length=RCA_TEXT_MAX_LENGTH)
    evidence: str = Field("", max_length=RCA_TEXT_MAX_LENGTH)


class InvestigationRcaWhyInput(BaseModel):
    """One Why step on save. Empty answer and evidence are honest empty, not 400."""

    model_config = ConfigDict(extra="forbid")

    level: int = Field(..., ge=1, le=20)
    answer: str = Field("", max_length=RCA_TEXT_MAX_LENGTH)
    evidence: Optional[str] = Field(None, max_length=RCA_TEXT_MAX_LENGTH)
    why: Optional[str] = Field(None, max_length=RCA_TEXT_MAX_LENGTH)


class InvestigationRcaUpsert(BaseModel):
    """Replace the run's workspace 5-Whys analysis.

    ``whys`` may be empty (treated as five blank slots) or name levels 1–5.
    Duplicate levels are refused rather than last-write-wins, so a stale editor
    cannot silently drop a Why another tab added at the same level.
    """

    model_config = ConfigDict(extra="forbid")

    problem_statement: str = Field("", max_length=RCA_TEXT_MAX_LENGTH)
    whys: List[InvestigationRcaWhyInput] = Field(default_factory=list)
    root_cause: str = Field("", max_length=RCA_TEXT_MAX_LENGTH)
    #: Omitted (or null) leaves the stored contributing factors alone.
    #:
    #: INV-C12 made the ICAM factor list on ``/investigations/{id}/factors`` the
    #: author of this text; it is derived from the factors and written to both
    #: legacy readers on every factor mutation. A workspace save that also sent
    #: a copy of it would be a second writer racing the first, which is PX-168's
    #: shape. The field stays on the contract, and a string is still honoured,
    #: because a caller that has not moved to the factor endpoints must keep the
    #: box it has — the structured factors live on ``fishbone_diagrams`` and are
    #: not lost when it does, only the derived paragraph is overwritten until
    #: the next factor mutation rewrites it.
    contributing_factors: Optional[str] = Field(default=None, max_length=RCA_TEXT_MAX_LENGTH)

    @field_validator("whys")
    @classmethod
    def _unique_levels(cls, value: List[InvestigationRcaWhyInput]) -> List[InvestigationRcaWhyInput]:
        levels = [item.level for item in value]
        if len(levels) != len(set(levels)):
            raise ValueError("whys must not repeat a level")
        return value


class InvestigationRcaResponse(BaseModel):
    """The run's workspace RCA.

    ``id`` is the ``five_whys_analyses`` row, or null when the run has no
    analysis yet — a successful empty answer, not a 404. Dual-written
    ``why_1``..``why_5`` strings stay on ``investigation_runs.data`` for
    closure and the pack; they are not advertised here, because PUT authors
    the analysis through ``whys`` and a leftover-string field would be a
    second writer (PX-168).
    """

    id: Optional[int] = None
    investigation_id: int
    problem_statement: str
    whys: List[InvestigationRcaWhy]
    root_cause: str
    contributing_factors: str


class CreateCapaFromWhyRequest(BaseModel):
    """Create a CAPA from one Why on this investigation's analysis (INV-C11).

    ``why_level`` is required. Empty Why is a 422, not invented CAPA text and
    not a 500. Optional title/description override the Why answer; they are
    not filled in from an empty slot.
    """

    model_config = ConfigDict(extra="forbid")

    why_level: int = Field(..., ge=1, le=20)
    title: Optional[str] = Field(default=None, max_length=255)
    description: Optional[str] = None
    due_date: Optional[str] = None
    priority: Optional[str] = None
    five_whys_id: Optional[int] = None
