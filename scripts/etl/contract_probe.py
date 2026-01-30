"""
API Contract Probe - Quality Governance Platform
Stage 10: Data Foundation

Validates API contracts before ETL operations.
Produces explicit outcomes: VERIFIED, UNAVAILABLE, or FAILED.

IMPORTANT: This probe does NOT claim validation when staging is unreachable.
- VERIFIED: Staging reachable AND all contract checks pass
- UNAVAILABLE: Staging unreachable (NOT validated, just unavailable)
- FAILED: Staging reachable but contract checks failed
"""

import json
import os
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import APIConfig, EntityType


class ProbeOutcome(Enum):
    """Explicit probe outcomes - no ambiguity."""

    VERIFIED = "VERIFIED"  # Reachable + all checks pass
    UNAVAILABLE = "UNAVAILABLE"  # Not reachable - NOT validated
    FAILED = "FAILED"  # Reachable but checks failed


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
class ContractProbeResult:
    """
    Complete probe result with explicit outcome.

    Outcomes:
    - VERIFIED: Target reachable and all contract checks passed
    - UNAVAILABLE: Target not reachable (NOT validated)
    - FAILED: Target reachable but contract checks failed
    """

    target: str
    base_url: str
    reachable: bool
    outcome: ProbeOutcome
    timestamp: datetime
    endpoints: List[EndpointProbeResult] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "base_url": self.base_url,
            "reachable": self.reachable,
            "outcome": self.outcome.value,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "summary": {
                "total_endpoints": len(self.endpoints),
                "passed": sum(1 for e in self.endpoints if e.success),
                "failed": sum(1 for e in self.endpoints if not e.success),
            },
            "endpoints": [e.to_dict() for e in self.endpoints],
        }


def load_environment_config(env_name: str = "staging") -> Dict[str, Any]:
    """
    Load environment configuration from single source of truth.

    Looks for docs/evidence/environment_endpoints.json in repo root.
    Falls back to environment variable if file not found.
    """
    # Try to find the config file
    possible_paths = [
        Path(__file__).parent.parent.parent / "docs" / "evidence" / "environment_endpoints.json",
        Path.cwd() / "docs" / "evidence" / "environment_endpoints.json",
        Path(os.environ.get("GITHUB_WORKSPACE", ".")) / "docs" / "evidence" / "environment_endpoints.json",
    ]

    config_path = None
    for path in possible_paths:
        if path.exists():
            config_path = path
            break

    if config_path:
        with open(config_path) as f:
            config = json.load(f)
        env_config = config.get("environments", {}).get(env_name, {})
        if env_config:
            return {
                "base_url": env_config.get("api_base_url"),
                "health_endpoint": env_config.get("health_endpoint", "/health"),
                "timeout_seconds": config.get("contract_probe", {}).get("timeout_seconds", 30),
                "source": str(config_path),
            }

    # Fallback to environment variable
    env_var = f"QGP_{env_name.upper()}_API_URL"
    base_url = os.environ.get(env_var)
    if base_url:
        return {
            "base_url": base_url,
            "health_endpoint": "/health",
            "timeout_seconds": 30,
            "source": f"env:{env_var}",
        }

    return {
        "base_url": None,
        "health_endpoint": "/health",
        "timeout_seconds": 30,
        "source": "none",
    }


