"""OpenTelemetry instrumentation and Azure Monitor integration."""

import json
import logging
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.metrics import Counter, Histogram, UpDownCounter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

logger = logging.getLogger(__name__)


class StructuredLogger:
    """Lightweight structured logger that emits JSON-formatted log lines.

    Compatible with Azure Monitor / Application Insights log ingestion and
    local console debugging.  Each call produces a single JSON object so
    downstream log aggregators can parse fields without regex.
    """

    def __init__(self, name: str) -> None:
        self._logger = logging.getLogger(name)

    def _emit(self, level: int, event: str, **kwargs: Any) -> None:
        payload = {"event": event, **kwargs}
        self._logger.log(level, json.dumps(payload, default=str))

    def info(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.INFO, event, **kwargs)

    def warning(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.WARNING, event, **kwargs)

    def error(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.ERROR, event, **kwargs)

    def debug(self, event: str, **kwargs: Any) -> None:
        self._emit(logging.DEBUG, event, **kwargs)

_tracer: trace.Tracer | None = None
_meter: metrics.Meter | None = None

# Business metric counters
_incidents_created: Counter | None = None
_incidents_resolved: Counter | None = None
_audits_completed: Counter | None = None
_audit_findings: Counter | None = None
_api_response_time: Histogram | None = None
_db_query_time: Histogram | None = None
_cache_hit_rate: UpDownCounter | None = None
_capa_created: Counter | None = None
_capa_closed: Counter | None = None
_complaints_created: Counter | None = None
_risks_created: Counter | None = None
_auth_login: Counter | None = None
_auth_logout: Counter | None = None
_documents_uploaded: Counter | None = None
_workflows_completed: Counter | None = None
_workflow_completion_time: Histogram | None = None
_error_rate_5xx: Counter | None = None
_cache_miss_rate: Counter | None = None
_db_pool_usage: UpDownCounter | None = None
_celery_task_failures: Counter | None = None
_celery_queue_depth: UpDownCounter | None = None
_auth_failures: Counter | None = None


def setup_telemetry(app: Any = None, service_name: str = "quality-governance-platform") -> None:
    """Initialize OpenTelemetry with tracing and metrics."""
    global _tracer, _meter
    global _incidents_created, _incidents_resolved
    global _audits_completed, _audit_findings
    global _api_response_time, _db_query_time, _cache_hit_rate

    from src.core.config import settings

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": settings.app_version,
            "deployment.environment": settings.app_env,
        }
    )

    default_sample_rate = 0.1 if settings.is_production else 1.0
    sample_rate = (
        settings.otel_trace_sample_rate if settings.otel_trace_sample_rate is not None else default_sample_rate
    )
    sampler = ParentBased(root=TraceIdRatioBased(sample_rate))

    tracer_provider = TracerProvider(resource=resource, sampler=sampler)
    logger.info("Trace sampling configured at %.0f%% (environment=%s)", sample_rate * 100, settings.app_env)

    connection_string = settings.applicationinsights_connection_string or None
    if connection_string:
        try:
            from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter, AzureMonitorTraceExporter

            trace_exporter = AzureMonitorTraceExporter(connection_string=connection_string)
            tracer_provider.add_span_processor(BatchSpanProcessor(trace_exporter))

            metric_exporter = AzureMonitorMetricExporter(connection_string=connection_string)
            metric_reader = PeriodicExportingMetricReader(metric_exporter)
            meter_provider = MeterProvider(resource=resource, metric_readers=[metric_reader])
        except ImportError:
            logger.warning("Azure Monitor exporter not available, using default providers")
            meter_provider = MeterProvider(resource=resource)
    else:
        meter_provider = MeterProvider(resource=resource)

    trace.set_tracer_provider(tracer_provider)
    metrics.set_meter_provider(meter_provider)

    _tracer = trace.get_tracer(__name__)
    _meter = metrics.get_meter(__name__)

    _incidents_created = _meter.create_counter("incidents.created", description="Number of incidents created")
    _incidents_resolved = _meter.create_counter("incidents.resolved", description="Number of incidents resolved")
    _audits_completed = _meter.create_counter("audits.completed", description="Number of audits completed")
    _audit_findings = _meter.create_counter("audits.findings", description="Number of audit findings")
    _api_response_time = _meter.create_histogram(
        "api.response_time_ms", description="API response time in milliseconds", unit="ms"
    )
    _db_query_time = _meter.create_histogram(
        "db.query_time_ms", description="Database query time in milliseconds", unit="ms"
    )
    _cache_hit_rate = _meter.create_up_down_counter("cache.operations", description="Cache hit/miss counter")

    # Additional business metrics
    global _capa_created, _capa_closed, _complaints_created, _risks_created
    global _auth_login, _auth_logout, _documents_uploaded, _workflows_completed
    global _workflow_completion_time
    global _error_rate_5xx, _cache_miss_rate, _db_pool_usage
    global _celery_task_failures, _celery_queue_depth, _auth_failures

    _capa_created = _meter.create_counter("capa.created", description="Number of CAPA actions created")
    _capa_closed = _meter.create_counter("capa.closed", description="Number of CAPA actions closed")
    _complaints_created = _meter.create_counter("complaints.created", description="Number of complaints created")
    _risks_created = _meter.create_counter("risks.created", description="Number of risks created")
    _auth_login = _meter.create_counter("auth.login", description="Number of user logins")
    _auth_logout = _meter.create_counter("auth.logout", description="Number of user logouts")
    _documents_uploaded = _meter.create_counter("documents.uploaded", description="Number of documents uploaded")
    _workflows_completed = _meter.create_counter("workflows.completed", description="Number of workflows completed")
    _workflow_completion_time = _meter.create_histogram(
        "workflow.completion_time_hours", description="Workflow completion time in hours", unit="h"
    )

    _error_rate_5xx = _meter.create_counter("api.error_rate_5xx", description="Count of 5xx HTTP errors")
    _cache_miss_rate = _meter.create_counter("cache.miss_rate", description="Count of cache misses")
    _db_pool_usage = _meter.create_up_down_counter(
        "db.pool_usage_percent", description="Database connection pool usage percentage"
    )
    _celery_task_failures = _meter.create_counter("celery.task_failures", description="Count of failed Celery tasks")
    _celery_queue_depth = _meter.create_up_down_counter(
        "celery.queue_depth", description="Current depth of Celery task queue"
    )
    _auth_failures = _meter.create_counter("auth.failures", description="Count of authentication failures")

    if app:
        FastAPIInstrumentor.instrument_app(app)
        try:
            from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

            SQLAlchemyInstrumentor().instrument()
        except ImportError:
            pass
        try:
            from opentelemetry.instrumentation.redis import RedisInstrumentor

            RedisInstrumentor().instrument()
        except ImportError:
            pass

    logger.info("OpenTelemetry instrumentation initialized for %s", service_name)


