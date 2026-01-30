"""
API Contract Probe - Quality Governance Platform
Stage 10: Data Foundation

Validates API contracts before ETL operations.
Asserts endpoint availability, response structure, and pagination support.
"""

import json
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .config import APIConfig, EntityType


@dataclass
class EndpointProbeResult:
    """Result of probing a single endpoint."""

    endpoint: str
    method: str
    status_code: int
    success: bool
    response_time_ms: float
    checks: Dict[str, bool] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    sample_keys: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "endpoint": self.endpoint,
            "method": self.method,
            "status_code": self.status_code,
            "success": self.success,
            "response_time_ms": round(self.response_time_ms, 2),
            "checks": self.checks,
            "errors": self.errors,
            "sample_keys": self.sample_keys,
        }


@dataclass
class ProbeResult:
    """Complete probe result for all endpoints."""

    environment: str
    base_url: str
    timestamp: datetime
    all_passed: bool
    endpoints: List[EndpointProbeResult] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "environment": self.environment,
            "base_url": self.base_url,
            "timestamp": self.timestamp.isoformat(),
            "all_passed": self.all_passed,
            "summary": {
                "total": len(self.endpoints),
                "passed": sum(1 for e in self.endpoints if e.success),
                "failed": sum(1 for e in self.endpoints if not e.success),
            },
            "endpoints": [e.to_dict() for e in self.endpoints],
        }


class ContractProbe:
    """
    Probes API endpoints to verify contract compliance.

    Checks:
    - Endpoint availability (2xx or 401/403 for auth-required)
    - Response structure (items/total/page/page_size for list endpoints)
    - Pagination parameter acceptance
    """

    # Expected response keys for paginated list endpoints
    PAGINATION_KEYS = {"items", "total", "page", "page_size"}

    # Endpoints to probe with expected behavior
    ENDPOINTS = {
        EntityType.INCIDENT: {
            "path": "/api/v1/incidents",
            "method": "GET",
            "auth_required": True,
            "paginated": True,
        },
        EntityType.COMPLAINT: {
            "path": "/api/v1/complaints/",
            "method": "GET",
            "auth_required": True,
            "paginated": True,
        },
        EntityType.RTA: {
            "path": "/api/v1/rtas/",
            "method": "GET",
            "auth_required": True,
            "paginated": True,
        },
    }

    def __init__(self, config: APIConfig):
        self.config = config
        # Create SSL context that doesn't verify (for staging with self-signed certs)
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.config.auth_token:
            headers["Authorization"] = f"Bearer {self.config.auth_token}"
        return headers

    def _make_request(
        self,
        url: str,
        method: str = "GET",
    ) -> tuple:
        """Make HTTP request and return (status, body, elapsed_ms)."""
        import time

        headers = self._build_headers()
        request = urllib.request.Request(url, headers=headers, method=method)

        start = time.time()
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.config.timeout_seconds,
                context=self._ssl_context,
            ) as response:
                elapsed = (time.time() - start) * 1000
                body = json.loads(response.read().decode("utf-8"))
                return response.status, body, elapsed
        except urllib.error.HTTPError as e:
            elapsed = (time.time() - start) * 1000
            try:
                body = json.loads(e.read().decode("utf-8"))
            except Exception:
                body = {"error": str(e.reason)}
            return e.code, body, elapsed
        except urllib.error.URLError as e:
            elapsed = (time.time() - start) * 1000
            return 0, {"error": f"Connection error: {e.reason}"}, elapsed
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            return 0, {"error": str(e)}, elapsed

    def probe_endpoint(
        self,
        entity_type: EntityType,
    ) -> EndpointProbeResult:
        """Probe a single entity endpoint."""
        endpoint_config = self.ENDPOINTS.get(entity_type)
        if not endpoint_config:
            return EndpointProbeResult(
                endpoint="unknown",
                method="GET",
                status_code=0,
                success=False,
                response_time_ms=0,
                errors=[f"Unknown entity type: {entity_type}"],
            )

        path = endpoint_config["path"]
        url = f"{self.config.base_url}{path}"

        # Add pagination params
        url_with_params = f"{url}?page=1&page_size=10"

        status, body, elapsed = self._make_request(url_with_params, "GET")

        result = EndpointProbeResult(
            endpoint=path,
            method="GET",
            status_code=status,
            success=False,
            response_time_ms=elapsed,
        )

        # Check 1: Status code
        if endpoint_config["auth_required"] and not self.config.auth_token:
            # Without auth, expect 401/403
            result.checks["auth_enforcement"] = status in (401, 403)
            if status in (401, 403):
                result.success = True  # Expected behavior without token
                return result
            else:
                result.errors.append(f"Expected 401/403 without auth, got {status}")
        else:
            # With auth, expect 200
            result.checks["status_ok"] = status == 200
            if status != 200:
                result.errors.append(f"Expected 200, got {status}")
                return result

        # Check 2: Response structure for paginated endpoints
        if endpoint_config["paginated"] and isinstance(body, dict):
            has_items = "items" in body
            has_total = "total" in body
            has_page = "page" in body
            has_page_size = "page_size" in body

            result.checks["has_items"] = has_items
            result.checks["has_total"] = has_total
            result.checks["has_page"] = has_page
            result.checks["has_page_size"] = has_page_size

            if not has_items:
                result.errors.append("Missing 'items' key in response")
            if not has_total:
                result.errors.append("Missing 'total' key in response")

            # Record sample keys from items
            if has_items and isinstance(body["items"], list) and len(body["items"]) > 0:
                result.sample_keys = list(body["items"][0].keys())

        # Final success check
        result.success = len(result.errors) == 0 and all(result.checks.values())

        return result

    def probe_all(self, environment_name: str) -> ProbeResult:
        """Probe all entity endpoints."""
        results = []

        for entity_type in EntityType:
            result = self.probe_endpoint(entity_type)
            results.append(result)

        all_passed = all(r.success for r in results)

        return ProbeResult(
            environment=environment_name,
            base_url=self.config.base_url,
            timestamp=datetime.utcnow(),
            all_passed=all_passed,
            endpoints=results,
        )

    def probe_health(self) -> EndpointProbeResult:
        """Probe health endpoint (no auth required)."""
        url = f"{self.config.base_url}/health"
        status, body, elapsed = self._make_request(url, "GET")

        result = EndpointProbeResult(
            endpoint="/health",
            method="GET",
            status_code=status,
            success=status == 200,
            response_time_ms=elapsed,
        )

        if status == 200:
            result.checks["health_ok"] = body.get("status") == "ok"
        else:
            result.errors.append(f"Health check failed with status {status}")

        return result


def run_contract_probe(env_name: str = "staging") -> ProbeResult:
    """
    Run contract probe against specified environment.

    Args:
        env_name: Environment to probe (development, staging, production)

    Returns:
        ProbeResult with all endpoint checks
    """
    from .config import get_config

    config = get_config(env_name)
    probe = ContractProbe(config.api_config)

    # First check health
    health_result = probe.probe_health()

    # Then probe all entity endpoints
    result = probe.probe_all(env_name)

    # Add health result
    result.endpoints.insert(0, health_result)
    result.all_passed = result.all_passed and health_result.success

    return result


if __name__ == "__main__":
    import sys

    env = sys.argv[1] if len(sys.argv) > 1 else "staging"
    result = run_contract_probe(env)

    print(json.dumps(result.to_dict(), indent=2))
    sys.exit(0 if result.all_passed else 1)
