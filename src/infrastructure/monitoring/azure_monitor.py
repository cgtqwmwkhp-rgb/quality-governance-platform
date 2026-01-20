"""
Azure Monitor & Application Insights Integration

Features:
- Centralized logging to Azure Log Analytics
- Application Insights APM
- Custom metrics and traces
- Exception tracking
- Dependency tracking
- Request/response logging
"""

import json
import logging
import os
import sys
import time
import traceback
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Optional
from uuid import uuid4

from fastapi import Request, Response

# ============================================================================
# Configuration
# ============================================================================


class MonitoringConfig:
    """Azure Monitor configuration."""
    
    INSTRUMENTATION_KEY = os.getenv("APPINSIGHTS_INSTRUMENTATIONKEY", "")
    CONNECTION_STRING = os.getenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "")
    LOG_ANALYTICS_WORKSPACE_ID = os.getenv("LOG_ANALYTICS_WORKSPACE_ID", "")
    LOG_ANALYTICS_KEY = os.getenv("LOG_ANALYTICS_KEY", "")
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    SERVICE_NAME = "quality-governance-platform"
    SERVICE_VERSION = os.getenv("SERVICE_VERSION", "1.0.0")


# ============================================================================
# Structured Logger
# ============================================================================


class StructuredLogger:
    """
    Structured logging with Azure Monitor integration.
    Outputs JSON-formatted logs for easy parsing by Azure Log Analytics.
    """
    
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(name)
        self._setup_handlers()
        self._correlation_id: Optional[str] = None
    
    def _setup_handlers(self):
        """Configure logging handlers."""
        if not self.logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JsonFormatter())
            self.logger.addHandler(handler)
            self.logger.setLevel(logging.INFO)
    
    def set_correlation_id(self, correlation_id: str):
        """Set correlation ID for request tracing."""
        self._correlation_id = correlation_id
    
    def _create_log_entry(
        self,
        level: str,
        message: str,
        extra: Optional[dict] = None,
    ) -> dict:
        """Create structured log entry."""
        entry = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": level,
            "logger": self.name,
            "message": message,
            "service": MonitoringConfig.SERVICE_NAME,
            "version": MonitoringConfig.SERVICE_VERSION,
            "environment": MonitoringConfig.ENVIRONMENT,
        }
        
        if self._correlation_id:
            entry["correlationId"] = self._correlation_id
        
        if extra:
            entry["properties"] = extra
        
        return entry
    
    def info(self, message: str, **extra):
        """Log info message."""
        self.logger.info(json.dumps(self._create_log_entry("INFO", message, extra)))
    
    def warning(self, message: str, **extra):
        """Log warning message."""
        self.logger.warning(json.dumps(self._create_log_entry("WARNING", message, extra)))
    
    def error(self, message: str, exception: Optional[Exception] = None, **extra):
        """Log error message with optional exception."""
        if exception:
            extra["exception"] = {
                "type": type(exception).__name__,
                "message": str(exception),
                "stackTrace": traceback.format_exc(),
            }
        self.logger.error(json.dumps(self._create_log_entry("ERROR", message, extra)))
    
    def critical(self, message: str, exception: Optional[Exception] = None, **extra):
        """Log critical message."""
        if exception:
            extra["exception"] = {
                "type": type(exception).__name__,
                "message": str(exception),
                "stackTrace": traceback.format_exc(),
            }
        self.logger.critical(json.dumps(self._create_log_entry("CRITICAL", message, extra)))
    
    def debug(self, message: str, **extra):
        """Log debug message."""
        self.logger.debug(json.dumps(self._create_log_entry("DEBUG", message, extra)))
    
    def audit(self, action: str, resource: str, user_id: Optional[int] = None, **extra):
        """Log audit event."""
        extra["audit"] = {
            "action": action,
            "resource": resource,
            "userId": user_id,
        }
        self.logger.info(json.dumps(self._create_log_entry("AUDIT", f"Audit: {action} on {resource}", extra)))


class JsonFormatter(logging.Formatter):
    """JSON log formatter."""
    
    def format(self, record: logging.LogRecord) -> str:
        if isinstance(record.msg, str):
            try:
                # Check if already JSON
                json.loads(record.msg)
                return record.msg
            except json.JSONDecodeError:
                pass
        
        return json.dumps({
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        })


# ============================================================================
# Application Insights Client
# ============================================================================


