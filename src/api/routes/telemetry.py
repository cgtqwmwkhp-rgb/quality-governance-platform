"""
Telemetry API for experiment events (EXP-001 and future)

This endpoint receives frontend telemetry events and:
1. Validates event schema (bounded dimensions only)
2. Logs to structured logger (for Azure Log Analytics)
3. Aggregates to local file for evaluator consumption

NO PII POLICY:
- All dimensions must be from an allowlist
- No free text fields accepted
- Session IDs are anonymous (not linked to users)
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field, validator
from sqlalchemy.exc import SQLAlchemyError

from src.api.dependencies import CurrentSuperuser, CurrentUser
from src.api.schemas.error_codes import ErrorCode
from src.api.schemas.telemetry import (
    GetExperimentMetricsResponse,
    ReceiveBatchEventResponse,
    ReceiveEventResponse,
    ResetMetricsResponse,
)
from src.infrastructure.monitoring.azure_monitor import track_metric

router = APIRouter(prefix="/telemetry", tags=["telemetry"])

logger = logging.getLogger(__name__)

# ============================================================================
# Configuration
# ============================================================================

# Allowlisted event names (bounded)
ALLOWED_EVENTS = {
    # EXP-001 form autosave events
    "exp001_form_opened",
    "exp001_draft_saved",
    "exp001_draft_recovered",
    "exp001_draft_discarded",
    "exp001_form_submitted",
    "exp001_form_abandoned",
    # Login UX events (LOGIN_UX_CONTRACT.md)
    "login_completed",
    "login_error_shown",
    "login_recovery_action",
    "login_slow_warning",
}

# Allowlisted dimension keys (bounded)
ALLOWED_DIMENSIONS = {
    # EXP-001 form dimensions
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
    # Login UX dimensions (LOGIN_UX_CONTRACT.md)
    "result",
    "durationBucket",
    "errorCode",
    "action",
}

# Allowlisted dimension values for string fields
ALLOWED_FORM_TYPES = {"incident", "near-miss", "complaint", "rta"}
ALLOWED_ENVIRONMENTS = {"development", "staging", "production"}

# Login UX dimension values (LOGIN_UX_CONTRACT.md)
ALLOWED_LOGIN_RESULTS = {"success", "error"}
ALLOWED_DURATION_BUCKETS = {"fast", "normal", "slow", "very_slow", "timeout"}
ALLOWED_ERROR_CODES = {
    "TIMEOUT",
    "UNAUTHORIZED",
    "UNAVAILABLE",
    "SERVER_ERROR",
    "NETWORK_ERROR",
    "UNKNOWN",
}
ALLOWED_ACTIONS = {"retry", "clear_session"}

# Local aggregation file (for evaluator)
# Default to a subdirectory in the project rather than hardcoded /tmp
_DEFAULT_METRICS_DIR = Path(__file__).parent.parent.parent.parent / "artifacts"
METRICS_DIR = Path(os.getenv("METRICS_DIR", str(_DEFAULT_METRICS_DIR)))


# ============================================================================
# Models
# ============================================================================


class TelemetryEvent(BaseModel):
    """Single telemetry event from frontend."""

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
        # Only allow known dimension keys
        for key in v.keys():
            if key not in ALLOWED_DIMENSIONS:
                raise ValueError(f"Dimension key '{key}' not in allowlist")

        # Validate formType values (EXP-001)
        if "formType" in v and v["formType"] not in ALLOWED_FORM_TYPES:
            raise ValueError(f"formType '{v['formType']}' not in allowlist")

        # Validate environment values
        if "environment" in v and v["environment"] not in ALLOWED_ENVIRONMENTS:
            raise ValueError(f"environment '{v['environment']}' not in allowlist")

        # Validate login UX dimension values (LOGIN_UX_CONTRACT.md)
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
    """Batch of telemetry events."""

    events: List[TelemetryEvent] = Field(..., min_length=1, max_length=100)


class MetricsAggregation(BaseModel):
    """Aggregated metrics for evaluator consumption."""

    experimentId: str
    collectionStart: str
    collectionEnd: str
    samples: int
    events: dict
    dimensions: dict


# ============================================================================
# Metrics Aggregation (local file for evaluator)
# ============================================================================


def load_metrics_file() -> dict:
    """Load existing metrics aggregation file."""
    metrics_path = METRICS_DIR / "experiment_metrics_EXP_001.json"
    if metrics_path.exists():
        with open(metrics_path, "r") as f:
            return json.load(f)
    return {
        "experimentId": "EXP_001",
        "collectionStart": None,
        "collectionEnd": None,
        "samples": 0,
        "events": {},
        "dimensions": {},
        "metrics": None,
    }


def save_metrics_file(metrics: dict) -> None:
    """Save metrics aggregation file."""
    METRICS_DIR.mkdir(parents=True, exist_ok=True)
    metrics_path = METRICS_DIR / "experiment_metrics_EXP_001.json"
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)


def aggregate_event(event: TelemetryEvent) -> None:
    """Aggregate a single event into metrics file."""
    metrics = load_metrics_file()

    # Update collection window
    if not metrics["collectionStart"]:
        metrics["collectionStart"] = event.timestamp
    metrics["collectionEnd"] = event.timestamp

    # Count events by name
    if event.name not in metrics["events"]:
        metrics["events"][event.name] = 0
    metrics["events"][event.name] += 1

    # Count primary sample event (exp001_form_submitted)
    if event.name == "exp001_form_submitted":
        metrics["samples"] += 1

    # Track dimension distributions
    for dim_key, dim_value in event.dimensions.items():
        if dim_key not in metrics["dimensions"]:
            metrics["dimensions"][dim_key] = {}
        dim_str = str(dim_value)
        if dim_str not in metrics["dimensions"][dim_key]:
            metrics["dimensions"][dim_key][dim_str] = 0
        metrics["dimensions"][dim_key][dim_str] += 1

    # Calculate derived metrics when we have samples
    if metrics["samples"] >= 10:
        form_opened = metrics["events"].get("exp001_form_opened", 0)
        form_submitted = metrics["events"].get("exp001_form_submitted", 0)
        form_abandoned = metrics["events"].get("exp001_form_abandoned", 0)
        draft_recovered = metrics["events"].get("exp001_draft_recovered", 0)

        # Abandonment rate
        if form_opened > 0:
            abandonment_rate = form_abandoned / form_opened
        else:
            abandonment_rate = 0

        # Draft recovery usage (among sessions with drafts)
        has_draft_true = metrics["dimensions"].get("hasDraft", {}).get("true", 0)
        if has_draft_true > 0:
            draft_recovery_usage = draft_recovered / has_draft_true
        else:
            draft_recovery_usage = 0

        metrics["metrics"] = {
            "abandonmentRate": round(abandonment_rate, 4),
            "draftRecoveryUsage": round(draft_recovery_usage, 4),
            "completionTime": 0,  # Would need timing data
            "errorRate": 0,  # Would need error counts
        }

    save_metrics_file(metrics)


# ============================================================================
# Routes
# ============================================================================


@router.post("/events", response_model=ReceiveEventResponse)
async def receive_event(event: TelemetryEvent, current_user: CurrentUser):
    """
    Receive a single telemetry event.

    Events are:
    1. Validated against allowlists (no PII)
    2. Logged to structured logger
    3. Aggregated to local file for evaluator

    This endpoint is fault-tolerant: file I/O errors are logged but do not
    return 500 to avoid blocking client telemetry.
    """
    track_metric("telemetry.event_received", 1, {"event_name": event.name})
    # Log to structured logger (goes to Azure Log Analytics)
    logger.info(
        f"TELEMETRY_EVENT: {event.name}",
        extra={
            "event_name": event.name,
            "session_id": event.sessionId,
            "dimensions": event.dimensions,
            "timestamp": event.timestamp,
        },
    )

    # Aggregate to local file (fault-tolerant)
    try:
        aggregate_event(event)
    except (SQLAlchemyError, ValueError) as e:
        # Log but don't fail - telemetry should never block clients
        logger.warning(f"Failed to aggregate telemetry event: {type(e).__name__}")

    return ReceiveEventResponse(status="ok")


@router.post("/events/batch", response_model=ReceiveBatchEventResponse)
async def receive_events_batch(batch: TelemetryBatch, current_user: CurrentUser):
    """
    Receive a batch of telemetry events (for offline buffer flush).

    This endpoint is fault-tolerant: file I/O errors are logged but do not
    return 500 to avoid blocking client telemetry.
    """
    processed = 0
    for event in batch.events:
        logger.info(
            f"TELEMETRY_EVENT: {event.name}",
            extra={
                "event_name": event.name,
                "session_id": event.sessionId,
                "dimensions": event.dimensions,
                "timestamp": event.timestamp,
            },
        )
        try:
            aggregate_event(event)
            processed += 1
        except (SQLAlchemyError, ValueError) as e:
            # Log but don't fail - telemetry should never block clients
            logger.warning(f"Failed to aggregate telemetry event: {type(e).__name__}")

    return ReceiveBatchEventResponse(status="ok", count=processed)


@router.get("/metrics/{experiment_id}", response_model=GetExperimentMetricsResponse)
async def get_metrics(experiment_id: str, current_user: CurrentUser):
    """
    Get aggregated metrics for an experiment.

    Used by the evaluator to check current sample count and metrics.
    """
    if experiment_id != "EXP_001":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    metrics = load_metrics_file()
    return metrics


@router.delete("/metrics/{experiment_id}", response_model=ResetMetricsResponse)
async def reset_metrics(experiment_id: str, current_user: CurrentSuperuser):
    """
    Reset metrics for an experiment (staging only, for testing).
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=ErrorCode.PERMISSION_DENIED)

    if experiment_id != "EXP_001":
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=ErrorCode.ENTITY_NOT_FOUND)

    metrics_path = METRICS_DIR / "experiment_metrics_EXP_001.json"
    if metrics_path.exists():
        metrics_path.unlink()

    return ResetMetricsResponse(status="reset")
