"""Structured JSON logging infrastructure with correlation context."""

import logging
import logging.handlers
import os
import sys
from typing import Any

from src.infrastructure.logging.context import get_request_id


class CorrelationFilter(logging.Filter):
    """Injects correlation IDs from contextvars into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.correlation_id = get_request_id() or ""  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE

        from src.infrastructure.logging.trace_context import get_span_id, get_trace_id

        record.trace_id = get_trace_id() or ""  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
        record.span_id = get_span_id() or ""  # type: ignore[attr-defined]  # TYPE-IGNORE: MYPY-OVERRIDE
        return True


class StructuredJsonFormatter(logging.Formatter):
    """Outputs log records as single-line JSON with standard fields."""

    def format(self, record: logging.LogRecord) -> str:
        import json
        from datetime import datetime, timezone

        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        for field in ("correlation_id", "trace_id", "span_id"):
            value = getattr(record, field, None)
            if value:
                payload[field] = value

        if record.exc_info and record.exc_info[1] is not None:
            payload["exception"] = self.formatException(record.exc_info)

        if hasattr(record, "__dict__"):
            skip = {
                "name",
                "msg",
                "args",
                "levelname",
                "levelno",
                "pathname",
                "filename",
                "module",
                "exc_info",
                "exc_text",
                "stack_info",
                "lineno",
                "funcName",
                "created",
                "msecs",
                "relativeCreated",
                "thread",
                "threadName",
                "processName",
                "process",
                "message",
                "correlation_id",
                "trace_id",
                "span_id",
                "taskName",
            }
            for key, value in record.__dict__.items():
                if key.startswith("_") or key in skip:
                    continue
                if key not in payload:
                    payload[key] = value

        return json.dumps(payload, default=str)


def configure_structured_logging(
    level: str = "INFO",
    log_dir: str | None = None,
) -> None:
    """Set up structured JSON logging with stdout and optional file rotation.

    Args:
        level: Root log level.
        log_dir: Directory for rotating log file. Disabled when *None*.
    """
    root = logging.getLogger()
    root.setLevel(level)
    root.handlers.clear()

    from src.infrastructure.logging.pii_filter import PIIFilter

    correlation_filter = CorrelationFilter()
    pii_filter = PIIFilter()
    formatter = StructuredJsonFormatter()

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setFormatter(formatter)
    stdout_handler.addFilter(correlation_filter)
    stdout_handler.addFilter(pii_filter)
    root.addHandler(stdout_handler)

    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            filename=os.path.join(log_dir, "app.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
        )
        file_handler.setFormatter(formatter)
        file_handler.addFilter(correlation_filter)
        file_handler.addFilter(pii_filter)
        root.addHandler(file_handler)

    for uvicorn_logger_name in ("uvicorn", "uvicorn.access"):
        uv = logging.getLogger(uvicorn_logger_name)
        uv.handlers.clear()
        uv.addHandler(stdout_handler)
        uv.setLevel(level)