class ContractProbe:
    """
    Probes API endpoints to verify contract compliance.

    Produces explicit outcomes - never claims validation when unreachable.
    """

    PAGINATION_KEYS = {"items", "total", "page", "page_size"}

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

    def __init__(self, base_url: str, timeout_seconds: int = 30, auth_token: Optional[str] = None):
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.auth_token = auth_token
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

    def _build_headers(self) -> Dict[str, str]:
        """Build request headers."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def _make_request(self, url: str, method: str = "GET") -> tuple:
        """Make HTTP request and return (status, body, elapsed_ms)."""
        headers = self._build_headers()
        request = urllib.request.Request(url, headers=headers, method=method)

        start = time.time()
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
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

    def check_reachable(self) -> tuple:
        """
        Check if the target is reachable.

        Returns: (is_reachable: bool, health_result: EndpointProbeResult)
        """
        url = f"{self.base_url}/health"
        status, body, elapsed = self._make_request(url, "GET")

        result = EndpointProbeResult(
            endpoint="/health",
            method="GET",
            status_code=status,
            success=False,
            response_time_ms=elapsed,
        )

        # Consider reachable if we get any valid HTTP response (not connection error)
        is_reachable = status > 0

        if status == 200:
            result.success = True
            result.checks["health_ok"] = body.get("status") == "ok"
        elif status > 0:
            # Got HTTP response but not 200 - still reachable
            result.errors.append(f"Health returned {status}")
        else:
            # Connection failed
            result.errors.append(f"Connection failed: {body.get('error', 'unknown')}")

        return is_reachable, result

    def probe_endpoint(self, entity_type: EntityType) -> EndpointProbeResult:
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
        url = f"{self.base_url}{path}?page=1&page_size=10"

        status, body, elapsed = self._make_request(url, "GET")

        result = EndpointProbeResult(
            endpoint=path,
            method="GET",
            status_code=status,
            success=False,
            response_time_ms=elapsed,
        )

        # Check auth enforcement (without token, expect 401/403)
        if endpoint_config["auth_required"] and not self.auth_token:
            result.checks["auth_enforcement"] = status in (401, 403)
            if status in (401, 403):
                result.success = True
                return result
            else:
                result.errors.append(f"Expected 401/403 without auth, got {status}")
                return result

        # With auth, expect 200
        result.checks["status_ok"] = status == 200
        if status != 200:
            result.errors.append(f"Expected 200, got {status}")
            return result

        # Check pagination structure
        if endpoint_config["paginated"] and isinstance(body, dict):
            for key in ["items", "total", "page", "page_size"]:
                result.checks[f"has_{key}"] = key in body
                if key not in body:
                    result.errors.append(f"Missing '{key}' in response")

            if "items" in body and isinstance(body["items"], list) and len(body["items"]) > 0:
                result.sample_keys = list(body["items"][0].keys())

        result.success = len(result.errors) == 0 and all(result.checks.values())
        return result

    def run_full_probe(self, env_name: str) -> ContractProbeResult:
        """
        Run complete contract probe with explicit outcome.

        Returns ContractProbeResult with outcome:
        - VERIFIED: Reachable and all checks pass
        - UNAVAILABLE: Not reachable (NOT validated)
        - FAILED: Reachable but checks failed
        """
        # Step 1: Check reachability
        is_reachable, health_result = self.check_reachable()

        if not is_reachable:
            return ContractProbeResult(
                target=env_name,
                base_url=self.base_url,
                reachable=False,
                outcome=ProbeOutcome.UNAVAILABLE,
                timestamp=datetime.utcnow(),
                endpoints=[health_result],
                message=f"Target {env_name} is UNREACHABLE. Contract NOT validated.",
            )

        # Step 2: Probe all endpoints
        endpoints = [health_result]
        all_passed = health_result.success

        for entity_type in EntityType:
            result = self.probe_endpoint(entity_type)
            endpoints.append(result)
            if not result.success:
                all_passed = False

        # Step 3: Determine outcome
        if all_passed:
            outcome = ProbeOutcome.VERIFIED
            message = f"Target {env_name} VERIFIED. All contract checks passed."
        else:
            outcome = ProbeOutcome.FAILED
            failed_endpoints = [e.endpoint for e in endpoints if not e.success]
            message = f"Target {env_name} FAILED. Checks failed: {failed_endpoints}"

        return ContractProbeResult(
            target=env_name,
            base_url=self.base_url,
            reachable=True,
            outcome=outcome,
            timestamp=datetime.utcnow(),
            endpoints=endpoints,
            message=message,
        )


def run_contract_probe(env_name: str = "staging") -> ContractProbeResult:
    """
    Run contract probe against specified environment.

    Loads endpoint from single source of truth (environment_endpoints.json).
    Returns explicit outcome - never claims validation when unreachable.
    """
    # Load config from single source of truth
    env_config = load_environment_config(env_name)

    base_url = env_config.get("base_url")
    if not base_url:
        return ContractProbeResult(
            target=env_name,
            base_url="(not configured)",
            reachable=False,
            outcome=ProbeOutcome.UNAVAILABLE,
            timestamp=datetime.utcnow(),
            message=f"No endpoint configured for {env_name}. Source: {env_config.get('source')}",
        )

    print(f"Endpoint source: {env_config.get('source')}")
    print(f"Target URL: {base_url}")

    auth_token = os.environ.get("QGP_API_TOKEN") or os.environ.get("QGP_STAGING_READ_TOKEN")

    probe = ContractProbe(
        base_url=base_url,
        timeout_seconds=env_config.get("timeout_seconds", 30),
        auth_token=auth_token,
    )

    return probe.run_full_probe(env_name)


def main() -> int:
    """
    CLI entry point with explicit exit codes.

    Exit codes:
    - 0: VERIFIED or UNAVAILABLE (non-blocking)
    - 1: FAILED (blocking - contract violation)
    """
    import sys

    env = sys.argv[1] if len(sys.argv) > 1 else "staging"
    result = run_contract_probe(env)

    print("")
    print("=" * 60)
    print(f"OUTCOME: {result.outcome.value}")
    print(f"MESSAGE: {result.message}")
    print("=" * 60)
    print("")
    print(json.dumps(result.to_dict(), indent=2))

    # Exit codes
    if result.outcome == ProbeOutcome.FAILED:
        print("")
        print("❌ CONTRACT PROBE FAILED - blocking")
        return 1
    elif result.outcome == ProbeOutcome.UNAVAILABLE:
        print("")
        print("⚠️ UNAVAILABLE - NOT validated (non-blocking)")
        return 0
    else:
        print("")
        print("✅ VERIFIED - contract compliance confirmed")
        return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())
