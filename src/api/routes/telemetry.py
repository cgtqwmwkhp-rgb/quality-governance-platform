"""Telemetry API routes.

Thin controller layer — all business logic lives in TelemetryService.
Validation schemas remain here (they are request-level concerns).
"""

import logging
from typing import Annotated, List, Optional

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field, validator

from src.api.dependencies import CurrentSuperuser, CurrentUser, require_permission
from src.api.schemas.telemetry import (
    GetExperimentMetricsResponse,
    ReceiveBatchEventResponse,
    ReceiveEventResponse,
    ResetMetricsResponse,
)
from src.domain.exceptions import AuthorizationError, NotFoundError
from src.domain.models.user import User
from src.domain.services.telemetry_service import TelemetryService

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

# ============================================================================
# Allowlists
# ============================================================================

ALLOWED_EVENTS = {
    "exp001_form_opened",
    "exp001_draft_saved",
    "exp001_draft_recovered",
    "exp001_draft_discarded",
    "exp001_form_submitted",
    "exp001_form_abandoned",
    "login_completed",
    "login_error_shown",
    "login_recovery_action",
    "login_slow_warning",
}

ALLOWED_DIMENSIONS = {
    "formType",
    "flagEnabled",
    "hasDraft",
    "hadDraft",
    "step",
    "stepCount",
    "lastStep",
    "draftAgeSeconds",
    "error",
    "environment",
    "result",
    "durationBucket",
    "errorCode",
    "action",
}

ALLOWED_FORM_TYPES = {"incident", "near-miss", "complaint", "rta"}
ALLOWED_ENVIRONMENTS = {"development", "staging", "production"}
ALLOWED_LOGIN_RESULTS = {"success", "error"}
ALLOWED_DURATION_BUCKETS = {"fast", "normal", "slow", "very_slow", "timeout"}
ALLOWED_ERROR_CODES = {"TIMEOUT", "UNAUTHORIZED", "UNAVAILABLE", "SERVER_ERROR", "NETWORK_ERROR", "UNKNOWN"}
ALLOWED_ACTIONS = {"retry", "clear_session"}


# ============================================================================
# Models
# ============================================================================


class TelemetryEvent(BaseModel):
    name: str = Field(..., description="Event name (must be allowlisted)")
    timestamp: str = Field(..., description="ISO timestamp")
    sessionId: str = Field(..., description="Anonymous session ID")
    dimensions: dict = Field(default_factory=dict, description="Event dimensions")

    @validator("name")
    def validate_event_name(cls, v):
        if v not in ALLOWED_EVENTS:
            raise ValueError(f"Event name '{v}' not in allowlist")
        return v

    @validator("dimensions")
    def validate_dimensions(cls, v):
        for key in v.keys():
            if key not in ALLOWED_DIMENSIONS:
                raise ValueError(f"Dimension key '{key}' not in allowlist")
        if "formType" in v and v["formType"] not in ALLOWED_FORM_TYPES:
            raise ValueError(f"formType '{v['formType']}' not in allowlist")
        if "environment" in v and v["environment"] not in ALLOWED_ENVIRONMENTS:
            raise ValueError(f"environment '{v['environment']}' not in allowlist")
        if "result" in v and v["result"] not in ALLOWED_LOGIN_RESULTS:
            raise ValueError(f"result '{v['result']}' not in allowlist")
        if "durationBucket" in v and v["durationBucket"] not in ALLOWED_DURATION_BUCKETS:
            raise ValueError(f"durationBucket '{v['durationBucket']}' not in allowlist")
        if "errorCode" in v and v["errorCode"] not in ALLOWED_ERROR_CODES:
            raise ValueError(f"errorCode '{v['errorCode']}' not in allowlist")
        if "action" in v and v["action"] not in ALLOWED_ACTIONS:
            raise ValueError(f"action '{v['action']}' not in allowlist")
        return v


class TelemetryBatch(BaseModel):
    events: List[TelemetryEvent] = Field(..., min_length=1, max_length=100)


# ============================================================================
# Routes
# ============================================================================


csp_logger = logging.getLogger("csp_report")


@router.post("/csp-report", status_code=status.HTTP_204_NO_CONTENT)
async def csp_report(request: Request):
    """Receive Content-Security-Policy violation reports from browsers."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    report = body.get("csp-report", body)
    csp_logger.warning(
        "CSP violation",
        extra={
            "blocked_uri": report.get("blocked-uri", "unknown"),
            "document_uri": report.get("document-uri", "unknown"),
            "violated_directive": report.get("violated-directive", "unknown"),
            "original_policy": report.get("original-policy", ""),
            "source_file": report.get("source-file", ""),
            "line_number": report.get("line-number", ""),
        },
    )
    return None


@router.post("/events", response_model=ReceiveEventResponse)
async def receive_event(
    event: TelemetryEvent,
    current_user: Annotated[User, Depends(require_permission("telemetry:create"))],
):
    """Receive a single telemetry event."""
    status_msg = TelemetryService.ingest_event(
        event_name=event.name,
        timestamp=event.timestamp,
        session_id=event.sessionId,
        dimensions=event.dimensions,
    )
    return ReceiveEventResponse(status=status_msg)


@router.post("/events/batch", response_model=ReceiveBatchEventResponse)
async def receive_events_batch(
    batch: TelemetryBatch,
    current_user: Annotated[User, Depends(require_permission("telemetry:create"))],
):
    """Receive a batch of telemetry events."""
    events_dicts = [e.model_dump() for e in batch.events]
    status_msg, processed = TelemetryService.ingest_batch(events_dicts)
    return ReceiveBatchEventResponse(status=status_msg, count=processed)


@router.get("/metrics/{experiment_id}", response_model=GetExperimentMetricsResponse)
async def get_metrics(experiment_id: str, current_user: CurrentUser):
    """Get aggregated metrics for an experiment."""
    try:
        return TelemetryService.get_metrics(experiment_id)
    except LookupError:
        raise NotFoundError("Experiment not found")


@router.delete("/metrics/{experiment_id}", response_model=ResetMetricsResponse)
async def reset_metrics(experiment_id: str, current_user: CurrentSuperuser):
    """Reset metrics for an experiment (staging only, for testing)."""
    if not current_user.is_superuser:
        raise AuthorizationError("Permission denied")
    try:
        result = TelemetryService.reset_metrics(experiment_id)
    except LookupError:
        raise NotFoundError("Experiment not found")
    return ResetMetricsResponse(status=result)