class ApplicationInsightsClient:
    """
    Application Insights telemetry client.
    Tracks requests, dependencies, exceptions, and custom events.
    """
    
    def __init__(self):
        self.instrumentation_key = MonitoringConfig.INSTRUMENTATION_KEY
        self.connection_string = MonitoringConfig.CONNECTION_STRING
        self._client = None
        self._initialized = False
        self._init_client()
    
    def _init_client(self):
        """Initialize Application Insights client."""
        if not self.instrumentation_key and not self.connection_string:
            return
        
        try:
            from opencensus.ext.azure import metrics_exporter
            from opencensus.ext.azure.log_exporter import AzureLogHandler
            from opencensus.ext.azure.trace_exporter import AzureExporter
            from opencensus.trace import config_integration
            from opencensus.trace.samplers import ProbabilitySampler
            from opencensus.trace.tracer import Tracer
            
            # Configure integrations
            config_integration.trace_integrations(["requests", "sqlalchemy"])
            
            # Create exporter
            connection = self.connection_string or f"InstrumentationKey={self.instrumentation_key}"
            self._exporter = AzureExporter(connection_string=connection)
            
            # Create tracer
            self._tracer = Tracer(
                exporter=self._exporter,
                sampler=ProbabilitySampler(1.0),  # Sample 100% in production
            )
            
            self._initialized = True
            
        except ImportError:
            # opencensus not installed
            pass
    
    def track_request(
        self,
        name: str,
        url: str,
        success: bool,
        duration_ms: float,
        response_code: int,
        properties: Optional[dict] = None,
    ):
        """Track HTTP request telemetry."""
        if not self._initialized:
            return
        
        try:
            from opencensus.trace import span as trace_span
            
            with self._tracer.span(name=name) as span:
                span.add_attribute("http.url", url)
                span.add_attribute("http.status_code", response_code)
                span.add_attribute("http.success", success)
                span.add_attribute("duration_ms", duration_ms)
                
                if properties:
                    for key, value in properties.items():
                        span.add_attribute(key, str(value))
        except Exception:
            pass
    
    def track_exception(
        self,
        exception: Exception,
        properties: Optional[dict] = None,
    ):
        """Track exception telemetry."""
        if not self._initialized:
            return
        
        try:
            from opencensus.trace.status import Status
            
            with self._tracer.span(name="exception") as span:
                span.status = Status(
                    code=2,  # Unknown error
                    message=str(exception),
                )
                span.add_attribute("exception.type", type(exception).__name__)
                span.add_attribute("exception.message", str(exception))
                span.add_attribute("exception.stacktrace", traceback.format_exc())
                
                if properties:
                    for key, value in properties.items():
                        span.add_attribute(key, str(value))
        except Exception:
            pass
    
    def track_dependency(
        self,
        name: str,
        dependency_type: str,
        target: str,
        success: bool,
        duration_ms: float,
        properties: Optional[dict] = None,
    ):
        """Track external dependency call."""
        if not self._initialized:
            return
        
        try:
            with self._tracer.span(name=name) as span:
                span.add_attribute("dependency.type", dependency_type)
                span.add_attribute("dependency.target", target)
                span.add_attribute("dependency.success", success)
                span.add_attribute("duration_ms", duration_ms)
                
                if properties:
                    for key, value in properties.items():
                        span.add_attribute(key, str(value))
        except Exception:
            pass
    
    def track_event(
        self,
        name: str,
        properties: Optional[dict] = None,
        measurements: Optional[dict] = None,
    ):
        """Track custom event."""
        if not self._initialized:
            return
        
        try:
            with self._tracer.span(name=name) as span:
                span.add_attribute("event.name", name)
                
                if properties:
                    for key, value in properties.items():
                        span.add_attribute(f"custom.{key}", str(value))
                
                if measurements:
                    for key, value in measurements.items():
                        span.add_attribute(f"metric.{key}", value)
        except Exception:
            pass
    
    def track_metric(
        self,
        name: str,
        value: float,
        properties: Optional[dict] = None,
    ):
        """Track custom metric."""
        if not self._initialized:
            return
        
        try:
            # Would use metrics exporter here
            pass
        except Exception:
            pass


# ============================================================================
# Middleware
# ============================================================================


