from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class FiveWhysAnalysisResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    status: str = "in_progress"
    iterations: list[dict[str, Any]] = []
    root_cause: Optional[str] = None

    class Config:
        from_attributes = True


class FishboneDiagramResponse(BaseModel):
    id: int
    entity_type: str
    entity_id: int
    status: str = "in_progress"
    causes: list[dict[str, Any]] = []
    root_cause: Optional[str] = None

    class Config:
        from_attributes = True


class RCACAPAResponse(BaseModel):
    id: int
    title: str
    status: str
    investigation_id: Optional[int] = None
    due_date: Optional[datetime] = None

    class Config:
        from_attributes = True
