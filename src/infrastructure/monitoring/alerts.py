"""Alert threshold definitions for monitoring integration.

These thresholds are consumed by Azure Monitor alert rules or any
compatible alerting system. They define the conditions under which
alerts should fire.
"""

from dataclasses import dataclass, field
from enum import Enum


class AlertSeverity(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass
class AlertRule:
    name: str
    metric: str
    condition: str
    threshold: float
    window_minutes: int
    severity: AlertSeverity
    description: str
    runbook_url: str = ""


ALERT_RULES: list[AlertRule] = [
    AlertRule(
        name="high_error_rate",
        metric="api.error_rate_5xx",
        condition="greater_than",
        threshold=5.0,
        window_minutes=5,
        severity=AlertSeverity.CRITICAL,
        description="5xx error rate exceeds 5% over 5 minutes",
    ),
    AlertRule(
        name="high_latency_p95",
        metric="api.response_time_ms",
        condition="percentile_95_greater_than",
        threshold=2000,
        window_minutes=10,
        severity=AlertSeverity.HIGH,
        description="P95 response time exceeds 2 seconds for 10 minutes",
    ),
    AlertRule(
        name="celery_queue_depth",
        metric="celery.queue_depth",
        condition="greater_than",
        threshold=100,
        window_minutes=5,
        severity=AlertSeverity.HIGH,
        description="Celery task queue exceeds 100 pending tasks",
    ),
    AlertRule(
        name="cache_miss_rate",
        metric="cache.miss_rate",
        condition="greater_than",
        threshold=50.0,
        window_minutes=15,
        severity=AlertSeverity.MEDIUM,
        description="Cache miss rate exceeds 50% over 15 minutes",
    ),
    AlertRule(
        name="db_pool_exhaustion",
        metric="db.pool_usage_percent",
        condition="greater_than",
        threshold=80.0,
        window_minutes=5,
        severity=AlertSeverity.CRITICAL,
        description="Database connection pool usage exceeds 80%",
    ),
    AlertRule(
        name="auth_failure_spike",
        metric="auth.failures",
        condition="greater_than",
        threshold=50,
        window_minutes=5,
        severity=AlertSeverity.HIGH,
        description="Authentication failures exceed 50 in 5 minutes",
    ),
    AlertRule(
        name="disk_usage_high",
        metric="system.disk_usage_percent",
        condition="greater_than",
        threshold=85.0,
        window_minutes=30,
        severity=AlertSeverity.MEDIUM,
        description="Disk usage exceeds 85%",
    ),
]


def get_critical_alerts() -> list[AlertRule]:
    return [r for r in ALERT_RULES if r.severity == AlertSeverity.CRITICAL]


def get_alerts_by_severity(severity: AlertSeverity) -> list[AlertRule]:
    return [r for r in ALERT_RULES if r.severity == severity]
