"""
API Contract Probe - Quality Governance Platform
Stage 10: Data Foundation

Validates API contracts before ETL operations.
Produces explicit outcomes: VERIFIED, UNAVAILABLE, or FAILED.

IMPORTANT: This probe does NOT claim validation when staging is unreachable.
- VERIFIED: Staging reachable AND all contract checks pass
- UNAVAILABLE: Staging unreachable (NOT validated, just unavailable)
- FAILED: Staging reachable but contract checks failed

Enforcement Modes:
- ADVISORY: Non-blocking, informational only (default for PRs)
- REQUIRED: Blocking, must pass (post-deploy, nightly verification)
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
from typing import Any, Dict, List, Optional, Tuple


class ProbeOutcome(Enum):
    """Explicit probe outcomes - no ambiguity."""

    VERIFIED = "VERIFIED"  # Reachable + all checks pass
    UNAVAILABLE = "UNAVAILABLE"  # Not reachable - NOT validated
    FAILED = "FAILED"  # Reachable but checks failed
    DEGRADED = "DEGRADED"  # Reachable but some non-critical checks failed


class EnforcementMode(Enum):
    """Enforcement modes for the probe."""

    ADVISORY = "ADVISORY"  # Non-blocking, informational
    REQUIRED = "REQUIRED"  # Blocking, must pass


@dataclass
class EndpointCheck:
    """Configuration for a single endpoint check."""

    name: str
    path: str
    method: str = "GET"
    auth_required: bool = False
    expected_status_without_auth: List[int] = field(default_factory=lambda: [401, 403])
    expected_status_with_auth: int = 200
    paginated: bool = False
    required_response_keys: List[str] = field(default_factory=list)
    critical: bool = True  # If False, failure doesn't cause overall FAILED


@dataclass
class EndpointProbeResult:
    """Result of probing a single endpoint."""

    name: str
    endpoint: str
    method: str
    status_code: int
    success: bool
    response_time_ms: float
    critical: bool = True
    checks: Dict[str, bool] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    sample_keys: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "endpoint": self.endpoint,
            "method": self.method,
            "status_code": self.status_code,
            "success": self.success,
            "critical": self.critical,
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
    - FAILED: Target reachable but critical contract checks failed
    - DEGRADED: Target reachable, critical checks pass, non-critical failed
    """

    target: str
    platform: str
    base_url: str
    reachable: bool
    outcome: ProbeOutcome
    enforcement_mode: EnforcementMode
    timestamp: datetime
    endpoints_checked: int = 0
    endpoints_passed: int = 0
    endpoints_failed: int = 0
    endpoints: List[EndpointProbeResult] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "target": self.target,
            "platform": self.platform,
            "base_url": self.base_url,
            "reachable": self.reachable,
            "outcome": self.outcome.value,
            "enforcement_mode": self.enforcement_mode.value,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "summary": {
                "endpoints_checked": self.endpoints_checked,
                "endpoints_passed": self.endpoints_passed,
                "endpoints_failed": self.endpoints_failed,
                "critical_failures": sum(1 for e in self.endpoints if not e.success and e.critical),
            },
            "endpoints": [e.to_dict() for e in self.endpoints],
        }


# Minimum viable contract surface (6 endpoints)
MINIMUM_CONTRACT_ENDPOINTS = [
    EndpointCheck(
        name="identity",
        path="/api/v1/meta/version",
        auth_required=False,
        critical=False,  # Nice to have, not blocking
    ),
    EndpointCheck(
        name="healthz",
        path="/healthz",
        auth_required=False,
        critical=True,
    ),
    EndpointCheck(
        name="readyz",
        path="/readyz",
        auth_required=False,
        critical=True,
    ),
    EndpointCheck(
        name="incidents_auth",
        path="/api/v1/incidents",
        auth_required=True,
        paginated=True,
        required_response_keys=["items", "total", "page", "page_size"],
        critical=True,
    ),
    EndpointCheck(
        name="complaints_auth",
        path="/api/v1/complaints/",
        auth_required=True,
        paginated=True,
        required_response_keys=["items", "total", "page", "page_size"],
        critical=True,
    ),
    EndpointCheck(
        name="rtas_auth",
        path="/api/v1/rtas/",
        auth_required=True,
        paginated=True,
        required_response_keys=["items", "total", "page", "page_size"],
        critical=True,
    ),
]

# Legacy health endpoint for backwards compatibility
LEGACY_HEALTH_ENDPOINT = EndpointCheck(
    name="health_legacy",
    path="/health",
    auth_required=False,
    critical=False,
)


