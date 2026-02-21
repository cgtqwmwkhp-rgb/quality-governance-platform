"""Telemetry domain service.

Extracts event ingestion, batch processing, metrics aggregation,
and metrics lifecycle from the telemetry route module.
"""

import json
import logging
from pathlib import Path
from typing import Any

from src.core.config import settings
from src.infrastructure.monitoring.azure_monitor import track_metric

logger = logging.getLogger(__name__)

_DEFAULT_METRICS_DIR = Path(__file__).parent.parent.parent / "artifacts"
METRICS_DIR = Path(settings.metrics_dir) if settings.metrics_dir else _DEFAULT_METRICS_DIR


class TelemetryService:
    """Handles telemetry event ingestion, aggregation, and metrics queries."""

    # ------------------------------------------------------------------
    # Metrics file I/O
    # ------------------------------------------------------------------

    @staticmethod
    def _load_metrics_file() -> dict:
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

    @staticmethod
    def _save_metrics_file(metrics: dict) -> None:
        METRICS_DIR.mkdir(parents=True, exist_ok=True)
        metrics_path = METRICS_DIR / "experiment_metrics_EXP_001.json"
        with open(metrics_path, "w") as f:
            json.dump(metrics, f, indent=2)

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    @classmethod
    def aggregate_event(cls, event_name: str, timestamp: str, session_id: str, dimensions: dict) -> None:
        """Aggregate a single validated event into the metrics file."""
        metrics = cls._load_metrics_file()

        if not metrics["collectionStart"]:
            metrics["collectionStart"] = timestamp
        metrics["collectionEnd"] = timestamp

        if event_name not in metrics["events"]:
            metrics["events"][event_name] = 0
        metrics["events"][event_name] += 1

        if event_name == "exp001_form_submitted":
            metrics["samples"] += 1

        for dim_key, dim_value in dimensions.items():
            if dim_key not in metrics["dimensions"]:
                metrics["dimensions"][dim_key] = {}
            dim_str = str(dim_value)
            if dim_str not in metrics["dimensions"][dim_key]:
                metrics["dimensions"][dim_key][dim_str] = 0
            metrics["dimensions"][dim_key][dim_str] += 1

        if metrics["samples"] >= 10:
            form_opened = metrics["events"].get("exp001_form_opened", 0)
            form_abandoned = metrics["events"].get("exp001_form_abandoned", 0)
            draft_recovered = metrics["events"].get("exp001_draft_recovered", 0)

            abandonment_rate = form_abandoned / form_opened if form_opened > 0 else 0

            has_draft_true = metrics["dimensions"].get("hasDraft", {}).get("true", 0)
            draft_recovery_usage = draft_recovered / has_draft_true if has_draft_true > 0 else 0

            metrics["metrics"] = {
                "abandonmentRate": round(abandonment_rate, 4),
                "draftRecoveryUsage": round(draft_recovery_usage, 4),
                "completionTime": 0,
                "errorRate": 0,
            }

        cls._save_metrics_file(metrics)

    # ------------------------------------------------------------------
    # Event ingestion
    # ------------------------------------------------------------------

    @classmethod
    def ingest_event(cls, event_name: str, timestamp: str, session_id: str, dimensions: dict) -> str:
        """Ingest a single telemetry event: log + aggregate.

        Returns:
            Status string ("ok").
        """
        track_metric("telemetry.event_received", 1, {"event_name": event_name})

        logger.info(
            f"TELEMETRY_EVENT: {event_name}",
            extra={
                "event_name": event_name,
                "session_id": session_id,
                "dimensions": dimensions,
                "timestamp": timestamp,
            },
        )

        try:
            cls.aggregate_event(event_name, timestamp, session_id, dimensions)
        except (ValueError, OSError) as e:
            logger.warning(
                "Failed to aggregate telemetry event [session=%s]: %s: %s",
                session_id,
                type(e).__name__,
                str(e)[:200],
                exc_info=True,
            )

        return "ok"

    @classmethod
    def ingest_batch(cls, events: list[dict[str, Any]]) -> tuple[str, int]:
        """Ingest a batch of telemetry events.

        Args:
            events: List of dicts with keys name, timestamp, sessionId, dimensions.

        Returns:
            Tuple of (status_string, processed_count).
        """
        processed = 0
        for event in events:
            logger.info(
                f"TELEMETRY_EVENT: {event['name']}",
                extra={
                    "event_name": event["name"],
                    "session_id": event["sessionId"],
                    "dimensions": event.get("dimensions", {}),
                    "timestamp": event["timestamp"],
                },
            )
            try:
                cls.aggregate_event(
                    event["name"],
                    event["timestamp"],
                    event["sessionId"],
                    event.get("dimensions", {}),
                )
                processed += 1
            except (ValueError, OSError) as e:
                logger.warning(
                    "Failed to aggregate telemetry event in batch [session=%s, event=%s]: %s: %s",
                    event["sessionId"],
                    event["name"],
                    type(e).__name__,
                    str(e)[:200],
                    exc_info=True,
                )

        status_msg = "ok" if processed == len(events) else "partial"
        return status_msg, processed

    # ------------------------------------------------------------------
    # Metrics queries
    # ------------------------------------------------------------------

    @classmethod
    def get_metrics(cls, experiment_id: str) -> dict:
        """Return aggregated metrics for an experiment.

        Raises:
            LookupError: If the experiment is not found.
        """
        if experiment_id != "EXP_001":
            raise LookupError(f"Experiment '{experiment_id}' not found")
        return cls._load_metrics_file()

    @classmethod
    def reset_metrics(cls, experiment_id: str) -> str:
        """Reset metrics for an experiment.

        Raises:
            LookupError: If the experiment is not found.
        """
        if experiment_id != "EXP_001":
            raise LookupError(f"Experiment '{experiment_id}' not found")

        metrics_path = METRICS_DIR / "experiment_metrics_EXP_001.json"
        if metrics_path.exists():
            metrics_path.unlink()

        return "reset"
