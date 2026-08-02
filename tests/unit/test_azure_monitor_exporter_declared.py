"""C-33: Azure Monitor OTel exporter must be declared so setup_telemetry can export.

Connection string alone is not enough — without the Azure Monitor exporter,
setup_telemetry catches ImportError and silently runs with no exporter.
"""

from importlib import metadata
from pathlib import Path

import pytest


def test_azure_monitor_exporter_is_declared_in_requirements():
    req = Path("requirements.txt").read_text(encoding="utf-8")
    assert "azure-monitor-opentelemetry-exporter" in req


def test_azure_monitor_trace_exporter_imports_when_installed():
    try:
        metadata.version("azure-monitor-opentelemetry-exporter")
    except metadata.PackageNotFoundError:
        pytest.skip("exporter not installed in this environment")
    from azure.monitor.opentelemetry.exporter import AzureMonitorMetricExporter, AzureMonitorTraceExporter  # noqa: F401
