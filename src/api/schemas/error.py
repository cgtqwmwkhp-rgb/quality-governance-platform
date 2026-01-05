
from pydantic import BaseModel
from typing import Any, Optional


class ErrorResponse(BaseModel):
    """Canonical error response schema."""

    error_code: str
    message: str
    details: Optional[Any] = None
    request_id: Optional[str] = None
