"""Alert threshold definitions for monitoring integration.

These thresholds are consumed by Azure Monitor alert rules or any
compatible alerting system. They define the conditions under which
alerts should fire.
"""

import json
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
        metric="cache.hit_rate",
        condition="less_than",
        threshold=50.0,
        window_minutes=15,
        severity=AlertSeverity.MEDIUM,
        description="Cache hit rate drops below 50% over 15 minutes",
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
    AlertRule(
        name="incident_creation_spike",
        metric="incidents.created",
        condition="gt",
        threshold=50,
        window_minutes=60,
        severity=AlertSeverity.HIGH,
        description="More than 50 incidents created in 1 hour",
    ),
    AlertRule(
        name="audit_completion_drop",
        metric="audits.completed",
        condition="lt",
        threshold=1,
        window_minutes=1440,
        severity=AlertSeverity.MEDIUM,
        description="No audits completed in 24 hours",
    ),
    AlertRule(
        name="compliance_score_drop",
        metric="compliance.score_checked",
        condition="lt",
        threshold=1,
        window_minutes=1440,
        severity=AlertSeverity.MEDIUM,
        description="No compliance checks in 24 hours",
    ),
    AlertRule(
        name="overdue_capa_count",
        metric="capa.overdue",
        condition="gt",
        threshold=10,
        window_minutes=1440,
        severity=AlertSeverity.HIGH,
        description="More than 10 overdue CAPA items",
    ),
    AlertRule(
        name="failed_signature_rate",
        metric="signatures.failed",
        condition="gt",
        threshold=5,
        window_minutes=60,
        severity=AlertSeverity.HIGH,
        description="More than 5 failed signatures in 1 hour",
    ),
    AlertRule(
        name="dlq_growth",
        metric="dlq.size",
        condition="gt",
        threshold=5,
        window_minutes=60,
        severity=AlertSeverity.HIGH,
        description="More than 5 failed tasks added to DLQ in 1 hour",
    ),
]


def get_critical_alerts() -> list[AlertRule]:
    return [r for r in ALERT_RULES if r.severity == AlertSeverity.CRITICAL]


def get_alerts_by_severity(severity: AlertSeverity) -> list[AlertRule]:
    return [r for r in ALERT_RULES if r.severity == severity]


_CONDITION_TO_OPERATOR = {
    "greater_than": "GreaterThan",
    "less_than": "LessThan",
    "greater_than_or_equal": "GreaterThanOrEqual",
    "less_than_or_equal": "LessThanOrEqual",
    "percentile_95_greater_than": "GreaterThan",
}


class AlertProvisioner:
    """Exports alert rules as Azure Monitor Bicep/ARM templates."""

    @staticmethod
    def export_arm_template(alert_rules: list[AlertRule]) -> dict:
        """Convert alert rules to ARM template format for Azure deployment."""
        resources = []
        for rule in alert_rules:
            operator = _CONDITION_TO_OPERATOR.get(rule.condition, "GreaterThan")
            resources.append(
                {
                    "type": "Microsoft.Insights/metricAlerts",
                    "apiVersion": "2018-03-01",
                    "name": rule.name,
                    "location": "global",
                    "properties": {
                        "description": rule.description,
                        "severity": rule.severity.value,
                        "enabled": True,
                        "evaluationFrequency": f"PT{rule.window_minutes}M",
                        "windowSize": f"PT{rule.window_minutes}M",
                        "criteria": {
                            "odata.type": "Microsoft.Azure.Monitor.SingleResourceMultipleMetricCriteria",
                            "allOf": [
                                {
                                    "name": f"{rule.name}_condition",
                                    "metricName": rule.metric,
                                    "operator": operator,
                                    "threshold": rule.threshold,
                                    "timeAggregation": "Average",
                                }
                            ],
                        },
                    },
                }
            )
        return {
            "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
            "contentVersion": "1.0.0.0",
            "resources": resources,
        }

    @staticmethod
    def export_to_file(
        alert_rules: list[AlertRule],
        output_path: str = "infrastructure/alerts.json",
    ) -> str:
        """Export alert rules to a JSON file for deployment."""
        template = AlertProvisioner.export_arm_template(alert_rules)
        with open(output_path, "w") as f:
            json.dump(template, f, indent=2)
        return output_path