def track_metric(name: str, value: float = 1.0, tags: dict[str, str] | None = None) -> None:
    """Track a business metric."""

    metric_map: dict[str, Counter | UpDownCounter | None] = {
        "incidents.created": _incidents_created,
        "incidents.resolved": _incidents_resolved,
        "audits.completed": _audits_completed,
        "audits.findings": _audit_findings,
        "capa.created": _capa_created,
        "capa.closed": _capa_closed,
        "complaints.created": _complaints_created,
        "risks.created": _risks_created,
        "auth.login": _auth_login,
        "auth.logout": _auth_logout,
        "documents.uploaded": _documents_uploaded,
        "workflows.completed": _workflows_completed,
        "api.error_rate_5xx": _error_rate_5xx,
        "cache.miss_rate": _cache_miss_rate,
        "db.pool_usage_percent": _db_pool_usage,
        "celery.task_failures": _celery_task_failures,
        "celery.queue_depth": _celery_queue_depth,
        "auth.failures": _auth_failures,
    }

    counter = metric_map.get(name)
    if counter:
        counter.add(int(value), attributes=tags or {})
    elif _meter:
        dynamic = _meter.create_counter(name, description=f"Dynamic metric: {name}")
        dynamic.add(int(value), attributes=tags or {})


def track_response_time(endpoint: str, duration_ms: float) -> None:
    """Record API response time."""
    if _api_response_time:
        _api_response_time.record(duration_ms, attributes={"endpoint": endpoint})


def track_query_time(query: str, duration_ms: float) -> None:
    """Record database query time."""
    if _db_query_time:
        _db_query_time.record(duration_ms, attributes={"query": query[:100]})


def track_cache_operation(hit: bool) -> None:
    """Record a cache hit or miss."""
    if _cache_hit_rate:
        _cache_hit_rate.add(1 if hit else -1, attributes={"result": "hit" if hit else "miss"})


def track_business_event(event_name: str, properties: dict[str, str] | None = None) -> None:
    """Track a business domain event as a custom metric."""
    track_metric(f"business.{event_name}", 1)
    if properties:
        logger.info("Business event: %s", event_name, extra={"event": event_name, **properties})


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer."""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer(__name__)
    return _tracer
