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
    contributing_factors: str = Field("", max_length=RCA_TEXT_MAX_LENGTH)

    @field_validator("whys")
    @classmethod
    def _unique_levels(cls, value: List[InvestigationRcaWhyInput]) -> List[InvestigationRcaWhyInput]:
        levels = [item.level for item in value]
        if len(levels) != len(set(levels)):
            raise ValueError("whys must not repeat a level")
        return value


class InvestigationRcaResponse(BaseModel):
    """The run's workspace RCA.

    ``analysis_id`` is null when the run has no analysis yet — a successful
    empty answer, not a 404. ``why_1``..``why_5`` are the exact strings written
    back onto ``investigation_runs.data`` so a caller can see what closure and
    the pack will still read.
    """

    analysis_id: Optional[int] = None
    investigation_id: int
    problem_statement: str
    whys: List[InvestigationRcaWhy]
    root_cause: str
    contributing_factors: str
    why_1: str = ""
    why_2: str = ""
    why_3: str = ""
    why_4: str = ""
    why_5: str = ""