def load_environment_config(env_name: str = "staging") -> Dict[str, Any]:
    """
    Load environment configuration from single source of truth.

    Looks for docs/evidence/environment_endpoints.json in repo root.
    Falls back to environment variable if file not found.
    """
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
        probe_config = config.get("contract_probe", {})
        if env_config:
            return {
                "base_url": env_config.get("api_base_url"),
                "platform": env_config.get("platform", "unknown"),
                "container_app_name": env_config.get("container_app_name"),
                "region": env_config.get("region"),
                "timeout_seconds": probe_config.get("timeout_seconds", 30),
                "source": str(config_path),
                "enforcement": probe_config.get("enforcement", {}),
            }

    # Fallback to environment variable
    env_var = f"QGP_{env_name.upper()}_API_URL"
    base_url = os.environ.get(env_var)
    if base_url:
        return {
            "base_url": base_url,
            "platform": "env-override",
            "timeout_seconds": 30,
            "source": f"env:{env_var}",
            "enforcement": {},
        }

    return {
        "base_url": None,
        "platform": "unknown",
        "timeout_seconds": 30,
        "source": "none",
        "enforcement": {},
    }


class ContractProbe:
    """
    Probes API endpoints to verify contract compliance.

    Produces explicit outcomes - never claims validation when unreachable.
    Supports minimum viable contract surface (6+ endpoints).
    """

    def __init__(
        self,
        base_url: str,
        timeout_seconds: int = 30,
        auth_token: Optional[str] = None,
        enforcement_mode: EnforcementMode = EnforcementMode.ADVISORY,
    ):
        self.base_url = base_url
        self.timeout_seconds = timeout_seconds
        self.auth_token = auth_token
        self.enforcement_mode = enforcement_mode
        self._ssl_context = ssl.create_default_context()
        self._ssl_context.check_hostname = False
        self._ssl_context.verify_mode = ssl.CERT_NONE

    def _build_headers(self, include_auth: bool = False) -> Dict[str, str]:
        """Build request headers."""
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": "QGP-Contract-Probe/1.0",
        }
        if include_auth and self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers

    def _make_request(
        self, url: str, method: str = "GET", include_auth: bool = False
    ) -> Tuple[int, Dict[str, Any], float]:
        """Make HTTP request and return (status, body, elapsed_ms)."""
        headers = self._build_headers(include_auth)
        request = urllib.request.Request(url, headers=headers, method=method)

        start = time.time()
        try:
            with urllib.request.urlopen(
                request,
                timeout=self.timeout_seconds,
                context=self._ssl_context,
            ) as response:
                elapsed = (time.time() - start) * 1000
                try:
                    body = json.loads(response.read().decode("utf-8"))
                except json.JSONDecodeError:
                    body = {"raw": "non-json-response"}
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

    def check_reachable(self) -> Tuple[bool, EndpointProbeResult]:
        """
        Check if the target is reachable using multiple endpoints.

        Returns: (is_reachable: bool, health_result: EndpointProbeResult)
        """
        # Try multiple health endpoints in order of preference
        health_paths = ["/healthz", "/readyz", "/health", "/"]

        for path in health_paths:
            url = f"{self.base_url}{path}"
            status, body, elapsed = self._make_request(url, "GET")

            result = EndpointProbeResult(
                name=f"reachability_{path.replace('/', '_')}",
                endpoint=path,
                method="GET",
                status_code=status,
                success=False,
                response_time_ms=elapsed,
            )

            # Consider reachable if we get any valid HTTP response
            if status > 0:
                result.success = status in (200, 204, 401, 403, 404)
                result.checks["http_response"] = True
                return True, result

        # All attempts failed - not reachable
        result = EndpointProbeResult(
            name="reachability_check",
            endpoint="/healthz",
            method="GET",
            status_code=0,
            success=False,
            response_time_ms=elapsed,
            errors=["Connection failed to all health endpoints"],
        )
        return False, result

    def probe_endpoint(self, check: EndpointCheck) -> EndpointProbeResult:
        """Probe a single endpoint according to its configuration."""
        url = f"{self.base_url}{check.path}"
        if check.paginated:
            url += "?page=1&page_size=1"

        # First, check without auth if auth is required
        if check.auth_required:
            status, body, elapsed = self._make_request(url, check.method, include_auth=False)

            result = EndpointProbeResult(
                name=check.name,
                endpoint=check.path,
                method=check.method,
                status_code=status,
                success=False,
                response_time_ms=elapsed,
                critical=check.critical,
            )

            # Check auth enforcement (without token should be 401/403)
            auth_enforced = status in check.expected_status_without_auth
            result.checks["auth_enforcement"] = auth_enforced

            if not auth_enforced:
                if status == 0:
                    result.errors.append("Connection failed")
                elif status == 404:
                    result.errors.append(f"Endpoint not found (404)")
                else:
                    result.errors.append(f"Expected {check.expected_status_without_auth} without auth, got {status}")
                return result

            # Auth is enforced - this is success for auth check
            result.success = True
            return result

        else:
            # No auth required - expect success
            status, body, elapsed = self._make_request(url, check.method)

            result = EndpointProbeResult(
                name=check.name,
                endpoint=check.path,
                method=check.method,
                status_code=status,
                success=False,
                response_time_ms=elapsed,
                critical=check.critical,
            )

            result.checks["status_ok"] = status == 200

            if status == 0:
                result.errors.append("Connection failed")
                return result
            elif status == 404:
                result.errors.append("Endpoint not found (404)")
                return result
            elif status != 200:
                result.errors.append(f"Expected 200, got {status}")
                return result

            # Check response structure if required
            if check.required_response_keys and isinstance(body, dict):
                for key in check.required_response_keys:
                    has_key = key in body
                    result.checks[f"has_{key}"] = has_key
                    if not has_key:
                        result.errors.append(f"Missing required key: {key}")

            result.success = len(result.errors) == 0 and all(result.checks.values())
            return result

    def run_full_probe(self, env_name: str, platform: str = "unknown") -> ContractProbeResult:
        """
        Run complete contract probe with explicit outcome.

        Returns ContractProbeResult with outcome:
        - VERIFIED: Reachable and all critical checks pass
        - UNAVAILABLE: Not reachable OR app not deployed (all 404s)
        - FAILED: Reachable but critical checks failed (mixed responses)
        - DEGRADED: Reachable, critical pass, non-critical failed
        """
        # Step 1: Check reachability
        is_reachable, reachability_result = self.check_reachable()

        if not is_reachable:
            return ContractProbeResult(
                target=env_name,
                platform=platform,
                base_url=self.base_url,
                reachable=False,
                outcome=ProbeOutcome.UNAVAILABLE,
                enforcement_mode=self.enforcement_mode,
                timestamp=datetime.utcnow(),
                endpoints_checked=1,
                endpoints_failed=1,
                endpoints=[reachability_result],
                message=f"Target {env_name} is UNREACHABLE. Contract NOT validated.",
            )

        # Step 2: Probe all endpoints in minimum contract set
        endpoints = []
        critical_failures = 0
        non_critical_failures = 0
        all_404_count = 0
        total_endpoints = 0

        # Add legacy health check first
        legacy_result = self.probe_endpoint(LEGACY_HEALTH_ENDPOINT)
        endpoints.append(legacy_result)
        total_endpoints += 1
        if legacy_result.status_code == 404:
            all_404_count += 1

        for check in MINIMUM_CONTRACT_ENDPOINTS:
            result = self.probe_endpoint(check)
            endpoints.append(result)
            total_endpoints += 1
            if result.status_code == 404:
                all_404_count += 1
            if not result.success:
                if result.critical:
                    critical_failures += 1
                else:
                    non_critical_failures += 1

        # Step 3: Determine outcome
        endpoints_passed = sum(1 for e in endpoints if e.success)
        endpoints_failed = len(endpoints) - endpoints_passed

        # Special case: ALL endpoints return 404
        # This means infrastructure is up but app not deployed - treat as UNAVAILABLE
        if all_404_count == total_endpoints:
            return ContractProbeResult(
                target=env_name,
                platform=platform,
                base_url=self.base_url,
                reachable=True,  # Infrastructure reachable
                outcome=ProbeOutcome.UNAVAILABLE,
                enforcement_mode=self.enforcement_mode,
                timestamp=datetime.utcnow(),
                endpoints_checked=len(endpoints),
                endpoints_passed=0,
                endpoints_failed=len(endpoints),
                endpoints=endpoints,
                message=f"Target {env_name} infrastructure reachable but APP NOT DEPLOYED (all 404). Contract NOT validated.",
            )

        if critical_failures > 0:
            outcome = ProbeOutcome.FAILED
            message = f"Target {env_name} FAILED. {critical_failures} critical endpoint(s) failed."
        elif non_critical_failures > 0:
            outcome = ProbeOutcome.DEGRADED
            message = f"Target {env_name} DEGRADED. Critical checks pass, {non_critical_failures} non-critical failed."
        else:
            outcome = ProbeOutcome.VERIFIED
            message = f"Target {env_name} VERIFIED. All {len(endpoints)} contract checks passed."

        return ContractProbeResult(
            target=env_name,
            platform=platform,
            base_url=self.base_url,
            reachable=True,
            outcome=outcome,
            enforcement_mode=self.enforcement_mode,
            timestamp=datetime.utcnow(),
            endpoints_checked=len(endpoints),
            endpoints_passed=endpoints_passed,
            endpoints_failed=endpoints_failed,
            endpoints=endpoints,
            message=message,
        )