async def monitoring_middleware(request: Request, call_next: Callable) -> Response:
    """
    FastAPI middleware for request monitoring.
    
    Tracks:
    - Request duration
    - Response status codes
    - Correlation IDs
    - Request/response details
    """
    # Generate correlation ID
    correlation_id = request.headers.get("X-Correlation-ID", str(uuid4()))
    
    # Create logger for this request
    logger = StructuredLogger("http.request")
    logger.set_correlation_id(correlation_id)
    
    # Start timing
    start_time = time.time()
    
    # Log request
    logger.info(
        f"Request started: {request.method} {request.url.path}",
        method=request.method,
        path=request.url.path,
        query=str(request.query_params),
        userAgent=request.headers.get("User-Agent", ""),
        clientIP=request.client.host if request.client else "",
    )
    
    try:
        # Process request
        response = await call_next(request)
        
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log response
        logger.info(
            f"Request completed: {response.status_code}",
            statusCode=response.status_code,
            durationMs=round(duration_ms, 2),
        )
        
        # Track in Application Insights
        app_insights = ApplicationInsightsClient()
        app_insights.track_request(
            name=f"{request.method} {request.url.path}",
            url=str(request.url),
            success=response.status_code < 400,
            duration_ms=duration_ms,
            response_code=response.status_code,
            properties={
                "correlationId": correlation_id,
                "method": request.method,
                "path": request.url.path,
            },
        )
        
        # Add correlation ID to response
        response.headers["X-Correlation-ID"] = correlation_id
        
        return response
        
    except Exception as e:
        # Calculate duration
        duration_ms = (time.time() - start_time) * 1000
        
        # Log error
        logger.error(
            f"Request failed: {str(e)}",
            exception=e,
            durationMs=round(duration_ms, 2),
        )
        
        # Track exception
        app_insights = ApplicationInsightsClient()
        app_insights.track_exception(
            exception=e,
            properties={
                "correlationId": correlation_id,
                "method": request.method,
                "path": request.url.path,
            },
        )
        
        raise


# ============================================================================
# Decorators
# ============================================================================


def track_dependency(
    dependency_type: str = "HTTP",
    name: Optional[str] = None,
):
    """
    Decorator to track function as a dependency call.
    
    Usage:
        @track_dependency(dependency_type="SQL", name="get_user")
        async def get_user_from_db(user_id: int):
            ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            dep_name = name or func.__name__
            start_time = time.time()
            success = True
            
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                duration_ms = (time.time() - start_time) * 1000
                app_insights = ApplicationInsightsClient()
                app_insights.track_dependency(
                    name=dep_name,
                    dependency_type=dependency_type,
                    target=func.__module__,
                    success=success,
                    duration_ms=duration_ms,
                )
        
        return wrapper
    return decorator


def track_event_decorator(event_name: str):
    """
    Decorator to track function execution as a custom event.
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000
                
                app_insights = ApplicationInsightsClient()
                app_insights.track_event(
                    name=event_name,
                    properties={
                        "function": func.__name__,
                        "module": func.__module__,
                    },
                    measurements={
                        "durationMs": duration_ms,
                    },
                )
                
                return result
            except Exception as e:
                app_insights = ApplicationInsightsClient()
                app_insights.track_exception(
                    exception=e,
                    properties={
                        "event": event_name,
                        "function": func.__name__,
                    },
                )
                raise
        
        return wrapper
    return decorator


@contextmanager
def track_operation(operation_name: str):
    """
    Context manager for tracking operations.
    
    Usage:
        with track_operation("process_report"):
            # ... operation code ...
    """
    logger = StructuredLogger(operation_name)
    start_time = time.time()
    
    logger.info(f"Operation started: {operation_name}")
    
    try:
        yield logger
        duration_ms = (time.time() - start_time) * 1000
        logger.info(
            f"Operation completed: {operation_name}",
            durationMs=round(duration_ms, 2),
        )
    except Exception as e:
        duration_ms = (time.time() - start_time) * 1000
        logger.error(
            f"Operation failed: {operation_name}",
            exception=e,
            durationMs=round(duration_ms, 2),
        )
        raise


# ============================================================================
# Health Checks
# ============================================================================


def get_monitoring_health() -> dict:
    """Get monitoring system health status."""
    return {
        "appInsights": {
            "configured": bool(MonitoringConfig.INSTRUMENTATION_KEY or MonitoringConfig.CONNECTION_STRING),
            "instrumentationKey": MonitoringConfig.INSTRUMENTATION_KEY[:8] + "..." if MonitoringConfig.INSTRUMENTATION_KEY else None,
        },
        "logAnalytics": {
            "configured": bool(MonitoringConfig.LOG_ANALYTICS_WORKSPACE_ID),
        },
        "environment": MonitoringConfig.ENVIRONMENT,
        "serviceVersion": MonitoringConfig.SERVICE_VERSION,
    }


# ============================================================================
# Global Logger Instance
# ============================================================================


# Create default logger
logger = StructuredLogger("qgp")
