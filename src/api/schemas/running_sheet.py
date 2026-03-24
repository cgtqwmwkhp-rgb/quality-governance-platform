"""Shared schemas for case runner-sheet entries."""

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class RunningSheetEntryType(str, enum.Enum):
    """Supported runner-sheet entry types."""

    NOTE = "note"
    UPDATE = "update"
    DECISION = "decision"
    COMMUNICATION = "communication"


class RunningSheetEntryCreate(BaseModel):
    """Payload for adding a new runner-sheet entry."""

    content: str = Field(..., min_length=1, max_length=4000)
    entry_type: RunningSheetEntryType = RunningSheetEntryType.NOTE

    @field_validator("content")
    @classmethod
    def strip_content(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Content is required")
        return value


class RunningSheetEntryResponse(BaseModel):
    """Response model for a runner-sheet entry."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    content: str
    entry_type: RunningSheetEntryType
    author_id: Optional[int] = None
    author_email: Optional[str] = None
    created_at: datetime