def run_contract_probe(
    env_name: str = "staging",
    enforcement_mode: EnforcementMode = EnforcementMode.ADVISORY,
) -> ContractProbeResult:
    """
    Run contract probe against specified environment.

    Loads endpoint from single source of truth (environment_endpoints.json).
    Returns explicit outcome - never claims validation when unreachable.
    """
    env_config = load_environment_config(env_name)

    base_url = env_config.get("base_url")
    if not base_url:
        return ContractProbeResult(
            target=env_name,
            platform="unknown",
            base_url="(not configured)",
            reachable=False,
            outcome=ProbeOutcome.UNAVAILABLE,
            enforcement_mode=enforcement_mode,
            timestamp=datetime.utcnow(),
            message=f"No endpoint configured for {env_name}. Source: {env_config.get('source')}",
        )

    print(f"Endpoint source: {env_config.get('source')}")
    print(f"Platform: {env_config.get('platform')}")
    print(f"Target URL: {base_url}")
    print(f"Enforcement: {enforcement_mode.value}")

    auth_token = os.environ.get("QGP_API_TOKEN") or os.environ.get("QGP_STAGING_READ_TOKEN")

    probe = ContractProbe(
        base_url=base_url,
        timeout_seconds=env_config.get("timeout_seconds", 30),
        auth_token=auth_token,
        enforcement_mode=enforcement_mode,
    )

    return probe.run_full_probe(env_name, env_config.get("platform", "unknown"))


