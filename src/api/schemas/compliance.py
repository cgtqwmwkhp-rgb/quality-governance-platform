"""Compliance Automation API response schemas."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel, Field


class ComplianceScoreResponse(BaseModel):
    """Response model for compliance score."""

    standard_id: int
    standard_name: str
    score: float
    total_clauses: int
    compliant_clauses: int


class ComplianceGapResponse(BaseModel):
    """Response model for compliance gap."""

    clause_id: str
    clause_name: str
    gap_description: str
    priority: str


class ComplianceReportResponse(BaseModel):
    """Response model for compliance report."""

    scores: list[ComplianceScoreResponse] = []
    gaps: list[ComplianceGapResponse] = []
    overall_score: float
