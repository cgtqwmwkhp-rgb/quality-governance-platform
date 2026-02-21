# ADR-0010: OpenTelemetry Instrumentation with Azure Monitor Export

**Status:** Accepted
**Date:** 2026-02-21
**Authors:** Platform Engineering Team

## Context

Operating a multi-tenant compliance platform in production requires comprehensive observability to detect issues, diagnose root causes, and measure system health. Without structured telemetry, debugging production incidents relies on log searching, performance bottlenecks go undetected, and capacity planning lacks data. The platform needs traces, metrics, and structured logs that integrate with our Azure cloud infrastructure.

## Decision

We adopt the OpenTelemetry SDK as the vendor-agnostic instrumentation layer. Auto-instrumentation is enabled for FastAPI (HTTP traces), SQLAlchemy (database query spans), and Redis (cache operation spans). Custom business metrics are recorded for key domain events: incident creation rates, audit completion rates, CAPA lifecycle transitions, risk score distributions, and authentication events. All telemetry is exported to Azure Monitor via the Azure Monitor OpenTelemetry exporter.

## Consequences

### Positive
- Vendor-agnostic instrumentation — can switch from Azure Monitor to any OTLP-compatible backend
- Auto-instrumentation provides immediate visibility into HTTP, database, and cache performance
- Business metrics enable data-driven capacity planning and SLA monitoring
- Distributed tracing correlates requests across API, Celery workers, and database

### Negative
- OpenTelemetry SDK adds a small memory and CPU overhead to every request
- Azure Monitor ingestion costs scale with telemetry volume — may need sampling at high traffic
- Developers must maintain custom metric definitions as new features are added

### Neutral
- PII scrubbing is applied to all telemetry attributes before export
- Sampling rate is configurable per environment (100% in staging, configurable in production)
- Dashboard and alert configuration is managed separately in Azure Monitor