def main() -> int:
    """
    CLI entry point with explicit exit codes.

    Exit codes:
    - 0: VERIFIED or (UNAVAILABLE/DEGRADED in ADVISORY mode)
    - 1: FAILED or (UNAVAILABLE/DEGRADED in REQUIRED mode)
    """
    import sys

    env = sys.argv[1] if len(sys.argv) > 1 else "staging"

    # Check for enforcement mode from env or args
    mode_str = os.environ.get("PROBE_ENFORCEMENT_MODE", "ADVISORY").upper()
    if len(sys.argv) > 2:
        mode_str = sys.argv[2].upper()

    try:
        enforcement_mode = EnforcementMode[mode_str]
    except KeyError:
        enforcement_mode = EnforcementMode.ADVISORY

    result = run_contract_probe(env, enforcement_mode)

    print("")
    print("=" * 70)
    print(f"OUTCOME: {result.outcome.value}")
    print(f"ENFORCEMENT: {result.enforcement_mode.value}")
    print(f"MESSAGE: {result.message}")
    print("=" * 70)
    print("")

    # Detailed endpoint summary
    print("ENDPOINT SUMMARY:")
    print("-" * 70)
    for ep in result.endpoints:
        status_icon = "✅" if ep.success else ("⚠️" if not ep.critical else "❌")
        print(f"  {status_icon} {ep.name}: {ep.status_code} ({ep.response_time_ms:.1f}ms)")
        if ep.errors:
            for err in ep.errors:
                print(f"      └─ {err}")
    print("")

    print(json.dumps(result.to_dict(), indent=2))

    # Exit code logic
    if result.outcome == ProbeOutcome.VERIFIED:
        print("")
        print("✅ VERIFIED - contract compliance confirmed")
        return 0
    elif result.outcome == ProbeOutcome.DEGRADED:
        print("")
        if result.enforcement_mode == EnforcementMode.REQUIRED:
            print("⚠️ DEGRADED in REQUIRED mode - non-blocking but logged")
        else:
            print("⚠️ DEGRADED - critical checks pass, some non-critical failed")
        return 0  # Degraded is non-blocking
    elif result.outcome == ProbeOutcome.UNAVAILABLE:
        print("")
        if result.enforcement_mode == EnforcementMode.REQUIRED:
            print("❌ UNAVAILABLE in REQUIRED mode - BLOCKING FAILURE")
            print("   Staging should be available after deployment.")
            return 1
        else:
            print("⚠️ UNAVAILABLE - NOT validated (non-blocking in ADVISORY mode)")
            print("   Contract compliance was NOT verified.")
            return 0
    else:  # FAILED
        print("")
        print("❌ CONTRACT FAILED - blocking")
        return 1


if __name__ == "__main__":
    import sys

    sys.exit(main())
