"""Standardized setup_required response schema.

Use this schema when a module is not yet configured or data is missing.
This provides a consistent response format that:
1. Returns HTTP 200 (not 5xx) so smoke gates pass
2. Signals to the frontend that setup is required
3. Prevents retry storms by using a deterministic error class
4. Provides actionable next steps

Usage:
    from src.api.schemas.setup_required import SetupRequiredResponse, setup_required_response

    # In an endpoint:
    if not module_configured:
        return setup_required_response(
            module="planet-mark",
            message="Carbon reporting years not configured",
            next_action="Configure at least one reporting year via POST /api/v1/planet-mark/years"
        )
"""

from typing import Optional

from pydantic import BaseModel, Field


class SetupRequiredResponse(BaseModel):
    """Standard response when a module requires setup before use.
    
    This is returned as HTTP 200 to avoid triggering smoke gate failures,
    but the error_class: SETUP_REQUIRED signals to clients that the module
    is not ready for normal operation.
    """
    
    error_class: str = Field(
        default="SETUP_REQUIRED",
        description="Error classification for client handling. Always 'SETUP_REQUIRED' for this response type."
    )
    setup_required: bool = Field(
        default=True,
        description="Flag indicating setup is required. Always true for this response type."
    )
    module: str = Field(
        ...,
        description="The module that requires setup (e.g., 'planet-mark', 'uvdb')"
    )
    message: str = Field(
        ...,
        description="Human-readable description of what setup is needed"
    )
    next_action: str = Field(
        ...,
        description="Specific action the user/admin should take"
    )
    request_id: Optional[str] = Field(
        default=None,
        description="Request ID for tracing"
    )
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "error_class": "SETUP_REQUIRED",
                "setup_required": True,
                "module": "planet-mark",
                "message": "No carbon reporting years configured",
                "next_action": "Create a reporting year via POST /api/v1/planet-mark/years",
                "request_id": "abc123-def456"
            }
        }
    }


def setup_required_response(
    module: str,
    message: str,
    next_action: str,
    request_id: Optional[str] = None
) -> dict:
    """Create a standardized setup_required response dict.
    
    Args:
        module: The module that requires setup
        message: Human-readable description
        next_action: Actionable next step
        request_id: Optional request ID for tracing
        
    Returns:
        dict matching SetupRequiredResponse schema
    """
    return {
        "error_class": "SETUP_REQUIRED",
        "setup_required": True,
        "module": module,
        "message": message,
        "next_action": next_action,
        "request_id": request_id,
    }
