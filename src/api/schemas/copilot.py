"""Pydantic response schemas for AI Copilot API."""

from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel


class CloseSessionResponse(BaseModel):
    """Response after closing a copilot session."""

    status: str


class SubmitFeedbackResponse(BaseModel):
    """Response after submitting message feedback."""

    status: str
    feedback_id: int


class ActionDetailResponse(BaseModel):
    """Single entry from the copilot actions registry."""

    model_config = {"extra": "allow"}


class ExecuteActionResponse(BaseModel):
    """Response after executing a copilot action."""

    status: str
    action: str
    parameters: dict[str, Any]
    result: dict[str, Any]


class SearchKnowledgeResponse(BaseModel):
    """Single knowledge-base search result."""

    id: int
    title: str
    content: str
    category: str
    tags: Optional[list[str]] = None


class AddKnowledgeResponse(BaseModel):
    """Response after adding a knowledge-base entry."""

    id: int
    title: str
