"""OpenTelemetry instrumentation and Azure Monitor integration."""

import logging
import os
from typing import Any

from opentelemetry import metrics, trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.metrics import Counter, Histogram, UpDownCounter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

logger = logging.getLogger(__name__)

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


def setup_telemetry(app: Any = None, service_name: str = "quality-governance-platform") -> None:
    """Initialize OpenTelemetry with tracing and metrics."""
    global _tracer, _meter
    global _incidents_created, _incidents_resolved
    global _audits_completed, _audit_findings
    global _api_response_time, _db_query_time, _cache_hit_rate

    resource = Resource.create(
        {
            "service.name": service_name,
            "service.version": os.getenv("APP_VERSION", "1.0.0"),
            "deployment.environment": os.getenv("ENVIRONMENT", "development"),
        }
    )

    tracer_provider = TracerProvider(resource=resource)

    connection_string = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING")
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
    global _incidents_created, _incidents_resolved, _audits_completed, _audit_findings

    metric_map: dict[str, Counter | None] = {
        "incidents.created": _incidents_created,
        "incidents.resolved": _incidents_resolved,
        "audits.completed": _audits_completed,
        "audits.findings": _audit_findings,
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


def get_tracer() -> trace.Tracer:
    """Get the OpenTelemetry tracer."""
    global _tracer
    if _tracer is None:
        _tracer = trace.get_tracer(__name__)
    return _tracer
